from copy import deepcopy

import pytest

from app.core.errors import DomainError
from app.routing.dijkstra import Arc, shortest_path
from app.routing.mixed import compute
from app.services.connections import route_evidence_requirements


def outdoor():
    return {
        "places": {"a": {"name": "A"}, "b": {"name": "B"}},
        "nodes": {"x": {"label": "X"}, "y": {"label": "Y"}},
        "anchors": {
            i: {
                "id": i,
                "node_id": node,
                "place_id": place,
                "is_open": True,
                "accessibility_status": "verified_step_free",
            }
            for i, node, place in (("aa", "x", "a"), ("ab", "y", "b"))
        },
        "edges": {
            "e": {
                "id": "e",
                "from_node_id": "x",
                "to_node_id": "y",
                "kind": "walkway",
                "distance_m": 256.884,
                "distance_status": "estimated",
                "is_open": True,
                "accessibility_status": "verified_step_free",
                "geometry": {"type": "LineString", "coordinates": [[0, 0], [0.001, 0.001]]},
            }
        },
    }


def test_legacy_estimated_geodesic_edge_remains_routable_in_mixed_graph():
    p = outdoor()
    r = compute(p, "a", "b")
    assert r["distance_m"] == 256.88 and r["segments"][0]["geometry"]
    assert compute(p, "a", "b", "fastest")["cost_units"] == "seconds"
    assert compute(p, "a", "b", "step_free")["distance_m"] == 256.88
    assert compute(p, "a", "b", mode="directions_only")["cost_units"] == "traversals"


def test_unknown_stair_time_is_not_a_fastest_candidate_or_step_free():
    p = outdoor()
    p["edges"]["e"]["kind"] = "stairs"
    assert compute(p, "a", "b")["estimated_duration_s"] is None
    for profile in ("step_free", "fastest"):
        with pytest.raises(DomainError):
            compute(p, "a", "b", profile)
    with pytest.raises(DomainError):
        compute(p, "a", "b", "fastest", "directions_only")


def test_multiple_doors_and_transition_priorities_only_break_equal_cost_ties():
    arcs = [Arc("z", "s", "t", 1, priority=0), Arc("a", "s", "t", 1, priority=8)]
    for entries in (arcs, list(reversed(arcs))):
        assert shortest_path(entries, {"s"}, {"t"}).edges == ["z"]
    arcs[0] = Arc("z", "s", "t", 2, priority=0)
    assert shortest_path(arcs, {"s"}, {"t"}).edges == ["a"]
    choices = [Arc("a", "one", "goal", 2), Arc("b", "two", "goal", 2)]
    assert (
        shortest_path(
            choices, {"one", "two"}, {"goal"}, source_priorities={"one": 8, "two": 0}
        ).nodes[0]
        == "two"
    )


def test_enabled_floor_cannot_be_published_with_only_negative_acceptance_cases():
    full = {
        "floor_routing": {"f": {"floor_id": "f", "enabled": True, "visibility": "public"}},
        "indoor_rooms": {r: {"floor_id": "f", "visibility": "public"} for r in ("a", "b")},
    }
    cases = [
        {"source": "a", "target": "b", "profile": p, "passed": True, "actual": {"found": False}}
        for p in ("shortest", "step_free")
    ]
    assert route_evidence_requirements(full, cases)
    positive = deepcopy(cases)
    positive[0]["actual"]["found"] = True
    assert route_evidence_requirements(full, positive) == []
