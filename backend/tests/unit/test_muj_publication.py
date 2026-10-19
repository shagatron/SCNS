from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.cli import muj_publication as cli
from app.cli.indoor_demo import DemoError
from app.services.muj_update import ROOT2, graph_records


def graph():
    return {**deepcopy(cli.pinned_graph()), "revision_version": 7}


def test_source_pair_topology_is_unresolved_and_unanchored_not_physical_separation():
    g = graph()
    _, before = graph_records(ROOT2)
    assert set(g["nodes"]) == set(before["nodes"])
    standard = cli.topology(g, "shortest")
    assert len(standard["components"]) == 29
    assert len(cli.topology(g, "step_free")["components"]) == 295
    pairs = cli.near_pairs(g, standard)
    assert all(p["manual_assessment_required"] for p in pairs)
    assert all(len(p["component_anchors"]) == 2 for p in pairs)
    assert all("does not prove" in p["assessment"] for p in pairs)
    for p in pairs:
        assert all(len(c) == 2 for c in p["components"])
        assert {e["accessibility_status"] for e in p["incident_edges"].values()} == {"unknown"}
    assert g == graph()  # read-only: no proximity merge or geometry change


def test_unknown_warning_and_changed_pinned_graph_are_blockers():
    g = graph()
    g["nodes"][cli.PAIRS[0][0]]["label"] = "Owner edit must survive"
    draft = uuid4()
    packet = {
        "sources": {},
        "checksum": "abc",
        "edit_version": 7,
        "status": "draft",
        "submissions": [],
    }
    run = {
        "id": str(uuid4()),
        "checksum": "abc",
        "edit_version": 7,
        "evidence": [],
        "report": {
            "errors": 0,
            "diagnostics": [
                {
                    "id": "new-warning",
                    "severity": "warning",
                    "code": "unexpected_new_finding",
                    "ids": [],
                    "entity": "nodes",
                    "message": "Needs human investigation",
                }
            ],
        },
    }
    result = cli.prepare(packet, g, run, [], None, draft)
    assert "new-warning" not in result["proposed_reasons"]
    assert len(result["unjustified_findings"]) == 1
    assert any("nodes differ" in b for b in result["blockers"])
    assert any("no justified template" in b for b in result["blockers"])
    assert g["nodes"][cli.PAIRS[0][0]]["label"] == "Owner edit must survive"


def test_collect_detects_changes_between_read_only_requests():
    draft = uuid4()
    packet = {
        "id": str(draft),
        "edit_version": 7,
        "checksum": "abc",
        "status": "draft",
        "submissions": [],
        "validations": [],
    }

    class Client:
        reads = 0

        def request(self, method, path):
            assert method == "GET"
            if path.endswith("/graph"):
                return {"revision_version": 7}
            self.reads += 1
            return {**packet, "edit_version": 8 if self.reads > 1 else 7}

    with pytest.raises(DemoError, match="changed during preflight"):
        cli.collect(Client(), draft)


def test_cli_invalid_session_never_reads_or_writes_dataset(tmp_path, monkeypatch):
    import sys

    class Client:
        session = {"user": {"id": str(uuid4())}}

        def request(self, *a, **k):
            pytest.fail("Malformed identity must stop before dataset access")

        def logout(self):
            pass

    monkeypatch.setattr(cli, "Client", lambda **k: Client())
    monkeypatch.setattr(cli, "prompt_login", lambda *a: None)
    monkeypatch.setattr(sys, "argv", ["muj_publication", "--draft", str(uuid4())])
    with pytest.raises(SystemExit, match="session"):
        cli.main()


def test_preflight_preserves_private_owner_reasons_and_exposes_stale_ids(tmp_path, monkeypatch):
    user, draft, validation = map(str, [uuid4(), uuid4(), uuid4()])
    report = {
        "draft_id": draft,
        "version": 9,
        "checksum": "abc",
        "validation_id": validation,
        "blockers": [],
        "proposed_reasons": {"current": "Specific proposed limitation."},
        "warning_counts": {},
        "status": "draft",
        "scope": cli.NOTES,
        "sources": {},
        "imports": [],
        "near_duplicate_pairs": [],
        "unjustified_findings": [],
        "existing_submissions": [],
    }
    monkeypatch.setattr(cli, "collect", lambda *a: ({"status": "draft"}, {}, {}, [], None))
    monkeypatch.setattr(cli, "prepare", lambda *a: deepcopy(report))
    monkeypatch.setattr(cli, "get_settings", lambda: SimpleNamespace(storage_root=tmp_path))
    c = SimpleNamespace(session={"user_id": user})
    folder, _ = cli.preflight(c, draft)
    proposed = folder / "proposal.json"
    payload = {
        "validation_id": validation,
        "acknowledgements": {
            "current": "Owner independently wrote this specific reason.",
            "stale": "Keep this text for reconciliation.",
        },
    }
    cli.persist(proposed, payload)
    _, updated = cli.preflight(c, draft)
    assert __import__("json").loads(proposed.read_text()) == payload
    assert any("retained untouched" in b for b in updated["blockers"])
    assert proposed.stat().st_mode & 0o777 == 0o600
