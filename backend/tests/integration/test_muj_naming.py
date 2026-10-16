"""Real session/CAS/CSRF/audits and CLI retries; artifact transport is simulated,
not a published MUJ dataset. All rows live in the rollback-only isolated test DB.
"""

import json
import sys
from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.cli import muj_naming as cli
from app.cli.indoor_demo import DemoError
from app.core.config import get_settings
from app.models import ActiveRelease, Revision
from app.models.admin import AuditEvent
from app.services.muj_update import apply_reviewed, plan
from app.services.publication import canonical, public_projection, snapshot
from tests.integration.test_admin import sign_in, version
from tests.integration.test_muj_update import identity as muj_identity
from tests.integration.test_muj_update import setup

pytestmark = pytest.mark.integration


@pytest.fixture
def identity(db, bundle, seeded):
    return muj_identity.__wrapped__(db, bundle, seeded)


def test_cli_actual_session_partial_receipt_failure_retry_conflict_permissions_and_isolation(
    client, db, bundle, identity, monkeypatch, tmp_path, capsys
):
    adapter, result, graph_path = setup(client, db, bundle, identity)
    draft = result["draft_id"]
    apply_reviewed(adapter, plan(adapter.request("GET", graph_path), draft))
    data = public_projection(snapshot(db, db.get(Revision, draft)))
    raw = canonical(data)
    from hashlib import sha256

    checksum = sha256(raw).hexdigest()
    release = {"id": str(uuid4()), "campus_id": str(cli.CAMPUS_ID), "artifact_checksum": checksum}
    release["artifact_url"] = (
        f"/api/v1/campuses/{cli.CAMPUS_ID}/artifacts/{release['id']}/{checksum}.json"
    )
    before_releases = list(db.scalars(select(ActiveRelease.release_id)))
    writes = []

    def read_graph():
        sign_in(client, identity)
        return client.get(graph_path).json()

    def data_audits():
        return db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action.like("catalog.%") | AuditEvent.action.like("graph.%"))
        )

    class HTTPClient:
        session = None

        def __init__(self, **kwargs):
            self.headers = {}

        def login(self, username, password):
            r = client.post(
                "/api/v1/admin/login",
                json={"username": username, "password": password},
                headers={"Origin": "http://localhost:5173"},
            )
            assert r.status_code == 200
            self.session = r.json()
            assert "user_id" in self.session and "user" not in self.session
            self.headers = {
                "Origin": "http://localhost:5173",
                "X-CSRF-Token": self.session["csrf_token"],
            }

        def request(self, method, path, payload=None, *, headers=None, binary=False):
            if method == "GET" and path.endswith("/release"):
                return deepcopy(release)
            if method == "GET" and "/artifacts/" in path:
                assert path == release["artifact_url"] and binary
                return raw
            r = client.request(
                method, path, json=payload, headers={**self.headers, **(headers or {})}
            )
            if method != "GET":
                writes.append((method, path, r.status_code))
            if not r.is_success:
                raise DemoError(f"API refused HTTP {r.status_code}")
            self.last_request_id = r.headers["X-Request-ID"]
            return r.json() if r.content else None

        def logout(self):
            if self.session:
                self.request("POST", "/api/v1/admin/logout")
                self.session = None

    monkeypatch.setattr(cli, "Client", HTTPClient)
    monkeypatch.setattr(
        cli, "prompt_login", lambda c, _: c.login(identity[0].username, identity[1])
    )
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()

    def invoke(apply=False, published_only=False):
        monkeypatch.setattr(
            sys,
            "argv",
            ["muj_naming"]
            + ([] if published_only else ["--draft", draft])
            + (["--apply-source-name"] if apply else []),
        )
        cli.main()

    invoke()
    assert not [w for w in writes if "/drafts/" in w[1]]
    folder = tmp_path / "private/muj-naming" / str(identity[0].id)
    report = json.loads(next(folder.glob("preflight-*")).read_text())
    assert len(report["changes"]) == 2 and not report["blockers"]
    auth = sign_in(client, identity)
    # Real services reject missing CSRF, stale CAS and foreign campus, not just client guards.
    c = next(c for c in report["changes"] if c["entity"] == "nodes")
    payload = {"changes": [{"entity": "nodes", "id": c["id"], "data": c["after"]}]}
    assert (
        client.post(
            graph_path,
            json=payload,
            headers={"Origin": "http://localhost:5173", "If-Match": f'"{report["draft_version"]}"'},
        ).status_code
        == 403
    )
    assert (
        client.post(
            graph_path, json=payload, headers=version(auth, report["draft_version"] - 1)
        ).status_code
        == 409
    )
    assert client.get(graph_path.replace(str(cli.CAMPUS_ID), str(uuid4()))).status_code == 403

    # An unchanged version at the prompt is required: preserve owner edits on conflict.
    def concurrent(_):
        state = client.get(graph_path).json()
        live = client.get("/api/v1/admin/session").json()
        active_headers = {"Origin": "http://localhost:5173", "X-CSRF-Token": live["csrf_token"]}
        named = next(iter(state["nodes"]))
        row = cli.writable("nodes", state["nodes"][named])
        row["label"] = "Owner-maintained unrelated junction"
        assert (
            client.post(
                graph_path,
                json={"changes": [{"entity": "nodes", "id": named, "data": row}]},
                headers=version(active_headers, state["revision_version"]),
            ).status_code
            == 200
        )
        return "APPLY NAMES"

    monkeypatch.setattr("builtins.input", concurrent)
    with pytest.raises(SystemExit):
        invoke(True)
    assert not [w for w in writes if "/drafts/" in w[1]]
    before_names = read_graph()
    monkeypatch.setattr("builtins.input", lambda _: "APPLY NAMES")
    original = cli.persist

    def fail_receipt(path, value):
        if path.name.startswith("receipt-"):
            raise OSError("fixture storage failure")
        original(path, value)

    monkeypatch.setattr(cli, "persist", fail_receipt)
    with pytest.raises(SystemExit):
        invoke(True)
    saved = read_graph()
    # First source change can be node or catalog, but precisely one transaction committed.
    remaining = cli.preflight(HTTPClientWithLogin(HTTPClient, identity), draft)
    assert len(remaining["changes"]) == 1
    audit_count = data_audits()
    invoke()  # read-only recovery, no invented original audit receipt
    assert data_audits() == audit_count
    monkeypatch.setattr(cli, "persist", original)
    invoke(True)
    final = read_graph()
    for r in cli.supported_changes():
        assert final[r["entity"]][r["id"]][cli.LABELS[r["entity"]]] == r["proposed_name"]
    assert final["edges"] == saved["edges"] and final["anchors"] == saved["anchors"]
    expected_rows = deepcopy(before_names)
    for change in cli.supported_changes():
        expected_rows[change["entity"]][change["id"]][cli.LABELS[change["entity"]]] = change[
            "proposed_name"
        ]
    for entity in ("nodes", "places", "edges", "anchors", "frames"):
        assert (
            final[entity] == expected_rows[entity]
        )  # All unrelated owner data/evidence preserved.
    assert list(db.scalars(select(ActiveRelease.release_id))) == before_releases
    n = final["revision_version"]
    invoke(True)
    invoke(True)
    assert read_graph()["revision_version"] == n
    receipts = list(folder.glob("receipt-*"))
    assert len(receipts) == 1  # original failed local receipt is never fabricated
    receipt = json.loads(receipts[0].read_text())
    assert receipt["audit_request_id"] and receipt["requested_by"] == str(identity[0].id)
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in folder.glob("*.json"))
    invoke(published_only=True)
    output = capsys.readouterr().out
    assert identity[1] not in output
    assert all(
        identity[1] not in p.read_text() and "csrf_token" not in p.read_text()
        for p in folder.glob("*.json")
    )


def HTTPClientWithLogin(cls, identity):
    c = cls()
    c.login(identity[0].username, identity[1])
    return c
