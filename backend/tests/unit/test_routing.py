import math
import random

import pytest

from app.routing.dijkstra import Arc, shortest_path


def arc(a, b, distance, **kw):
    return Arc(f"{a}-{b}", a, b, distance, **kw)


def test_weighted_route_beats_fewer_hops_and_reconstructs_edges():
    graph = [
        arc("a", "d", 200),
        arc("a", "b", 50),
        arc("b", "c", 20),
        arc("c", "d", 70),
        arc("b", "a", 50),
    ]
    path = shortest_path(graph, {"a"}, {"d"})
    assert path.distance_m == 140
    assert path.nodes == ["a", "b", "c", "d"]
    assert path.edges == ["a-b", "b-c", "c-d"]


def test_directed_disconnected_same_node_and_multiple_anchors():
    graph = [arc("a", "b", 7), arc("c", "b", 3)]
    assert shortest_path(graph, {"b"}, {"a"}) is None
    assert shortest_path(graph, {"a"}, {"isolated"}) is None
    assert shortest_path(graph, {"a"}, {"a"}).distance_m == 0
    path = shortest_path(graph, {"a", "c"}, {"b", "unreachable-door"})
    assert path.nodes == ["c", "b"]
    assert path.distance_m == 3


def test_hard_constraints_and_closure_overlay():
    graph = [
        arc("a", "b", 1, kind="stairs", accessibility="not_step_free"),
        arc("a", "c", 5, accessibility="verified_step_free"),
        arc("c", "b", 5, accessibility="verified_step_free"),
        arc("a", "d", 0.5, visibility="restricted"),
        arc("d", "b", 0.5),
        arc("a", "e", 0.2, is_open=False),
        arc("e", "b", 0.2),
    ]
    assert shortest_path(graph, {"a"}, {"b"}).distance_m == 1
    assert shortest_path(graph, {"a"}, {"b"}, "step_free").distance_m == 10
    assert shortest_path(graph, {"a"}, {"b"}, "step_free", frozenset({"c-b"})) is None
    assert shortest_path([arc("a", "b", 1)], {"a"}, {"b"}, "step_free") is None


@pytest.mark.parametrize("value", [-1, 0, float("inf"), float("nan"), -float("inf")])
def test_invalid_cost(value):
    with pytest.raises(ValueError):
        arc("a", "b", value)


def test_duplicate_edge_and_invalid_profile():
    with pytest.raises(ValueError):
        shortest_path([arc("a", "b", 1), arc("a", "b", 2)], {"a"}, {"b"})
    with pytest.raises(ValueError):
        shortest_path([], {"a"}, {"b"}, "teleport")


def test_generated_graphs_match_independent_floyd_warshall():
    rng = random.Random(2701)
    for _ in range(40):
        n = rng.randint(2, 9)
        graph = [
            arc(str(a), str(b), rng.randint(1, 80))
            for a in range(n)
            for b in range(n)
            if a != b and rng.random() < 0.24
        ]
        distances = [[0 if a == b else math.inf for b in range(n)] for a in range(n)]
        lookup = {e.id: e for e in graph}
        for e in graph:
            distances[int(e.source)][int(e.target)] = e.distance_m
        for k in range(n):
            for i in range(n):
                for j in range(n):
                    distances[i][j] = min(distances[i][j], distances[i][k] + distances[k][j])
        for i in range(n):
            for j in range(n):
                result = shortest_path(graph, {str(i)}, {str(j)})
                if math.isinf(distances[i][j]):
                    assert result is None
                else:
                    assert result.distance_m == distances[i][j]
                    assert sum(lookup[e].distance_m for e in result.edges) == result.distance_m
                    for a, b, e in zip(result.nodes, result.nodes[1:], result.edges, strict=False):
                        assert (lookup[e].source, lookup[e].target) == (a, b)
