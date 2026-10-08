"""Multi-source Dijkstra over explicitly directed, eligible edges; no geometric shortcuts."""

import heapq
import math
from collections import defaultdict
from dataclasses import dataclass
from itertools import count


@dataclass(frozen=True)
class Arc:
    id: str
    source: str
    target: str
    distance_m: float
    kind: str = "walkway"
    accessibility: str = "unknown"
    is_open: bool = True
    visibility: str = "public"

    def __post_init__(self):
        if not math.isfinite(self.distance_m) or self.distance_m <= 0:
            raise ValueError("Movement distance must be finite and positive")


@dataclass(frozen=True)
class Path:
    nodes: list[str]
    edges: list[str]
    distance_m: float


def shortest_path(
    arcs: list[Arc],
    sources: set[str],
    targets: set[str],
    profile: str = "shortest",
    closed_edges: frozenset[str] = frozenset(),
    source_priorities: dict[str, int] | None = None,
    target_priorities: dict[str, int] | None = None,
) -> Path | None:
    if profile not in {"shortest", "step_free"}:
        raise ValueError("Unsupported profile")
    adjacency: dict[str, list[Arc]] = defaultdict(list)
    seen = set()
    for arc in arcs:
        if arc.id in seen:
            raise ValueError("Duplicate edge ID")
        seen.add(arc.id)
        if not arc.is_open or arc.visibility != "public" or arc.id in closed_edges:
            continue
        if profile == "step_free" and (
            arc.kind == "stairs" or arc.accessibility != "verified_step_free"
        ):
            continue
        adjacency[arc.source].append(arc)
    for edges in adjacency.values():
        edges.sort(key=lambda edge: edge.id)
    source_priorities, target_priorities = source_priorities or {}, target_priorities or {}
    serial = count()
    best = {node: (0.0, source_priorities.get(node, 0), node) for node in sources}
    previous: dict[str, Arc] = {}
    queue = [(rank, next(serial), node) for node, rank in sorted(best.items())]
    heapq.heapify(queue)
    terminal = None
    while queue:
        rank, _, node = heapq.heappop(queue)
        distance, source_priority, origin = rank
        if terminal and distance > terminal[0]:
            break
        if rank != best[node]:
            continue
        if node in targets:
            candidate = (distance, target_priorities.get(node, 0), source_priority, node, origin)
            if terminal is None or candidate < terminal:
                terminal = candidate
            continue
        for arc in adjacency[node]:
            candidate = (distance + arc.distance_m, source_priority, origin)
            if candidate < best.get(arc.target, (math.inf, 0, "")):
                best[arc.target] = candidate
                previous[arc.target] = arc
                heapq.heappush(queue, (candidate, next(serial), arc.target))
    if terminal:
        node = terminal[3]
        nodes, edges = [node], []
        while node in previous:
            arc = previous[node]
            edges.append(arc.id)
            node = arc.source
            nodes.append(node)
        return Path(nodes[::-1], edges[::-1], terminal[0])
    return None
