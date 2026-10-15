"""Actual built helper/API/import worker, owned disposable DB; no developer writes."""

import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.cli.admin import bootstrap
from app.cli.dataset import read_bundle, seed_bundle
from app.cli.indoor_demo import DemoError
from app.cli.muj import LocalClient, stage
from app.models import ActiveRelease, Campus, Edge, Place, Revision
from app.models.admin import AuditEvent
from app.models.imports import ImportJob
from app.models.publication import SourceAsset
from app.services.imports import stable_id
from app.services.muj_setup import CAMPUS_ID, ROOT
from app.services.muj_update import apply_reviewed, plan


def main():
    url = os.environ["DATABASE_URL"]
    database = make_url(url).database
    if (
        os.environ.get("APP_ENV") != "test"
        or not database.startswith("scns_demo_")
        or not database.endswith("_e2e_test")
    ):
        raise RuntimeError("Owned disposable database required")
    engine = create_engine(url)
    password = secrets.token_urlsafe(32)
    bundle = read_bundle(Path("/app/data/demo/campus.json"))
    with Session(engine) as db, db.begin():
        release = seed_bundle(db, bundle)
        bootstrap(db, "muj-test-owner", "Ephemeral owner", password, bundle.campus.id)
        before = str(release.id)
    client = LocalClient()
    client.login("muj-test-owner", password)
    try:
        second = LocalClient()
        second.login("muj-test-owner", password)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(
                    pool.map(
                        lambda c: c.request(
                            "POST", f"/api/v1/admin/campuses/{bundle.campus.id}/muj-setup"
                        ),
                        [client, second],
                    )
                )
            assert len({r["draft_id"] for r in results}) == 1
            assert sum(r["created"] for r in results) == 1
        finally:
            second.logout()
        # Stop deliberately after the worker prepares the first preview; rerun reconciles it.
        try:
            stage(client, ROOT, confirm=lambda _: "STOP")
        except DemoError as exc:
            assert "Stopped before apply" in str(exc)
        else:
            raise AssertionError("Expected bounded interruption")
        state = stage(client, ROOT, confirm=lambda _: "APPLY")
        with Session(engine) as db:
            revision = db.get(Revision, UUID(state["draft_id"]))
            v = revision.edit_version
            counts = {
                m.__tablename__: db.scalar(
                    select(func.count()).select_from(m).where(m.campus_id == CAMPUS_ID)
                )
                for m in (Revision, Edge, Place, ImportJob)
            }
            assert revision.status == "draft"
            assert not db.get(Campus, CAMPUS_ID).is_demo
            assert db.get(ActiveRelease, (CAMPUS_ID, "public")) is None
            assert str(db.get(ActiveRelease, (bundle.campus.id, "public")).release_id) == before
            assert all(
                s.approved_by is None
                for s in db.scalars(select(SourceAsset).where(SourceAsset.campus_id == CAMPUS_ID))
            )
            assert (
                counts["import_jobs"] == 3
                and counts["navigation_edges"] == 688
                and counts["places"] == 55
            )
            audits = db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.campus_id == CAMPUS_ID)
            )
        repeated = stage(
            client,
            ROOT,
            confirm=lambda _: (_ for _ in ()).throw(
                AssertionError("Committed replay must not prompt")
            ),
        )
        assert repeated["draft_id"] == state["draft_id"]
        with Session(engine) as db:
            assert db.get(Revision, UUID(state["draft_id"])).edit_version == v
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(AuditEvent.campus_id == CAMPUS_ID)
                )
                == audits
            )
        path = f"/api/v1/admin/campuses/{CAMPUS_ID}/drafts/{state['draft_id']}/graph"
        preview = plan(client.request("GET", path), state["draft_id"])
        assert preview["counts"] == {"add": 20, "update": 0, "delete": 2}
        receipt = apply_reviewed(client, preview)
        assert receipt["state"] == "applied"
        assert apply_reviewed(client, preview)["state"] == "already_applied"
        corrected = client.request("GET", path)
        assert (len(corrected["nodes"]), len(corrected["edges"]), len(corrected["anchors"])) == (
            295,
            700,
            22,
        )
        with Session(engine) as db:
            assert db.get(Revision, UUID(state["draft_id"])).edit_version == v + 1
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(AuditEvent.request_id == receipt["audit_request_id"])
                )
                == 22
            )
            assert db.get(ActiveRelease, (CAMPUS_ID, "public")) is None
            assert str(db.get(ActiveRelease, (bundle.campus.id, "public")).release_id) == before
            assert all(
                s.approved_by is None
                for s in db.scalars(select(SourceAsset).where(SourceAsset.campus_id == CAMPUS_ID))
            )
        target = str(stable_id(CAMPUS_ID, "places", "osm-node-10828149259"))
        source = str(stable_id(CAMPUS_ID, "places", "osm-node-10780185180"))
        new_route = client.request("GET", path + f"/route-test?source={source}&target={target}")
        assert new_route["found"] and new_route["distance_m"] > 0
        print(
            "V2 built computed University Entrance -> mapped entrance10828149259:",
            new_route["distance_m"],
            "metres,",
            len(new_route["edge_ids"]),
            "stored edges",
        )
        try:
            stage(client, ROOT, confirm=lambda _: "APPLY")
        except DemoError as error:
            assert "409" in str(error)
        else:
            raise AssertionError("Original v1 helper must not replay after correction")
        print(
            "PASS built v2 correction: exact preview, one atomic graph POST, 22 actor audits, explicit replaced-edge removal, retry no-op, old-helper guard, unapproved source/public release isolation."
        )
        print(
            "PASS built MUJ helper: interrupted preview resumed; three real-worker batches applied; replay unchanged; draft/source/audit/public isolation; route evidence prepared."
        )
    finally:
        client.logout()
        engine.dispose()


if __name__ == "__main__":
    main()
