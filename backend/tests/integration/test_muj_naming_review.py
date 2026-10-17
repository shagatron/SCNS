"""Full normal-history fixture for read-only clone inspection, rollback-only DB.

Source-based MUJ fixture publication exists only inside this isolated test
transaction; no cloud developer/Windows release or external app is published.
"""

import base64
import json
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import select

from app.cli import muj_naming as naming
from app.cli import muj_naming_review as cli
from app.cli import muj_publication as original
from app.cli.indoor_demo import DemoError
from app.core.config import get_settings
from app.models import ActiveRelease
from app.models.admin import AuditEvent, RoleAssignment
from app.models.publication import ReviewSubmission
from app.services.muj_update import apply_reviewed, plan
from tests.integration.test_admin import sign_in, version
from tests.integration.test_imports import apply, preview
from tests.integration.test_muj import provision
from tests.integration.test_muj_update import Adapter
from tests.integration.test_muj_update import identity as muj_identity
from tests.integration.test_publication import reviewer as publication_reviewer

pytestmark = pytest.mark.integration


@pytest.fixture
def identity(db, bundle, seeded):
    return muj_identity.__wrapped__(db, bundle, seeded)


@pytest.fixture
def reviewer(db, bundle):
    return publication_reviewer.__wrapped__(db, bundle)


