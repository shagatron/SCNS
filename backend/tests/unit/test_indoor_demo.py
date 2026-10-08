import json
from copy import deepcopy
from uuid import uuid4

import pytest

from app.cli.indoor_demo import (
    Client,
    DemoError,
    Setup,
    journal,
    matching_records,
    persist,
    prompt_login,
    remap,
)


def test_fixture_ids_namespace_and_bindings_preserve_null_unknowns():
    old, namespace, floor = map(str, [uuid4(), uuid4(), uuid4()])
    value = {
        old: {
            "node_id": old,
            "floor_id": "$GROUND",
            "width_m": None,
            "accessibility_status": "unknown",
        }
    }
    mapped = remap(value, namespace, {"GROUND": floor})
    identity = next(iter(mapped))
    assert identity != old and mapped[identity]["node_id"] == identity
    assert mapped[identity]["floor_id"] == floor and mapped[identity]["width_m"] is None
    assert mapped == remap(value, namespace, {"GROUND": floor})
    assert remap(value, str(uuid4()), {"GROUND": floor}) != mapped
    assert old in value


def test_secure_prompt_refuses_non_tty_and_echoing_fallback(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(DemoError, match="Secure terminal"):
        prompt_login(Client(), "owner")
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "owner")

    def unsafe(_):
        import getpass
        import warnings

        warnings.warn("fallback", getpass.GetPassWarning, stacklevel=2)
        pytest.fail("Echoing fallback must never continue")

    monkeypatch.setattr("getpass.getpass", unsafe)
    with pytest.raises(DemoError, match="echoed fallback"):
        prompt_login(Client(), "owner")


def test_remote_credential_target_refused():
    with pytest.raises(DemoError, match="local Compose"):
        Client("https://example.com")


def test_journal_resume_lock_owner_and_fixture_guards(tmp_path):
    campus, owner = str(uuid4()), str(uuid4())
    with journal(tmp_path, campus, owner) as (path, state):
        state["draft"] = str(uuid4())
        persist(path, state)
        saved = deepcopy(state)
        assert path.stat().st_mode & 0o777 == 0o600
        with pytest.raises(DemoError, match="Another demo"):
            with journal(tmp_path, campus, owner):
                pass
    with journal(tmp_path, campus, owner) as (_, state):
        assert state == saved
    with pytest.raises(DemoError, match="owner/fixtures"):
        with journal(tmp_path, campus, str(uuid4())):
            pass
    path.write_text("invalid")
    with pytest.raises(DemoError, match="Invalid journal"):
        with journal(tmp_path, campus, owner):
            pass
    assert path.read_text() == "invalid"


def test_partial_or_modified_records_never_upsert():
    data = {"nodes": {"a": {"x": 1}, "b": {"x": 2}}}
    assert matching_records(data, {"nodes": {}}) is None
    assert matching_records(data, {"nodes": {"a": {"x": 1}, "b": {"x": 2, "derived": 42}}})
    for actual in ({"nodes": {"a": {"x": 1}}}, {"nodes": {"a": {"x": 3}, "b": {"x": 2}}}):
        with pytest.raises(DemoError, match="partial"):
            matching_records(data, actual)


def test_interrupted_cas_step_reconciles_without_another_write(tmp_path):
    state = {"campus": str(uuid4()), "edit_version": 4, "pending": "trace", "steps": {}}
    setup = Setup(None, None, tmp_path / "progress.json", state, None)
    setup.floors = lambda: {"edit_version": 5, "status": "draft", "truncated": False}

    def never():
        pytest.fail("Lost successful response must not cause a second write")

    assert setup.step("trace", lambda: True, never)
    assert state["edit_version"] == 5 and "pending" not in state
    assert json.loads(setup.path.read_text())["steps"]["trace"]
    setup.floors = lambda: {"edit_version": 6, "status": "draft", "truncated": False}
    with pytest.raises(DemoError, match="outside recorded"):
        setup.guard()


def test_pending_step_with_unrelated_concurrent_write_refuses_retry(tmp_path):
    state = {"campus": str(uuid4()), "edit_version": 4, "pending": "trace", "steps": {}}
    setup = Setup(None, None, tmp_path / "progress.json", state, None)
    setup.floors = lambda: {"edit_version": 5, "status": "draft", "truncated": False}
    with pytest.raises(DemoError, match="Cannot reconcile"):
        setup.step("trace", lambda: None, lambda: pytest.fail("must not write"))
    assert state["edit_version"] == 4 and state["steps"] == {}
