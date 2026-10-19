from copy import deepcopy
from uuid import uuid4

import pytest

from app.cli import muj_naming_review as cli
from app.cli import muj_publication as original
from app.cli.indoor_demo import DemoError
from app.cli.muj_naming import supported_changes
from app.services.publication import TABLES, checksum


def snapshots():
    parent = {layer: {} for layer in TABLES}
    parent["campus"] = {"id": str(cli.CAMPUS_ID)}
    baseline = original.pinned_graph()
    for entity, rows in baseline.items():
        parent[entity] = deepcopy(rows)
    e22 = next(r for r in supported_changes() if r["entity"] == "places")
    parent["places"][e22["id"]].update(aliases=[], search_text="old derived index")
    diff = []
    for row in supported_changes():
        entity, identity = row["entity"], row["id"]
        before = deepcopy(parent[entity][identity])
        after = deepcopy(before)
        after["name" if entity == "places" else "label"] = row["proposed_name"]
        if entity == "places":
            after["search_text"] = cli.normalize(
                " ".join([after["code"], after["name"], after["kind"], *after["aliases"]])
            )
        diff.append({"entity": entity, "id": identity, "before": before, "after": after})
    current = deepcopy(parent)
    for d in diff:
        current[d["entity"]][d["id"]] = d["after"]
    return parent, {"diff": diff, "checksum": checksum(current), "sources": {}}, current


def findings():
    e22 = next(r for r in supported_changes() if r["entity"] == "places")
    rows = []
    for n in range(143):
        d = {
            "code": "unmapped_entrance",
            "entity": "places",
            "ids": [str(n)],
            "message": f"Synthetic unchanged finding {n}",
            "severity": "warning",
        }
        d["id"] = checksum(d)[:24]
        rows.append(d)
    for profile in ("shortest", "step_free"):
        d = {
            "code": "connectivity_" + profile,
            "entity": "places",
            "ids": [e22["id"]],
            "message": f"{e22['current_label']}: add an eligible entrance/path or document legitimate isolation ({profile}).",
            "severity": "warning",
        }
        d["id"] = checksum(d)[:24]
        rows.append(d)
    for n in range(3):
        d = {
            "code": "import_provenance",
            "entity": "imports",
            "ids": [str(uuid4())],
            "message": f"Synthetic pinned import {n}",
            "severity": "warning",
        }
        d["id"] = checksum(d)[:24]
        rows.append(d)
    current = []
    for d in rows:
        if d["code"] == "import_provenance":
            continue
        new = deepcopy(d)
        if new["code"].startswith("connectivity_"):
            new["message"] = new["message"].replace(e22["current_label"], e22["proposed_name"])
            new["id"] = checksum({k: v for k, v in new.items() if k != "id"})[:24]
        current.append(new)
    reasons = {
        d[
            "id"
        ]: f"Previously reviewed limited OSM ambiguity for {e22['current_label']}; no physical isolation or accessibility approval asserted."
        for d in rows
    }
    return rows, current, reasons


def test_full_diff_checksum_allows_exact_names_and_derived_index_only():
    parent, packet, expected = snapshots()
    original_parent = deepcopy(parent)
    assert cli.verify_diff(parent, packet) == expected
    assert parent == original_parent


@pytest.mark.parametrize("change", ["geometry", "sources", "extra", "index", "hidden_checksum"])
def test_full_diff_refuses_owner_or_source_changes_without_altering_input(change):
    parent, packet, _ = snapshots()
    if change == "geometry":
        packet["diff"][0]["after"]["point"]["coordinates"][0] += 0.0001
    elif change == "sources":
        packet["sources"] = {"unexpected": {"approved_by": "changed"}}
    elif change == "extra":
        packet["diff"].append({"entity": "edges", "id": "owner", "before": None, "after": {}})
    elif change == "index":
        next(d for d in packet["diff"] if d["entity"] == "places")["after"]["search_text"] = (
            "stale index"
        )
    else:
        packet["checksum"] = "wrong"
    saved = deepcopy(packet)
    with pytest.raises(DemoError):
        cli.verify_diff(parent, packet)
    assert packet == saved


def test_warning_ids_follow_only_e22_wording_with_actual_reported_transitions():
    old, current, reasons = findings()
    transitions, removed, proposed, unjustified = cli.compare_findings(old, current, reasons)
    assert (
        len(transitions) == 145 and len(removed) == 3 and len(proposed) == 145 and not unjustified
    )
    changed = {t["old_id"]: t["current_id"] for t in transitions if t["changed_label"]}
    assert changed == {
        "2e91f6527197dcf605c6bd1c": "31e82f537d40675eb7d195da",
        "afc1f1a73eadcdbf2e59b416": "814311f5e36600b827d98bd1",
    }
    for t in transitions:
        if not t["changed_label"]:
            assert proposed[t["current_id"]] == reasons[t["old_id"]]
        else:
            assert (
                "TMA Pai Auditorium entrance" in proposed[t["current_id"]]
                and "Mapped entrance 11664524407" not in proposed[t["current_id"]]
            )


