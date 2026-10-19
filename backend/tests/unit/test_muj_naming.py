import json
from copy import deepcopy

import pytest

from app.cli.indoor_demo import DemoError
from app.cli.muj_naming import preflight, supported_changes
from app.cli.muj_publication import pinned_graph
from app.routing.instructions import outdoor_instruction
from app.routing.mixed import compute
from app.services.muj_naming import INVENTORY, ROOT, build_inventory, draw_map
from app.services.muj_setup import CAMPUS_ID
from tests.unit.test_connection_costs import outdoor


def test_inventory_pin_explicit_building_membership_and_unresolved_identities():
    inventory = json.loads(INVENTORY.read_bytes())
    assert len(inventory["records"]) == 423
    changes = supported_changes()
    assert len(changes) == 2 and {r["entity"] for r in changes} == {"nodes", "places"}
    assert {r["external_id"] for r in changes} == {"osm-node-11664524407"}
    assert {r["proposed_name"] for r in changes} == {"TMA Pai Auditorium entrance"}
    entrances = {
        r["marker"]: r for r in inventory["records"] if r["entity"] == "places" and r["marker"]
    }
    assert len(entrances) == 23
    assert sum(r["proposed_name"] is None for r in entrances.values()) == 17
    assert entrances["E02"]["proposed_name"] is None
    assert entrances["E05"]["proposed_name"] is None
    assert entrances["E22"]["existing_building_id"] is None  # no association mutation
    for marker in ("E08", "E16", "E23"):
        assert entrances[marker]["proposed_name"] is None
    raw = ROOT / "data/raw/muj/source.osm"
    if raw.exists():
        assert build_inventory(raw.read_bytes()) == inventory
        assert draw_map(raw.read_bytes(), inventory, (75.563, 26.841, 75.566, 26.844), "Test <map>")
    with pytest.raises(ValueError, match="checksum"):
        build_inventory(b"<osm/>")
    encoded = json.dumps(inventory)
    for key in ('"uid"', '"user"', '"changeset"', '"created_by"'):
        assert key not in encoded


@pytest.mark.parametrize(
    "kind,text",
    [
        ("walkway", "Continue along the walkway."),
        ("stairs", "Take the stairs."),
        ("ramp", "Follow the ramp."),
    ],
)
def test_only_exact_technical_outdoor_labels_use_neutral_wording(kind, text):
    assert outdoor_instruction(kind, "OSM junction 10828149259") == text
    for label in (
        "University Entrance",
        "North gate",
        "OSM junction 123 - owner label",
        "c1",
        "Main Gate",
    ):
        assert outdoor_instruction(kind, label).endswith(f"to {label}.")


def test_mixed_metric_traversal_fastest_and_step_free_keep_same_path_and_arrival():
    p = outdoor()
    for profile, mode in [
        ("shortest", "metric"),
        ("shortest", "directions_only"),
        ("fastest", "metric"),
        ("step_free", "metric"),
    ]:
        before = compute(p, "a", "b", profile, mode)
        q = deepcopy(p)
        q["nodes"]["y"]["label"] = "OSM junction 123"
        after = compute(q, "a", "b", profile, mode)
        assert after["segments"][0]["instruction"] == "Continue along the walkway."
        before["segments"][0]["instruction"] = after["segments"][0]["instruction"]
        assert before == after
        assert after["arrival_instruction"] == "Arrive at B."


class FixtureClient:
    def __init__(self):
        from hashlib import sha256

        self.data = {**pinned_graph(), "campus": {"id": str(CAMPUS_ID)}, "audience": "public"}
        self.raw = json.dumps(self.data, sort_keys=True).encode()
        sha = sha256(self.raw).hexdigest()
        self.release = {
            "id": "00000000-0000-4000-8000-000000000001",
            "campus_id": str(CAMPUS_ID),
            "artifact_checksum": sha,
        }
        self.release["artifact_url"] = (
            f"/api/v1/campuses/{CAMPUS_ID}/artifacts/{self.release['id']}/{sha}.json"
        )
        self.graph = {**deepcopy(self.data), "revision_version": 42}
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append(method)
        assert method == "GET"
        if path.endswith("/release"):
            return deepcopy(self.release)
        if "/artifacts/" in path:
            return self.raw
        if path.endswith("/graph"):
            return deepcopy(self.graph)
        raise AssertionError(path)


def test_read_only_preflight_binds_real_published_checksum_and_exact_two_fields():
    client = FixtureClient()
    report = preflight(client, "00000000-0000-4000-8000-000000000002")
    assert not report["blockers"] and report["draft_version"] == 42
    assert len(report["changes"]) == 2
    for c in report["changes"]:
        assert {k for k in c["after"] if c["before"][k] != c["after"][k]} == {
            "name" if c["entity"] == "places" else "label"
        }
    assert set(client.calls) == {"GET"}


@pytest.mark.parametrize("edit", ["label", "point", "anchor"])
def test_preflight_preserves_conflicting_owner_changes(edit):
    client = FixtureClient()
    c = next(r for r in supported_changes() if r["entity"] == "nodes")
    if edit == "label":
        client.graph["nodes"][c["id"]]["label"] = "Owner knows this door"
    elif edit == "point":
        client.graph["nodes"][c["id"]]["point"]["coordinates"][0] += 0.0001
    else:
        client.graph["anchors"] = {}
    report = preflight(client, "00000000-0000-4000-8000-000000000002")
    assert report["blockers"] and set(client.calls) == {"GET"}


def test_artifact_integrity_and_safe_url_guard():
    client = FixtureClient()
    client.raw = b"{}"
    with pytest.raises(DemoError, match="checksum"):
        preflight(client)
    client = FixtureClient()
    client.release["artifact_url"] = "http://example.test/secret"
    with pytest.raises(DemoError, match="URL"):
        preflight(client)


def test_lost_success_response_reconciles_only_remaining_names_and_never_fabricates_receipt():
    from app.cli.muj_naming import apply_reviewed

    class Transport(FixtureClient):
        def __init__(self):
            super().__init__()
            self.writes = 0
            self.lose = True

        def request(self, method, path, payload=None, *, headers=None, **kwargs):
            if method == "GET":
                return super().request(method, path, **kwargs)
            assert headers == {"If-Match": f'"{self.graph["revision_version"]}"'}
            if method == "POST":
                change = payload["changes"][0]
                self.graph["nodes"][change["id"]].update(change["data"])
            else:
                identity = path.split("/")[-1]
                self.graph["places"][identity].update(payload["data"])
            self.graph["revision_version"] += 1
            self.writes += 1
            self.last_request_id = f"actual-response-{self.writes}"
            if self.lose:
                self.lose = False
                raise DemoError("Response lost after committed write")
            return {"revision_version": self.graph["revision_version"]}

    transport = Transport()
    draft = "00000000-0000-4000-8000-000000000002"
    receipts = []
    with pytest.raises(DemoError, match="lost"):
        apply_reviewed(transport, preflight(transport, draft), receipts.append)
    assert transport.writes == 1 and not receipts
    remaining = preflight(transport, draft)
    assert len(remaining["changes"]) == 1
    final = apply_reviewed(transport, remaining, receipts.append)
    assert not final["changes"] and transport.writes == 2 and len(receipts) == 1
    assert receipts[0]["audit_request_id"] == "actual-response-2"
    apply_reviewed(transport, final, receipts.append)
    assert transport.writes == 2 and len(receipts) == 1
