"""Actual built API + independent worker check on runner-owned disposable PostGIS only.

Test-only account provisioning uses the existing bootstrap/role services. The demo
itself uses HTTP approvals, never writes approval flags. No passwords leave RAM.
"""

import json
import os
import secrets
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.cli.admin import bootstrap
from app.cli.dataset import read_bundle, seed_bundle
from app.cli.indoor_demo import Client, DemoError, Setup, journal
from app.models import ActiveRelease, Revision
from app.models.admin import AuditEvent, RoleAssignment, User
from app.models.floorplans import FloorplanJob
from app.models.publication import ReviewSubmission
from app.services.admin_auth import HASHER
from app.services.publication import checksum, snapshot


def main():
    url = os.environ["DATABASE_URL"]
    database = make_url(url).database
    if (
        os.environ.get("APP_ENV") != "test"
        or not database.startswith("scns_demo_")
        or not database.endswith("_e2e_test")
    ):
        raise RuntimeError("Built helper harness requires its uniquely owned disposable DB")
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(url)
    password, reviewer_password = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    bundle = read_bundle(Path("/app/data/demo/campus.json"))
    with Session(engine) as db, db.begin():
        seed_bundle(db, bundle)
        actor = bootstrap(db, "demo-owner", "Ephemeral test owner", password, bundle.campus.id)
        reviewer = User(
            username="demo-reviewer",
            display_name="Independent test reviewer",
            password_hash=HASHER.hash(reviewer_password),
        )
        db.add(reviewer)
        db.flush()
        db.add(
            RoleAssignment(
                user_id=reviewer.id, campus_id=bundle.campus.id, role="reviewer_publisher"
            )
        )
        actor_id = str(actor.id)
    owner, reviewer = Client(), Client()
    deadline = time.monotonic() + 30
    while True:
        try:
            owner.request("GET", "/api/v1/health/ready")
            break
        except DemoError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.25)
    owner.login("demo-owner", password)

    def reviewer_login(client):
        dashboard = owner.request("GET", f"/api/v1/admin/campuses/{bundle.campus.id}/dashboard")
        current_draft = dashboard["drafts"][0]
        draft_path = f"/api/v1/admin/campuses/{bundle.campus.id}/drafts/{current_draft['id']}"
        listing = owner.request("GET", draft_path + "/floors")
        floor = next(
            f
            for f in listing["floors"]
            if f["frame"] and f["frame"]["calibration"] and not f["layer"]["approved"]
        )
        for endpoint in (
            f"/sources/{floor['layer']['source_id']}/approve",
            f"/floors/{floor['id']}/calibration/approve",
        ):
            try:
                owner.request(
                    "POST",
                    draft_path + endpoint,
                    headers={"If-Match": f'"{listing["edit_version"]}"'},
                )
            except DemoError as exc:
                assert "HTTP 403" in str(exc)
            else:
                raise AssertionError("Normal server guards must reject self-approval")
        assert (
            owner.request("GET", draft_path + "/floors")["edit_version"] == listing["edit_version"]
        )
        return client.login("demo-reviewer", reviewer_password)

    campus = str(bundle.campus.id)
    base = f"/api/v1/admin/campuses/{campus}"
    original_release = owner.request("GET", base + "/dashboard")["release"]["id"]
    try:
        with TemporaryDirectory(prefix="scns-owned-demo-check-") as directory:
            # Retain full approved plans/calibration/tracing/connections in Draft3,
            # plus a separate user-created ACA Ground floor in another existing draft.
            earlier = owner.request("POST", base + "/drafts")
            assert earlier["version"] == 2
            old_path = base + f"/drafts/{earlier['id']}"
            building = next(
                b["id"]
                for b in owner.request("GET", old_path + "/floors")["buildings"]
                if b["code"] == "ACA"
            )
            owner.request(
                "POST",
                old_path + "/floors",
                {
                    "building_id": building,
                    "code": "G",
                    "label": "ACA retained Ground",
                    "ordering": 0,
                    "visibility": "public",
                },
                headers={"If-Match": '"1"'},
            )
            with journal(Path(directory) / "retained", campus, actor_id) as (path, retained):
                Setup(owner, reviewer, path, retained, reviewer_login).run()
                assert retained["draft_number"] == 3
            reviewer.logout()
            with Session(engine) as db:
                retained_checksums = {
                    r: checksum(snapshot(db, db.get(Revision, UUID(r))))
                    for r in (retained["draft"], earlier["id"])
                }
            # Lose the successful create response and later the successful plan apply response.
            with journal(Path(directory) / "target", campus, actor_id) as (path, state):
                original_request = owner.request
                lose = {"draft": True, "apply": True}

                def interrupted(method, api_path, *args, **kwargs):
                    response = original_request(method, api_path, *args, **kwargs)
                    if method == "POST" and api_path == base + "/drafts" and lose["draft"]:
                        lose["draft"] = False
                        raise DemoError("Simulated lost successful draft response")
                    if method == "POST" and api_path.endswith("/apply") and lose["apply"]:
                        lose["apply"] = False
                        raise DemoError("Simulated lost successful apply response")
                    return response

                owner.request = interrupted
                for expected in ("draft response", "apply response"):
                    try:
                        Setup(owner, reviewer, path, state, reviewer_login).run()
                    except DemoError as exc:
                        assert expected in str(exc)
                    else:
                        raise AssertionError("Interrupted step unexpectedly succeeded")
                    # Read exactly what the next process would load from persisted journal.
                    state = json.loads(path.read_text())
                assert state["pending"] == "Ground/apply"
                owner.request = original_request
                result = Setup(owner, reviewer, path, state, reviewer_login).run()
                assert state["complete"] and result["report"]["errors"] == 0
                assert len(result["evidence"]) == 14 and all(
                    e["passed"] for e in result["evidence"]
                )
                with Session(engine) as db:
                    revision_count = db.scalar(select(func.count()).select_from(Revision))
                    job_count = db.scalar(select(func.count()).select_from(FloorplanJob))
                    audit_count = db.scalar(select(func.count()).select_from(AuditEvent))
                    assert revision_count == 4 and job_count == 4
                    assert db.scalar(select(func.count()).select_from(ReviewSubmission)) == 0
                # Rerun does not create records, approvals, audit events or validation runs.
                same = Setup(owner, reviewer, path, state, reviewer_login).run()
                assert same["id"] == result["id"]
                with Session(engine) as db:
                    assert db.scalar(select(func.count()).select_from(Revision)) == revision_count
                    assert db.scalar(select(func.count()).select_from(FloorplanJob)) == job_count
                    assert db.scalar(select(func.count()).select_from(AuditEvent)) == audit_count
                    for identity, before in retained_checksums.items():
                        assert checksum(snapshot(db, db.get(Revision, UUID(identity)))) == before
                    assert (
                        str(db.get(ActiveRelease, (bundle.campus.id, "public")).release_id)
                        == original_release
                    )
                    events = db.scalars(
                        select(AuditEvent).where(AuditEvent.revision_id == UUID(state["draft"]))
                    ).all()
                    approvals = [
                        e
                        for e in events
                        if e.action in {"source.approve", "floor.calibration_approve"}
                    ]
                    assert len(approvals) == 4 and all(
                        str(e.actor_id) != actor_id for e in approvals
                    )
                    assert all(
                        str(e.actor_id) == actor_id
                        for e in events
                        if e.action in {"floorplan.upload", "indoor.patch", "connections.patch"}
                    )
                public_floors = owner.request("GET", f"/api/v1/campuses/{campus}/floors")["floors"]
                assert public_floors == []
                # Any subsequent user edit must stop reruns, never roll back that edit.
                target_path = base + f"/drafts/{state['draft']}"
                owner.request(
                    "POST",
                    target_path + "/floors",
                    {
                        "building_id": building,
                        "code": "USER",
                        "label": "User preserved edit",
                        "ordering": 9,
                        "visibility": "public",
                    },
                    headers={"If-Match": f'"{state["edit_version"]}"'},
                )
                try:
                    Setup(owner, reviewer, path, state, reviewer_login).run()
                except DemoError as exc:
                    assert "outside recorded" in str(exc)
                else:
                    raise AssertionError("External edits must halt setup")
            # A lost create response plus an intervening user edit is refused,
            # rather than silently adopting the newer version as a baseline.
            with journal(Path(directory) / "stale-create", campus, actor_id) as (path, state):
                original_request = owner.request

                def edited_create(method, api_path, *args, **kwargs):
                    response = original_request(method, api_path, *args, **kwargs)
                    if method == "POST" and api_path == base + "/drafts":
                        original_request(
                            "POST",
                            base + f"/drafts/{response['id']}/floors",
                            {
                                "building_id": building,
                                "code": "USER",
                                "label": "Intervening user floor",
                                "ordering": 7,
                            },
                            headers={"If-Match": '"1"'},
                        )
                        raise DemoError("Lost create after intervening edit")
                    return response

                owner.request = edited_create
                try:
                    Setup(owner, reviewer, path, state, reviewer_login).run()
                except DemoError as exc:
                    assert "Lost create" in str(exc)
                else:
                    raise AssertionError("Expected ambiguous create")
                owner.request = original_request
                state = json.loads(path.read_text())
                try:
                    Setup(owner, reviewer, path, state, reviewer_login).run()
                except DemoError as exc:
                    assert "outside recorded" in str(exc)
                else:
                    raise AssertionError("Edited create retry must not become the baseline")
                assert state["edit_version"] == 1 and state["steps"] == {}
                saved = owner.request("GET", base + f"/drafts/{state['draft']}/floors")
                assert (
                    saved["edit_version"] == 2
                    and saved["floors"][0]["label"] == "Intervening user floor"
                )
                with Session(engine) as db:
                    assert db.scalar(select(func.count()).select_from(Revision)) == 5
            gate = str(next(p.id for p in bundle.places if p.code == "GATE"))
            library = str(next(p.id for p in bundle.places if p.code == "LIB"))
            route = owner.request(
                "POST",
                "/api/v1/routes",
                {
                    "campus_id": campus,
                    "source": {"kind": "place", "place_id": gate},
                    "destination": {"kind": "place", "place_id": library},
                    "profile": "shortest",
                    "expected_release_id": original_release,
                },
            )
            assert route["distance_m"] == 256.88 and len(route["segments"]) == 3
            # Same actor approval and reviewer editor privileges remain rejected by server.
            wrong = Client()
            wrong.login("demo-reviewer", reviewer_password)
            try:
                try:
                    wrong.request(
                        "POST",
                        old_path + "/floors",
                        {"building_id": building, "code": "NO", "label": "Denied", "ordering": 2},
                        headers={"If-Match": '"2"'},
                    )
                except DemoError as exc:
                    assert "HTTP 403" in str(exc)
                else:
                    raise AssertionError("Reviewer must not become editor")
            finally:
                wrong.logout()
        print(
            "PASS: built API/real worker PNG masking; separate Draft3 and retained approved tracing preserved; two independent approval pairs;14 computed cases18/36/57m; lost-response recovery; zero-write rerun; stale-edit refusal; public release isolation."
        )
    finally:
        reviewer.logout()
        owner.logout()
        engine.dispose()


if __name__ == "__main__":
    main()