@pytest.mark.parametrize("change", ["message", "missing", "extra", "reference"])
def test_unexpected_findings_are_not_blanket_mapped(change):
    old, current, reasons = findings()
    if change == "message":
        current[0]["message"] = "Different underlying problem"
    elif change == "missing":
        current.pop()
    elif change == "extra":
        current.append({**current[0], "id": "new"})
    else:
        current[0]["ids"] = ["different place"]
    with pytest.raises(DemoError, match="Unexpected"):
        cli.compare_findings(old, current, reasons)


def test_missing_reason_is_flagged_not_invented_and_original_pin_rejects_clone():
    old, current, reasons = findings()
    reasons.pop(old[0]["id"])
    _, _, proposed, missing = cli.compare_findings(old, current, reasons)
    assert old[0]["id"] not in proposed and missing
    parent, packet, clone = snapshots()
    graph = {**clone, "revision_version": 3}
    result = original.prepare(
        {
            "sources": {},
            "checksum": packet["checksum"],
            "edit_version": 3,
            "status": "draft",
            "submissions": [],
        },
        graph,
        None,
        [],
        None,
        uuid4(),
    )
    assert any("nodes differ" in b for b in result["blockers"])
    assert any("places differ" in b for b in result["blockers"])


def test_shared_client_only_permits_bounded_read_only_audit_query():
    from app.cli.indoor_demo import Client

    calls = []

    class Response:
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def read(self):
            return b"[]"

    class Opener:
        def open(self, request, timeout):
            calls.append(request.full_url)
            return Response()

    client = Client()
    client.opener = Opener()
    path = f"/api/v1/admin/campuses/{cli.CAMPUS_ID}/audit"
    assert client.request("GET", path, query={"offset": 50}) == []
    assert calls == [client.url + path + "?offset=50"]
    for method, target, query in [
        ("POST", path, {"offset": 0}),
        ("GET", path, {"password": "never sent"}),
        ("GET", path, {"offset": -1}),
        ("GET", path, {"offset": True}),
        ("GET", path, {"offset": 100001}),
        ("GET", "/api/v1/admin/session", {"offset": 0}),
    ]:
        with pytest.raises(DemoError, match="read-only audit"):
            client.request(method, target, query=query)
    assert len(calls) == 1


def test_new_cli_dispatch_is_read_only_and_disallows_actions(monkeypatch):
    import sys

    draft, validation = uuid4(), uuid4()
    calls = []

    class Client:
        session = {"user_id": str(uuid4())}

        def logout(self):
            calls.append("logout")

    monkeypatch.setattr(original, "Client", lambda **kwargs: Client())
    monkeypatch.setattr(original, "prompt_login", lambda *args: None)
    monkeypatch.setattr(cli, "preflight", lambda c, d, v: calls.append((d, v)))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "muj_publication",
            "--draft",
            str(draft),
            "--validation",
            str(validation),
            "--naming-clone",
        ],
    )
    original.main()
    assert calls == [(draft, validation), "logout"]
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "muj_publication",
            "--draft",
            str(draft),
            "--naming-clone",
            "--action",
            "approve",
            "--bundle",
            "ignored",
        ],
    )
    with pytest.raises(SystemExit) as error:
        original.main()
    assert error.value.code == 2 and len(calls) == 2


def test_original_action_path_explicitly_refuses_copied_clone_bundle(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace

    folder = tmp_path / "private/muj-publication/bundle"
    folder.mkdir(parents=True)
    (folder / "report.json").write_text(json.dumps({"scope_type": "e22-naming-clone"}))
    monkeypatch.setattr(original, "get_settings", lambda: SimpleNamespace(storage_root=tmp_path))
    with pytest.raises(DemoError, match="Original pinned action path refuses"):
        original.perform(SimpleNamespace(), folder, "submit")


@pytest.mark.parametrize("field", ["checksum", "edit_version"])
def test_selected_validation_must_match_current_content_and_version(field):
    _, diagnostics, _ = findings()
    run = {
        "id": str(uuid4()),
        "checksum": "current",
        "edit_version": 3,
        "report": {"errors": 0, "warnings": len(diagnostics), "diagnostics": diagnostics},
    }
    packet = {"checksum": "current", "edit_version": 3, "status": "draft", "validations": [run]}
    run[field] = "stale" if field == "checksum" else 2
    with pytest.raises(DemoError, match="stale"):
        cli.select_run(packet, run["id"])
