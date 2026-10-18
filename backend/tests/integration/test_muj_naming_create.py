"""Actual authenticated draft cloning, CSRF/CAS/audits and interrupted CLI recovery.

Synthetic Demo fixture with an E22-shaped naming proposal, not a published MUJ
copy. Only legacy immutable artifact transport is projected for this fixture.
"""

import hashlib
import json
import sys
from copy import deepcopy

import pytest
from sqlalchemy import select

from app.cli import muj_naming as cli
from app.cli import muj_naming_create as create
from app.cli.indoor_demo import DemoError
from app.core.config import get_settings
from app.core.portable import is_private_file
from app.models import ActiveRelease, Revision
from app.models.admin import AuditEvent
from app.services.publication import canonical, public_projection, snapshot
from tests.integration.test_admin import identity as owner_identity
from tests.integration.test_admin import sign_in

pytestmark = pytest.mark.integration


@pytest.fixture
def identity(db, bundle, seeded):
    return owner_identity.__wrapped__(db, bundle, seeded)


@pytest.mark.parametrize("failure", ["creation_response", "journal_save", "node_receipt"])
def test_create_cli_single_confirmation_normal_api_and_durable_interruption_recovery(
    client, db, bundle, seeded, identity, monkeypatch, tmp_path, capsys, failure
):
    campus = str(bundle.campus.id)
    monkeypatch.setattr(cli, "CAMPUS_ID", bundle.campus.id)
    monkeypatch.setattr(create, "CAMPUS_ID", bundle.campus.id)
    data = public_projection(snapshot(db, db.get(Revision, seeded.dataset_revision_id)))
    raw = canonical(data)
    release = client.get(f"/api/v1/campuses/{campus}/release").json()
    release["artifact_checksum"] = hashlib.sha256(raw).hexdigest()
    release["artifact_url"] = (
        f"/api/v1/campuses/{campus}/artifacts/{seeded.id}/{release['artifact_checksum']}.json"
    )
    place = next(p for p in bundle.places if p.code == "LIB")
    anchor = next(a for a in bundle.anchors if a.place_id == place.id)
    records = []
    for entity, identity_id, label in [
        ("places", place.id, "name"),
        ("nodes", anchor.node_id, "label"),
    ]:
        row = data[entity][str(identity_id)]
        records.append(
            {
                "entity": entity,
                "id": str(identity_id),
                "marker": "E22",
                "external_id": "osm-node-11664524407",
                "current_label": row[label],
                "proposed_name": "TMA Pai Auditorium entrance",
                "point": row["point"],
                "reason": "Synthetic E22-shaped test proposal, no campus identity evidence.",
                "confidence": "synthetic test only",
            }
        )
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps({"records": records, "source_sha256": "0" * 64}))
    monkeypatch.setattr(cli, "INVENTORY", inventory)
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    get_settings.cache_clear()
    folder = tmp_path / "storage/private/muj-naming"
    ledger = folder / "create-e22.json"
    lose = [True]
    writes = []

    class HTTP:
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
            if "/drafts" in path and method != "GET":
                writes.append((method, path, r.status_code))
            if not r.is_success:
                raise DemoError(f"API refused HTTP {r.status_code}")
            self.last_request_id = r.headers["X-Request-ID"]
            if (
                failure == "creation_response"
                and method == "POST"
                and path.endswith("/drafts")
                and lose[0]
            ):
                lose[0] = False
                raise DemoError("Injected lost creation response after server success")
            return r.json() if r.content else None

        def logout(self):
            if self.session:
                self.request("POST", "/api/v1/admin/logout")
                self.session = None

    monkeypatch.setattr(cli, "Client", HTTP)
    monkeypatch.setattr(
        cli, "prompt_login", lambda c, _: c.login(identity[0].username, identity[1])
    )

    def invoke():
        monkeypatch.setattr(sys, "argv", ["muj_naming", "--create-draft-and-apply"])
        cli.main()

    # Cancelling the one confirmation cannot create a draft or write a name.
    monkeypatch.setattr("builtins.input", lambda _: "CANCEL")
    invoke()
    assert not writes and not ledger.exists()
    confirmations = []

    def confirm(message):
        confirmations.append(message)
        return "CREATE AND APPLY E22"

    monkeypatch.setattr("builtins.input", confirm)
    real_create_persist = create.persist
    real_persist = cli.persist

    def save_creation(path, state):
        if (
            failure == "journal_save"
            and path.name == "create-e22.json"
            and state.get("draft")
            and lose[0]
        ):
            lose[0] = False
            raise OSError("Injected UUID-save failure after draft commit")
        real_create_persist(path, state)

    def save_receipt(path, state):
        if failure == "node_receipt" and path.name.startswith("create-e22-receipt-") and lose[0]:
            lose[0] = False
            raise OSError("Injected naming receipt failure")
        real_persist(path, state)

    monkeypatch.setattr(create, "persist", save_creation)
    monkeypatch.setattr(cli, "persist", save_receipt)
    original_release = db.get(ActiveRelease, (bundle.campus.id, "public")).release_id
    with pytest.raises(SystemExit):
        invoke()
    assert len(confirmations) == 1 and ledger.exists()
    intent = json.loads(ledger.read_text())
    assert intent["creation_key"] == create.creation_key(str(identity[0].id))

    def creations():
        return list(db.scalars(select(AuditEvent).where(AuditEvent.action == "draft.create")))

    assert len(creations()) == 1
    created_id = creations()[0].revision_id
    assert db.get(Revision, created_id).parent_id == seeded.dataset_revision_id
    # A normal retry with the same durable key never creates a second draft.
    invoke()
    assert len(creations()) == 1 and len(confirmations) == 2
    state = json.loads(ledger.read_text())
    assert state["draft"]["id"] == str(created_id)
    assert state["creation_audit"]["request_id"] == creations()[0].request_id
    assert state["creation_audit"]["id"] == str(creations()[0].id)
    assert state["last_verification"]["remaining"] == []
    sign_in(client, identity)
    graph = client.get(f"/api/v1/admin/campuses/{campus}/drafts/{created_id}/graph").json()
    old_graph = snapshot(db, db.get(Revision, seeded.dataset_revision_id))
    current = snapshot(db, db.get(Revision, created_id))
    for entity in current:
        if entity not in {"places", "nodes"}:
            assert current[entity] == old_graph[entity]
    for entity, label in [("nodes", "label"), ("places", "name")]:
        expected = deepcopy(old_graph[entity])
        target = next(r["id"] for r in records if r["entity"] == entity)
        expected[target][label] = "TMA Pai Auditorium entrance"
        if entity == "places":
            assert "tma pai auditorium entrance" in current[entity][target]["search_text"]
            expected[target]["search_text"] = current[entity][target]["search_text"]
        assert current[entity] == expected
    edit = graph["revision_version"]
    count = len(writes)
    invoke()
    invoke()  # completed retries must not even POST draft creation again
    assert len(writes) == count and len(confirmations) == 2
    # Simulate external loss of the LOCAL test journal. The key is independent
    # of that file, so even this recovery cannot create a duplicate server draft.
    ledger.unlink()
    invoke()
    assert len(confirmations) == 3
    recovered = json.loads(ledger.read_text())
    assert recovered["draft"]["id"] == str(created_id)
    assert recovered["creation_audit"]["request_id"] == creations()[0].request_id
    assert len(creations()) == 1
    sign_in(client, identity)
    assert (
        client.get(f"/api/v1/admin/campuses/{campus}/drafts/{created_id}/graph").json()[
            "revision_version"
        ]
        == edit
    )
    assert db.get(ActiveRelease, (bundle.campus.id, "public")).release_id == original_release
    assert not list(db.scalars(select(AuditEvent).where(AuditEvent.action.like("publication.%"))))
    for path in folder.glob("*.json"):
        text = path.read_text()
        assert identity[1] not in text and "csrf_token" not in text
        assert is_private_file(path)
    out = capsys.readouterr().out
    assert identity[1] not in out and str(created_id) in out and "remaining 0" in out
    get_settings.cache_clear()
