"""Actual CLI, HTTP contracts and normal review services; never publish a MUJ fixture."""

import base64
import json
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.cli import muj_publication as cli
from app.cli.indoor_demo import DemoError
from app.core.config import get_settings
from app.core.portable import is_private_file
from app.models import ActiveRelease, Revision
from app.models.admin import AuditEvent, RoleAssignment
from app.services import publication
from app.services.muj_update import apply_reviewed, plan
from tests.integration.test_admin import ORIGIN, sign_in, version
from tests.integration.test_imports import apply, preview
from tests.integration.test_muj import identity as muj_identity
from tests.integration.test_muj import provision
from tests.integration.test_muj_update import Adapter
from tests.integration.test_publication import reviewer as publication_reviewer

pytestmark = pytest.mark.integration


@pytest.fixture
def identity(db, bundle, seeded):
    return muj_identity.__wrapped__(db, bundle, seeded)


@pytest.fixture
def reviewer(db, bundle):
    return publication_reviewer.__wrapped__(db, bundle)


def test_real_cli_preflight_manual_findings_stale_checks_retry_and_independent_approval(
    client, db, bundle, identity, reviewer, monkeypatch, tmp_path, capsys
):
    import sys

    headers = sign_in(client, identity)
    result = provision(client, bundle, headers)
    draft_meta = {"id": result["draft_id"]}
    muj = SimpleNamespace(campus=SimpleNamespace(id=cli.CAMPUS_ID))
    for path in sorted(cli.ROOT.glob("batch-*.json")):
        response = client.post(
            f"/api/v1/admin/campuses/{cli.CAMPUS_ID}/drafts/{result['draft_id']}/imports",
            params={"filename": path.name},
            content=path.read_bytes(),
            headers={
                **headers,
                "Content-Type": "application/octet-stream",
                "X-Import-Options": base64.b64encode(
                    (cli.ROOT / "options.json").read_bytes()
                ).decode(),
                "Idempotency-Key": path.stem + "-publication-test",
            },
        )
        job = preview(db, response)
        apply(client, muj, draft_meta, headers, job)
    graph_path = f"/api/v1/admin/campuses/{cli.CAMPUS_ID}/drafts/{result['draft_id']}/graph"
    adapter = Adapter(client, headers)
    draft = result["draft_id"]
    base = graph_path.removesuffix("/graph")
    apply_reviewed(adapter, plan(adapter.request("GET", graph_path), draft))
    before_release = list(db.scalars(select(ActiveRelease.release_id)))
    db.add(
        RoleAssignment(user_id=reviewer[0].id, campus_id=cli.CAMPUS_ID, role="reviewer_publisher")
    )
    db.flush()
    reviewer_headers = sign_in(client, reviewer)
    packet = client.get(base + "/review").json()
    source = next(iter(packet["sources"]))
    approved = client.post(
        base + f"/sources/{source}/approve",
        headers=version(reviewer_headers, packet["edit_version"]),
    )
    assert approved.status_code == 200
    headers = sign_in(client, identity)
    packet = client.get(base + "/review").json()
    body = {
        "routes": [
            {
                "source": cli.place("10780185181"),
                "target": cli.place("11573265515"),
                "profile": p,
                "expected_found": p == "shortest",
                "cost_mode": "directions_only",
                "maximum_distance_m": None,
                "reason": "Limited OSM test: unknown accessibility excluded; no field survey.",
            }
            for p in ("shortest", "step_free")
        ]
    }
    run_response = client.post(
        base + "/validations", json=body, headers=version(headers, packet["edit_version"])
    )
    assert run_response.status_code == 200
    run = run_response.json()
    assert run["report"]["errors"] == 0 and run["report"]["warnings"] == 148
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    account = [identity]
    writes, statuses = [], []

    class HTTPClient:
        session = None

        def __init__(self, **kwargs):
            self.headers = ORIGIN

        def login(self, username, password):
            r = client.post(
                "/api/v1/admin/login",
                json={"username": username, "password": password},
                headers=ORIGIN,
            )
            assert r.status_code == 200
            self.session = r.json()
            assert "user_id" in self.session and "user" not in self.session
            self.headers = {**ORIGIN, "X-CSRF-Token": self.session["csrf_token"]}

        def request(self, method, path, payload=None, *, headers=None):
            r = client.request(
                method, path, json=payload, headers={**self.headers, **(headers or {})}
            )
            if method != "GET":
                writes.append(path)
                statuses.append(r.status_code)
            if not r.is_success:
                raise DemoError(f"Normal API refused with HTTP {r.status_code}")
            self.last_request_id = r.headers["X-Request-ID"]
            return r.json()

        def logout(self):
            if self.session:
                assert client.post("/api/v1/admin/logout", headers=self.headers).status_code == 204
                self.session = None

    monkeypatch.setattr(cli, "Client", HTTPClient)
    monkeypatch.setattr(
        cli, "prompt_login", lambda c, _: c.login(account[0][0].username, account[0][1])
    )

    def invoke(action="preflight", folder=None, draft_override=None):
        args = ["muj_publication", "--draft", str(draft_override or draft), "--action", action]
        if folder:
            args += ["--bundle", str(folder)]
        monkeypatch.setattr(sys, "argv", args)
        cli.main()

    foreign = db.scalar(select(Revision.id).where(Revision.campus_id == bundle.campus.id))
    with pytest.raises(SystemExit, match="HTTP 404"):
        invoke(draft_override=foreign)
    grant = db.get(RoleAssignment, (reviewer[0].id, cli.CAMPUS_ID, "reviewer_publisher"))
    db.delete(grant)
    db.flush()
    account[0] = reviewer
    with pytest.raises(SystemExit, match="HTTP 403"):
        invoke()
    db.add(
        RoleAssignment(user_id=reviewer[0].id, campus_id=cli.CAMPUS_ID, role="reviewer_publisher")
    )
    db.flush()
    account[0] = identity
    invoke()
    folder = next(tmp_path.rglob("report.json")).parent
    report = json.loads((folder / "report.json").read_text())
    assert report["version"] == packet["edit_version"] and report["version"] > 6
    assert report["checksum"] == packet["checksum"]
    assert report["warning_counts"] == {
        "connectivity_shortest": 52,
        "connectivity_step_free": 55,
        "unmapped_entrance": 33,
        "import_provenance": 3,
        "near_duplicate": 2,
        "components_shortest": 1,
        "components_step_free": 1,
        "unknown_accessibility": 1,
    }
    assert len(report["proposed_reasons"]) == 146
    assert {d["code"] for d in report["unjustified_findings"]} == {"near_duplicate"}
    assert not writes
    monkeypatch.setattr("builtins.input", lambda _: "SUBMIT")
    with pytest.raises(SystemExit, match="blockers"):
        invoke("submit", folder)
    assert not writes

    def assess(folder):
        path = folder / "manual-findings.json"
        manual = json.loads(path.read_text())
        for item in manual.values():
            item.update(
                accept_limited_osm_preview=True,
                reason="Fixture reviewer accepts only source-preserving local preview ambiguity, no physical separation or survey claim.",
                evidence_reviewed="Inspected pinned OSM ways, node tags, one anchor per isolated two-node component and documented route exclusions. GPS-on-stub approach remains possible.",
            )
        cli.persist(path, manual)

    assess(folder)
    invoke()
    report = json.loads((folder / "report.json").read_text())
    assert not report["blockers"], report["blockers"]
    proposal = json.loads((folder / "proposal.json").read_text())
    assert len(proposal["acknowledgements"]) == 148
    warning = next(iter(proposal["acknowledgements"]))
    proposal["acknowledgements"][warning] = (
        "Owner entered specific source/coverage explanation; preserve this exact text."
    )
    cli.persist(folder / "proposal.json", proposal)
    invoke()
    assert (
        json.loads((folder / "proposal.json").read_text())["acknowledgements"][warning]
        == proposal["acknowledgements"][warning]
    )

    # A change during human confirmation must be caught before posting.
    def race(_):
        db_revision = publication.locked_revision(db, cli.CAMPUS_ID, UUID(draft), read=True)
        db_revision.edit_version += 1
        db.flush()
        return "SUBMIT"

    monkeypatch.setattr("builtins.input", race)
    with db.begin_nested() as transaction:
        with pytest.raises(SystemExit, match="changed while reviewing"):
            invoke("submit", folder)
        transaction.rollback()
    assert not writes
    monkeypatch.setattr("builtins.input", lambda _: "SUBMIT")
    real_persist = cli.persist

    def fail_receipt(path, document):
        if path.name == "receipt-submit.json":
            raise OSError("Injected receipt disk failure after submission commit")
        real_persist(path, document)

    monkeypatch.setattr(cli, "persist", fail_receipt)
    with pytest.raises(SystemExit, match="may have committed"):
        invoke("submit", folder)
    monkeypatch.setattr(cli, "persist", real_persist)
    invoke("submit", folder)
    invoke("submit", folder)
    assert len(writes) == 1 and statuses == [200]
    receipt = json.loads((folder / "receipt-submit.json").read_text())
    assert receipt["state"] == "existing_action_verified" and "request_id" not in receipt
    assert (
        db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "review.submit", AuditEvent.revision_id == UUID(draft))
        )
        == 1
    )

    # Contributor gets a fresh bundle but normal server independent-review guard refuses.
    invoke()
    owner_review = max(tmp_path.rglob("report.json"), key=lambda p: p.stat().st_mtime_ns).parent
    assess(owner_review)
    invoke()
    monkeypatch.setattr("builtins.input", lambda _: "APPROVE")
    with pytest.raises(SystemExit, match="may have committed"):
        invoke("approve", owner_review)
    assert statuses[-1] == 403
    # Reviewer has a separate private bundle and must explicitly assess both ambiguous findings.
    account[0] = reviewer
    invoke()
    reviewer_folder = max(tmp_path.rglob("report.json"), key=lambda p: p.stat().st_mtime_ns).parent
    assert reviewer_folder != owner_review
    report = json.loads((reviewer_folder / "report.json").read_text())
    assert (
        report["existing_submissions"][0]["acknowledgements"][warning]
        == proposal["acknowledgements"][warning]
    )
    assess(reviewer_folder)
    invoke()
    invoke("approve", reviewer_folder)
    invoke("approve", reviewer_folder)
    assert statuses == [200, 403, 200]
    assert (
        db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "review.approve", AuditEvent.revision_id == UUID(draft))
        )
        == 1
    )
    assert list(db.scalars(select(ActiveRelease.release_id))) == before_release
    assert client.get(f"/api/v1/campuses/{cli.CAMPUS_ID}/release").status_code == 404
    for f in tmp_path.rglob("*.json"):
        raw = f.read_text()
        safe = identity[1] not in raw and reviewer[1] not in raw and "csrf_token" not in raw
        assert safe
        assert is_private_file(f)
    out = capsys.readouterr().out
    safe = identity[1] not in out and reviewer[1] not in out
    assert safe
    get_settings.cache_clear()