def test_normal_parent_history_clone_diff_current_reasons_and_read_only_retries(
    client, db, bundle, identity, reviewer, monkeypatch, tmp_path
):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    owner_headers = sign_in(client, identity)
    result = provision(client, bundle, owner_headers)
    fixture = SimpleNamespace(campus=SimpleNamespace(id=cli.CAMPUS_ID))
    for batch in sorted(original.ROOT.glob("batch-*.json")):
        response = client.post(
            f"/api/v1/admin/campuses/{cli.CAMPUS_ID}/drafts/{result['draft_id']}/imports",
            params={"filename": batch.name},
            content=batch.read_bytes(),
            headers={
                **owner_headers,
                "Content-Type": "application/octet-stream",
                "X-Import-Options": base64.b64encode(
                    (original.ROOT / "options.json").read_bytes()
                ).decode(),
                "Idempotency-Key": batch.stem + "-e22-review-fixture",
            },
        )
        job = preview(db, response)
        apply(client, fixture, {"id": result["draft_id"]}, owner_headers, job)
    adapter = Adapter(client, owner_headers)
    path = f"/api/v1/admin/campuses/{cli.CAMPUS_ID}/drafts/{result['draft_id']}/graph"
    parent_id = result["draft_id"]
    base = path.removesuffix("/graph")
    apply_reviewed(adapter, plan(adapter.request("GET", path), parent_id))
    db.add(
        RoleAssignment(user_id=reviewer[0].id, campus_id=cli.CAMPUS_ID, role="reviewer_publisher")
    )
    db.flush()
    headers = sign_in(client, reviewer)
    packet = client.get(base + "/review").json()
    source = next(iter(packet["sources"]))
    r = client.post(
        base + f"/sources/{source}/approve", headers=version(headers, packet["edit_version"])
    )
    assert r.status_code == 200, r.text
    body = {
        "routes": [
            {
                "source": original.place("10780185181"),
                "target": original.place("11573265515"),
                "profile": p,
                "expected_found": p == "shortest",
                "cost_mode": "directions_only",
                "maximum_distance_m": None,
                "reason": "Isolated source-only fixture coverage; step-free evidence absent.",
            }
            for p in ("shortest", "step_free")
        ]
    }
    headers = sign_in(client, identity)
    packet = client.get(base + "/review").json()
    r = client.post(
        base + "/validations", json=body, headers=version(headers, packet["edit_version"])
    )
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["report"]["warnings"] == 148
    graph = client.get(path).json()
    # Explicit per-finding fixture reasons are not production acknowledgements.
    assessments = {
        d["id"]: {
            "accept_limited_osm_preview": True,
            "reason": "Fixture accepts only unresolved source-stub ambiguity, never physical separation.",
            "evidence_reviewed": "Exact two source ways and entrance anchors retained; no floor/physical or accessibility verification.",
        }
        for d in run["report"]["diagnostics"]
        if d["code"] == "near_duplicate"
    }
    _, _, _, jobs, _ = original.collect(adapter, UUID(parent_id), UUID(run["id"]))
    report = original.prepare(packet, graph, run, jobs, None, parent_id, assessments)
    assert not report["blockers"], report["blockers"]
    acknowledgements = report["proposed_reasons"]
    assert len(acknowledgements) == 148
    submitted = client.post(
        base + "/submissions",
        json={"validation_id": run["id"], "acknowledgements": acknowledgements},
        headers=version(headers, packet["edit_version"]),
    )
    assert submitted.status_code == 200, submitted.text
    sub = submitted.json()
    headers = sign_in(client, reviewer)
    approved = client.post(
        base + f"/submissions/{sub['id']}/decision",
        json={
            "decision": "approve",
            "notes": "Distinct test application account review only; no independent human or institution claim.",
            "acknowledgements": acknowledgements,
        },
        headers=version(headers, sub["edit_version"]),
    )
    assert approved.status_code == 200, approved.text
    published = client.post(
        base + "/publish",
        json={
            "submission_id": sub["id"],
            "expected_release_id": None,
            "key": "isolated-e22-parent-fixture",
        },
        headers=version(headers, approved.json()["edit_version"]),
    )
    assert published.status_code == 200, published.text
    headers = sign_in(client, identity)
    created = client.post(
        f"/api/v1/admin/campuses/{cli.CAMPUS_ID}/drafts",
        headers={**headers, "Idempotency-Key": "isolated-e22-clone-fixture"},
    )
    assert created.status_code == 201, created.text
    draft = created.json()["id"]
    clone_base = f"/api/v1/admin/campuses/{cli.CAMPUS_ID}/drafts/{draft}"

    class HTTP:
        session = {"user_id": str(identity[0].id)}

        def request(
            self,
            method,
            path,
            payload=None,
            *,
            headers_override=None,
            binary=False,
            headers=None,
            query=None,
        ):
            r = client.request(
                method, path, json=payload, params=query, headers={**auth[0], **(headers or {})}
            )
            if not r.is_success:
                raise DemoError(f"Normal API refused HTTP {r.status_code}")
            self.last_request_id = r.headers["X-Request-ID"]
            return r.content if binary else r.json() if r.content else None

    auth = [headers]
    http = HTTP()
    naming.apply_reviewed(http, naming.preflight(http, draft), lambda _: None)
    packet = client.get(clone_base + "/review").json()
    assert packet["edit_version"] == 3
    r = client.post(
        clone_base + "/validations", json=body, headers=version(headers, packet["edit_version"])
    )
    assert r.status_code == 200, r.text
    validation = r.json()
    assert validation["report"]["warnings"] == 145
    before = list(db.scalars(select(ActiveRelease.release_id)))
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    # Following calls use exclusively dataset GETs; auth handled separately.
    real_request = http.request
    reads = []

    def readonly(method, path, *args, **kwargs):
        assert method == "GET"
        reads.append(path)
        return real_request(method, path, *args, **kwargs)

    monkeypatch.setattr(http, "request", readonly)
    folder, report = cli.preflight(http, UUID(draft), UUID(validation["id"]))
    assert not report["blockers"], report["blockers"]
    assert len(report["proposed_reasons"]) == 145 and len(report["counterparts"]) == 145
    assert sum(t["old_id"] == t["current_id"] for t in report["counterparts"]) == 143
    assert len(report["removed_import_findings"]) == 3 and len(report["original_imports"]) == 3
    assert report["sources"] == packet["sources"]  # approvals retained, not rewritten
    proposal = json.loads((folder / "proposal.json").read_text())
    warning = next(iter(proposal["acknowledgements"]))
    proposal["acknowledgements"][warning] = (
        "Owner entered a specific revised explanation; preserve exact text on repeated reads."
    )
    cli.persist(folder / "proposal.json", proposal)
    again, updated = cli.preflight(http, UUID(draft), UUID(validation["id"]))
    assert again == folder and json.loads((folder / "proposal.json").read_text()) == proposal
    assert not updated["blockers"]
    # Exercise the actual CLI with real top-level SessionOut and normal API submissions.
    # Nested test savepoints keep the subsequent editable-draft regression unchanged.
    import sys

    monkeypatch.setattr(original, "Client", lambda **kwargs: http)

    def login(*args):
        auth[0] = sign_in(client, identity)
        http.session = client.get("/api/v1/admin/session").json()
        assert http.session["user_id"] == str(identity[0].id) and "user" not in http.session

    def logout():
        response = client.post("/api/v1/admin/logout", headers=auth[0])
        assert response.status_code == 204

    http.logout = logout
    monkeypatch.setattr(original, "prompt_login", login)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "muj_publication",
            "--naming-clone",
            "--action",
            "submit",
            "--draft",
            draft,
            "--validation",
            validation["id"],
            "--bundle",
            str(folder),
            "--expected-version",
            "3",
            "--expected-checksum",
            packet["checksum"],
        ],
    )
    monkeypatch.setattr("builtins.input", lambda _: "SUBMIT E22")
    actual_persist = cli.persist
    for interruption in ("response", "receipt"):
        transaction = db.begin_nested()
        posts = []
        failure = [True]

        def transport(
            method, target, *args, posts=posts, interruption=interruption, failure=failure, **kwargs
        ):
            if method != "GET":
                assert method == "POST" and target == clone_base + "/submissions"
                posts.append(target)
            result = real_request(method, target, *args, **kwargs)
            if method == "POST" and interruption == "response" and failure[0]:
                failure[0] = False
                raise DemoError("Simulated response loss after successful server commit")
            return result

        def save(target, value, interruption=interruption, failure=failure):
            if target.name == "receipt-submit.json" and interruption == "receipt" and failure[0]:
                failure[0] = False
                raise OSError("Simulated disk failure after successful application")
            return actual_persist(target, value)

        monkeypatch.setattr(http, "request", transport)
        monkeypatch.setattr(cli, "persist", save)
        try:
            with pytest.raises(SystemExit, match="may have committed"):
                original.main()
            submissions = list(
                db.scalars(
                    select(ReviewSubmission).where(ReviewSubmission.revision_id == UUID(draft))
                )
            )
            events = list(
                db.scalars(
                    select(AuditEvent).where(
                        AuditEvent.revision_id == UUID(draft), AuditEvent.action == "review.submit"
                    )
                )
            )
            assert len(submissions) == len(events) == len(posts) == 1
            assert submissions[0].acknowledgements == proposal["acknowledgements"]
            assert events[0].actor_id == identity[0].id
            assert not (folder / "receipt-submit.json").exists()
            # Same command reconciles exact committed server state, never prompts/posts again.
            monkeypatch.setattr(
                "builtins.input", lambda _: pytest.fail("Exact retry must be read-only")
            )
            original.main()
            original.main()
            recovery = json.loads((folder / "receipt-submit-recovery.json").read_text())
            assert recovery["submission_id"] == str(submissions[0].id)
            assert "request_id" not in recovery and len(posts) == 1
            assert (
                len(
                    list(
                        db.scalars(
                            select(AuditEvent).where(
                                AuditEvent.revision_id == UUID(draft),
                                AuditEvent.action == "review.submit",
                            )
                        )
                    )
                )
                == 1
            )
            after = client.get(clone_base + "/review")  # Logged out by CLI: normal auth required.
            assert after.status_code == 401
            login()
            after = client.get(clone_base + "/review").json()
            assert after["diff"] == packet["diff"] and after["sources"] == packet["sources"]
            assert after["checksum"] == packet["checksum"] and after["edit_version"] == 4
            assert list(db.scalars(select(ActiveRelease.release_id))) == before
            assert json.loads((folder / "proposal.json").read_text()) == proposal
            # Altered private reasons cannot masquerade as the already-submitted action.
            edited = json.loads(json.dumps(proposal))
            edited["acknowledgements"][warning] = (
                "Different explanation after successful server submission."
            )
            actual_persist(folder / "proposal.json", edited)
            with pytest.raises(SystemExit, match="intent differs"):
                original.main()
            assert len(posts) == 1
            actual_persist(folder / "proposal.json", proposal)
        finally:
            transaction.rollback()
            db.expire_all()
            for name in (
                "intent-submit.json",
                "receipt-submit.json",
                "receipt-submit-recovery.json",
            ):
                (folder / name).unlink(missing_ok=True)  # Test-owned temporary files only.
            monkeypatch.setattr(cli, "persist", actual_persist)
            monkeypatch.setattr("builtins.input", lambda _: "SUBMIT E22")
            login()
    # Normal endpoint still enforces permission, CSRF and CAS. No helper bypass.
    with db.begin_nested() as guard_tx:
        grants = list(
            db.scalars(
                select(RoleAssignment).where(
                    RoleAssignment.user_id == identity[0].id,
                    RoleAssignment.campus_id == cli.CAMPUS_ID,
                )
            )
        )
        for grant in grants:
            db.delete(grant)
        db.flush()
        with pytest.raises(DemoError, match="403"):
            cli.submit(
                http, draft, validation["id"], folder, 3, packet["checksum"], lambda _: "SUBMIT E22"
            )
        guard_tx.rollback()
    db.expire_all()
    for headers_override in (
        {"If-Match": '"3"', "X-CSRF-Token": "invalid"},
        {"If-Match": '"2"'},
    ):
        r = client.post(
            clone_base + "/submissions", json=proposal, headers={**auth[0], **headers_override}
        )
        assert r.status_code == (403 if "X-CSRF-Token" in headers_override else 409)
    assert not list(
        db.scalars(select(ReviewSubmission).where(ReviewSubmission.revision_id == UUID(draft)))
    )
    monkeypatch.setattr(http, "request", readonly)
    # A stale local key must survive as an explicit blocker, never be dropped.
    proposal["acknowledgements"]["stale-id"] = (
        "Owner retained stale text for manual reconciliation."
    )
    cli.persist(folder / "proposal.json", proposal)
    _, blocked = cli.preflight(http, UUID(draft), UUID(validation["id"]))
    assert (
        blocked["blockers"]
        and "stale-id" in json.loads((folder / "proposal.json").read_text())["acknowledgements"]
    )
    # A real version change after validation stops before suggesting reasons.
    graph = client.get(clone_base + "/graph").json()
    other = next(
        i for i in graph["nodes"] if i not in {s["id"] for s in naming.supported_changes()}
    )
    row = naming.writable("nodes", graph["nodes"][other])
    row["label"] = "Preserve owner junction edit"
    assert (
        client.post(
            clone_base + "/graph",
            json={"changes": [{"entity": "nodes", "id": other, "data": row}]},
            headers=version(auth[0], graph["revision_version"]),
        ).status_code
        == 200
    )
    with pytest.raises(DemoError, match="diff"):
        cli.preflight(http, UUID(draft), UUID(validation["id"]))
    assert list(db.scalars(select(ActiveRelease.release_id))) == before
    assert json.loads((folder / "proposal.json").read_text()) == proposal
    conflict = json.loads((folder.parent / "blocked.json").read_text())
    assert conflict["blockers"] and conflict["details"]["observed_diff"]
    assert any(d["id"] == other for d in conflict["details"]["observed_diff"])
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in tmp_path.rglob("*.json"))
    assert all(
        identity[1] not in p.read_text() and "csrf_token" not in p.read_text()
        for p in tmp_path.rglob("*.json")
    )
    get_settings.cache_clear()
