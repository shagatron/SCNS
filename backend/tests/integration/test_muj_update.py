"""Versioned source corrections through the actual campus-scoped transactional graph API."""

import pytest
from sqlalchemy import func, select

from app.cli.indoor_demo import DemoError
from app.models import ActiveRelease
from app.models.admin import AuditEvent, RoleAssignment
from app.services.imports import stable_id
from app.services.muj_setup import CAMPUS_ID
from app.services.muj_update import apply_reviewed, plan
from tests.integration.test_admin import version
from tests.integration.test_muj import identity as muj_identity
from tests.integration.test_muj import import_all

pytestmark = pytest.mark.integration


@pytest.fixture
def identity(db, bundle, seeded):
    return muj_identity.__wrapped__(db, bundle, seeded)


class Adapter:
    def __init__(self, client, headers):
        self.client, self.headers = client, headers
        self.posts = 0

    def request(self, method, path, payload=None, *, headers=None):
        response = self.client.request(
            method, path, json=payload, headers={**self.headers, **(headers or {})}
        )
        assert response.status_code == 200, response.text
        self.last_request_id = response.headers["X-Request-ID"]
        self.posts += method == "POST"
        return response.json()


def setup(client, db, bundle, identity):
    headers, result, _, _ = import_all(client, db, bundle, identity)
    path = f"/api/v1/admin/campuses/{CAMPUS_ID}/drafts/{result['draft_id']}/graph"
    return Adapter(client, headers), result, path


