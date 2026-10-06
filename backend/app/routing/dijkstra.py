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
    serial = count()
    best = {node: 0.0 for node in sources}
    previous: dict[str, Arc] = {}
    queue = [(0.0, next(serial), node) for node in sorted(sources)]
    heapq.heapify(queue)
    while queue:
        distance, _, node = heapq.heappop(queue)
        if distance != best[node]:
            continue
        if node in targets:
            nodes, edges = [node], []
            while node in previous:
                arc = previous[node]
                edges.append(arc.id)
                node = arc.source
                nodes.append(node)
            return Path(nodes[::-1], edges[::-1], distance)
        for arc in adjacency[node]:
            candidate = distance + arc.distance_m
            if candidate < best.get(arc.target, math.inf):
                best[arc.target] = candidate
                previous[arc.target] = arc
                heapq.heappush(queue, (candidate, next(serial), arc.target))
    return None
