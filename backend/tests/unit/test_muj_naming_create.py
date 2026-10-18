import json
from copy import deepcopy
from uuid import uuid4

import pytest

from app.cli import muj_naming_create as cli
from app.cli.indoor_demo import DemoError, persist
from app.core.portable import lock_file
from tests.unit.test_muj_naming import FixtureClient

OWNER = "00000000-0000-4000-8000-000000000007"


class CreationClient(FixtureClient):
    def __init__(self):
        super().__init__()
        self.release["dataset_revision_id"] = str(uuid4())
        self.created = []
        self.events = []
        self.omit_audit = False
        self.wrong_parent = False

    def request(self, method, path, payload=None, *, headers=None, **kwargs):
        if path.endswith("/audit"):
            return deepcopy(self.events)
        if method == "POST" and path.endswith("/drafts"):
            assert headers == {"Idempotency-Key": cli.creation_key(OWNER)}
            if not self.created:
                self.created.append(
                    {
                        "id": str(uuid4()),
                        "version": 4,
                        "edit_version": 1,
                        "campus_id": str(cli.CAMPUS_ID),
                        "status": "draft",
                    }
                )
                if not self.omit_audit:
                    self.events.append(
                        {
                            "action": "draft.create",
                            "actor_id": OWNER,
                            "revision_id": self.created[0]["id"],
                            "campus_id": str(cli.CAMPUS_ID),
                            "after": {
                                "idempotency_key": cli.creation_key(OWNER),
                                "parent_id": str(uuid4())
                                if self.wrong_parent
                                else self.release["dataset_revision_id"],
                            },
                            "request_id": "real-audit-request",
                            "id": "real-event",
                        }
                    )
            return deepcopy(self.created[0])
        return super().request(method, path, **kwargs)


def test_key_is_stable_without_a_local_journal_and_bound_to_original_owner():
    assert cli.creation_key(OWNER) == cli.creation_key(OWNER)
    assert cli.creation_key(OWNER) != cli.creation_key(str(uuid4()))
    assert len(cli.creation_key(OWNER)) <= 80


@pytest.mark.parametrize("problem", ["missing_audit", "wrong_parent"])
def test_uncertain_parentage_stops_with_durable_uuid_not_another_draft(
    tmp_path, monkeypatch, problem
):
    client = CreationClient()
    client.omit_audit = problem == "missing_audit"
    client.wrong_parent = problem == "wrong_parent"
    monkeypatch.setattr("builtins.input", lambda _: "CREATE AND APPLY E22")
    with pytest.raises(DemoError, match="audit|parent"):
        cli.run(client, OWNER, tmp_path, lambda _: pytest.fail("No naming write permitted"))
    saved = json.loads((tmp_path / "create-e22.json").read_text())
    assert saved["draft"]["id"] == client.created[0]["id"]
    with pytest.raises(DemoError):
        cli.run(client, OWNER, tmp_path, lambda _: pytest.fail("No naming write"))
    assert len(client.created) == 1


def test_stale_release_at_confirmation_does_not_create_anything(tmp_path, monkeypatch):
    client = CreationClient()

    def confirm(_):
        client.release["id"] = str(uuid4())
        return "CREATE AND APPLY E22"

    monkeypatch.setattr("builtins.input", confirm)
    with pytest.raises(DemoError):
        cli.run(client, OWNER, tmp_path, lambda _: None)
    assert not client.created and not (tmp_path / "create-e22.json").exists()


def test_invalid_or_other_owner_journal_and_live_lock_preserve_saved_state(tmp_path, monkeypatch):
    path = tmp_path / "create-e22.json"
    path.write_text("{broken")
    with pytest.raises(DemoError, match="invalid"):
        cli.read_state(path, OWNER)
    assert path.read_text() == "{broken"
    state = {
        "format": cli.FORMAT,
        "owner": str(uuid4()),
        "campus_id": str(cli.CAMPUS_ID),
        "creation_key": cli.creation_key(OWNER),
        "release": {"id": str(uuid4())},
    }
    persist(path, state)
    with pytest.raises(DemoError):
        cli.read_state(path, OWNER)
    with (tmp_path / "create-e22.lock").open("a") as lock:
        lock_file(lock)
        with pytest.raises(DemoError, match="Another E22"):
            cli.run(CreationClient(), OWNER, tmp_path, lambda _: None)
    assert json.loads(path.read_text()) == state


def test_inventory_cannot_expand_this_workflow_to_another_entrance(tmp_path, monkeypatch):
    changes = deepcopy(cli.supported_changes())
    changes[0]["external_id"] = "osm-node-10828149259"
    monkeypatch.setattr(cli, "supported_changes", lambda: changes)
    with pytest.raises(DemoError, match="allowlist"):
        cli.run(CreationClient(), OWNER, tmp_path, lambda _: None)
    assert not (tmp_path / "create-e22.json").exists()