def test_reviewed_update_permissions_atomic_replacement_audit_replay_and_public_isolation(
    client, db, bundle, identity
):
    adapter, result, path = setup(client, db, bundle, identity)
    current = adapter.request("GET", path)
    preview = plan(current, result["draft_id"])
    old_route = client.get(
        path + "/route-test",
        params={
            "source": str(stable_id(CAMPUS_ID, "places", "osm-node-10780185180")),
            "target": str(stable_id(CAMPUS_ID, "places", "osm-node-10828149259")),
        },
    )
    assert not old_route.json()["found"]
    before_release = list(db.scalars(select(ActiveRelease.release_id)))
    # The correction cannot acquire privileges missing from the existing graph service.
    owner_role = db.get(RoleAssignment, (identity[0].id, CAMPUS_ID, "system_admin"))
    db.delete(owner_role)
    db.flush()
    for role in ["reviewer_publisher", "operations", None]:
        assignment = (
            RoleAssignment(user_id=identity[0].id, campus_id=CAMPUS_ID, role=role) if role else None
        )
        if assignment:
            db.add(assignment)
        db.flush()
        response = client.post(
            path,
            json={"changes": preview["changes"]},
            headers=version(adapter.headers, current["revision_version"]),
        )
        assert response.status_code == 403
        if assignment:
            db.delete(assignment)
        db.flush()
    db.add(RoleAssignment(user_id=identity[0].id, campus_id=CAMPUS_ID, role="editor"))
    db.flush()
    receipt = apply_reviewed(adapter, preview)
    assert receipt["state"] == "applied" and adapter.posts == 1
    updated = adapter.request("GET", path)
    assert (len(updated["nodes"]), len(updated["edges"]), len(updated["anchors"])) == (295, 700, 22)
    assert updated["revision_version"] == current["revision_version"] + 1
    for change in preview["changes"]:
        if change["data"] is None:
            assert change["id"] not in updated[change["entity"]]
    audits = list(
        db.scalars(select(AuditEvent).where(AuditEvent.request_id == receipt["audit_request_id"]))
    )
    assert len(audits) == 22 and all(a.actor_id == identity[0].id for a in audits)
    assert sum(a.action == "graph.edges.delete" for a in audits) == 2
    assert apply_reviewed(adapter, preview)["state"] == "already_applied"
    assert adapter.posts == 1
    assert list(db.scalars(select(ActiveRelease.release_id))) == before_release
    assert client.get(f"/api/v1/campuses/{CAMPUS_ID}/release").status_code == 404
    quality = adapter.request("GET", path + "/validation")
    assert quality["errors"] == 0, quality
    print("V2 graph validation", quality["errors"], quality["warnings"])
    for source, target, profile in [
        ("10780185181", "11573265515", "shortest"),
        ("10780185181", "11573972967", "shortest"),
        ("10780185181", "12585506492", "shortest"),
        ("10780185180", "10780185181", "shortest"),
        ("10780185181", "11573265515", "step_free"),
        ("10780185180", "10828149259", "shortest"),
    ]:
        response = client.get(
            path + "/route-test",
            params={
                "source": str(stable_id(CAMPUS_ID, "places", "osm-node-" + source)),
                "target": str(stable_id(CAMPUS_ID, "places", "osm-node-" + target)),
                "profile": profile,
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "synthetic" not in data["notice"].lower()
        if (
            target in ["12585506492"]
            or (source == "10780185180" and target == "10780185181")
            or profile == "step_free"
        ):
            assert not data["found"]
        elif target in ["11573265515", "11573972967", "10828149259"]:
            assert data["found"]
        print(
            "V2 computed route",
            source,
            target,
            profile,
            data["found"],
            data["distance_m"],
            len(data["edge_ids"]),
        )
    db.add(RoleAssignment(user_id=identity[0].id, campus_id=CAMPUS_ID, role="system_admin"))
    db.flush()
    assert (
        client.post(
            f"/api/v1/admin/campuses/{bundle.campus.id}/muj-setup", headers=adapter.headers
        ).status_code
        == 409
    )


def test_unrelated_owner_edit_preserved_and_stale_preview_cannot_apply(
    client, db, bundle, identity
):
    adapter, result, path = setup(client, db, bundle, identity)
    initial = adapter.request("GET", path)
    preview = plan(initial, result["draft_id"])
    used = {
        c["data"][k]
        for c in preview["changes"]
        if c["entity"] == "edges" and c["data"]
        for k in ["from_node_id", "to_node_id"]
    }
    identity_id = next(i for i in initial["nodes"] if i not in used)
    data = {
        k: initial["nodes"][identity_id][k]
        for k in ["frame_id", "label", "visibility", "point", "evidence"]
    }
    data["label"] = "Owner edited unrelated node — preserve"
    adapter.request(
        "POST",
        path,
        {"changes": [{"entity": "nodes", "id": identity_id, "data": data}]},
        headers={"If-Match": f'"{initial["revision_version"]}"'},
    )
    with pytest.raises(DemoError, match="since preview"):
        apply_reviewed(adapter, preview)
    response = client.post(
        path,
        json={"changes": preview["changes"]},
        headers=version(adapter.headers, initial["revision_version"]),
    )
    assert response.status_code == 409
    fresh = adapter.request("GET", path)
    apply_reviewed(adapter, plan(fresh, result["draft_id"]))
    assert adapter.request("GET", path)["nodes"][identity_id]["label"] == data["label"]


def test_late_failure_rolls_back_replaced_edges_new_records_version_and_audits(
    client, db, bundle, identity, monkeypatch
):
    from app.services import admin_graph

    adapter, result, path = setup(client, db, bundle, identity)
    initial = adapter.request("GET", path)
    preview = plan(initial, result["draft_id"])
    audits = db.scalar(select(func.count()).select_from(AuditEvent))

    def fail(*args, **kwargs):
        raise ValueError("Injected late audit failure")

    monkeypatch.setattr(admin_graph, "audit", fail)
    with pytest.raises(ValueError, match="Injected"):
        apply_reviewed(adapter, preview)
    assert adapter.request("GET", path) == initial
    assert db.scalar(select(func.count()).select_from(AuditEvent)) == audits


@pytest.mark.parametrize("fail_receipt", [False, True])
def test_cli_real_session_application_and_read_only_receipt_recovery(
    client, db, bundle, identity, tmp_path, monkeypatch, capsys, fail_receipt
):
    import json
    import sys
    from uuid import UUID

    from app.cli import muj_update as cli
    from app.core.config import get_settings
    from tests.integration.test_admin import ORIGIN

    adapter, result, path = setup(client, db, bundle, identity)
    initial = adapter.request("GET", path)
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    adapters = []

    class CLIAdapter(Adapter):
        session = None

        def login(self, username, password):
            response = client.post(
                "/api/v1/admin/login",
                json={"username": username, "password": password},
                headers=ORIGIN,
            )
            assert response.status_code == 200
            self.session = response.json()
            assert "user" not in self.session
            assert self.session["user_id"] == str(identity[0].id)
            assert set(self.session) == {
                "user_id",
                "username",
                "display_name",
                "csrf_token",
                "expires_at",
                "grants",
            }
            self.headers = {**ORIGIN, "X-CSRF-Token": self.session["csrf_token"]}
            # Inspect the actual authenticated GET response too, without logging secrets.
            session = client.get("/api/v1/admin/session")
            assert session.status_code == 200 and session.json() == self.session

        def logout(self):
            if self.session:
                assert client.post("/api/v1/admin/logout", headers=self.headers).status_code == 204
                self.session = None

    def make_client(**kwargs):
        instance = CLIAdapter(client, {})
        adapters.append(instance)
        return instance

    monkeypatch.setattr(cli, "Client", make_client)
    monkeypatch.setattr(
        cli, "prompt_login", lambda c, _: c.login(identity[0].username, identity[1])
    )
    monkeypatch.setattr("builtins.input", lambda _: "APPLY")
    monkeypatch.setattr(sys, "argv", ["muj_update", "--draft", result["draft_id"]])
    persist = cli.persist

    def failed_save(target, document):
        if target.name.startswith("receipt-"):
            raise OSError("Injected disk failure; do not echo arbitrary OS details")
        persist(target, document)

    if fail_receipt:
        monkeypatch.setattr(cli, "persist", failed_save)
        with pytest.raises(SystemExit, match="Graph application succeeded.*receipt saving failed"):
            cli.main()
    else:
        cli.main()
    folder = tmp_path / "private/muj-updates" / result["draft_id"]
    applications = list(folder.glob("receipt-*.json"))
    assert len(applications) == (0 if fail_receipt else 1)
    db.expire_all()
    graph_audits = list(db.scalars(select(AuditEvent).where(AuditEvent.campus_id == CAMPUS_ID)))
    originals = [a for a in graph_audits if a.action.startswith("graph.")]
    assert len(originals) == 22 and all(a.actor_id == identity[0].id for a in originals)
    if applications:
        saved = json.loads(applications[0].read_text())
        assert saved["requested_by"] == str(identity[0].id)
        assert saved["receipt_type"] == "application" and saved["graph_writes_this_run"] == 1
        assert {a.request_id for a in originals} == {saved["audit_request_id"]}
    # Fresh real session on each invocation; no fake auth or bypass of graph service.
    monkeypatch.setattr(cli, "persist", persist)
    monkeypatch.setattr(
        sys, "argv", ["muj_update", "--draft", result["draft_id"], "--recover-receipt"]
    )
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("Recovery must never ask APPLY"))
    for _ in range(2):
        cli.main()
    assert sum(a.posts for a in adapters) == 1  # only original graph POST, no duplicate writes
    # Login again only to read the graph; prior CLI sessions really logged out.
    inspection = make_client()
    inspection.login(identity[0].username, identity[1])
    current = inspection.request("GET", path)
    assert current["revision_version"] == initial["revision_version"] + 1
    assert plan(current, UUID(result["draft_id"]))["state"] == "already_applied"
    assert [
        a.id for a in db.scalars(select(AuditEvent).where(AuditEvent.campus_id == CAMPUS_ID))
    ] == [a.id for a in graph_audits]
    inspection.logout()
    files = list(folder.glob("verification-*.json"))
    assert len(files) == 1  # repeated verification safely refreshes its own file, retains receipts
    verified = json.loads(files[0].read_text())
    assert verified["state"] == "already_applied"
    assert verified["revision_version"] == current["revision_version"]
    assert verified["verified_by"] == str(identity[0].id)
    assert verified["receipt_type"] == "state_verification"
    assert verified["graph_writes_this_run"] == 0
    assert "audit_request_id" not in verified and "requested_by" not in verified
    assert "not recovered" in verified["evidence_limit"]
    for file in folder.glob("*.json"):
        assert file.stat().st_mode & 0o777 == 0o600
        text = file.read_text()
        assert identity[1] not in text and "csrf_token" not in text
    output = capsys.readouterr().out
    assert "no graph writes" in output and identity[1] not in output
    get_settings.cache_clear()
