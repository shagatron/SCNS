# DSA explanation verified against the submission source

This is an explanation of implemented code, not an additional algorithm feature. Submission baseline: accepted Docker application136667f. No route algorithm or custom data structure was added for academic packaging.

## Graph and structures

- [Core engine](../../backend/app/routing/dijkstra.py): immutable `Arc` dataclass, directed source/target IDs, finite strictly positive scalar movement cost; adjacency is Python `defaultdict(list)`. Reverse movement requires another arc. Geometry crossing/nearby endpoints do not invent a graph connection.
- Python dictionaries hold best rank and predecessor arcs; sets hold start/target IDs and detect duplicate edge IDs. These are built-in hash tables, not a custom hash-map implementation. Python lists hold adjacency/paths; `heapq` is a binary min-heap over a list.
- Heap items contain rank, a monotonic serial from `itertools.count`, and node ID. Rank includes primary cost and deterministic source/path priority tie-breaks. Adjacencies and initial sources are sorted. No custom priority queue, A*, navigation AI or all-pairs production route engine is claimed.

## Dijkstra, relaxation and reconstruction

1. Remove closed/restricted/ineligible arcs before adjacency insertion; explicit closure edge IDs and strict step-free checks also apply in the core. Initialize all eligible source nodes at cost0 (multi-source search).
2. Pop the smallest rank. Skip it if it differs from `best[node]`: this is lazy stale-entry handling. There is no indexed decrease-key operation.
3. For each outgoing arc, add its positive cost and tie-break priority. If its candidate rank is strictly better, replace the best label/predecessor and push a new heap entry.
4. Consider reachable targets and deterministic target priorities. After a target exists, stop only when the next popped primary cost exceeds the best terminal cost; equal-cost target alternatives remain eligible for tie-breaking.
5. Follow predecessor arcs backwards from the selected target, reverse the node/edge lists, and return the computed path. Unreachable returns `None`; same-node return requires no movement. Service adapters produce structured no-route responses.

A unit example has a direct a→d cost200, but a→b→c→d costs50+20+70=140. The computed path must be the three-edge140-cost path, demonstrating why fewer hops and minimum weight differ. [Tests](../../backend/tests/unit/test_routing.py) also cover directionality, disconnected nodes, same-node arrival, multiple anchors, eligibility/closures, invalid costs and deterministic priorities.

## Objectives, physical measures and eligibility

[Published mixed adapter](../../backend/app/routing/mixed.py) constructs namespaced outdoor/indoor nodes and candidate entrances/doors, only from permitted published capabilities. It converts the selected objective into scalar arc cost, then calls the same Dijkstra core:

| Mode/profile | Minimized quantity | Important limits |
|---|---|---|
| Metric shortest | Stored eligible metres | Outdoor estimated OSM lengths are allowed; indoor metric capability/known approved measurement status required. This is not field-survey certification. |
| Directions only | One unit per eligible arc | Fewest eligible traversals, not shortest physical length or fastest travel. May use unknown physical measurements; those stay unknown. Fastest is rejected with this policy. |
| Fastest, metric policy | Supported baseline seconds | Ordinary walking distance/configured speed, connector movement and lift wait estimates when required; absent time evidence excludes that connection. No live queues/personal speed inference. |
| Step-free with selected policy | Same policy cost over a restricted graph | Stairs/unknown or unverified access excluded; no accessible shortcut invented. Reviewed capability/source/connector and operational eligibility still required. |

The core's historical field name `Arc.distance_m`/`Path.distance_m` carries the selected scalar cost; the adapter's explicit `cost_units` distinguishes metres, seconds and traversals. **Do not describe unit-cost educational paths as metres.** The mixed adapter aggregates physical measures separately, returns null totals when incomplete, and keeps known partial distance distinct from a complete measurement. Main API passes configured walking speed(default1.4m/s); connector times use supported reviewed values. [Service](../../backend/app/services/mixed_routes.py) applies release/restriction/version/freshness context; the pure kernel does not perform database reads or GPS sensing.

The [educational adapter](../../backend/app/services/educational_indoor.py) uses the same engine with every authored movement costing1. Its original15-node/26-directed-arc graph has no real campus or publication identity. Same/cross/reverse/same-room routes compute3/9/9/0traversals; the disconnected room has no edges. All physical distance/ETA/accessibility are unknown, including same-room physical totals. Original floor schematics are illustration pixels, not a measured plan.

## Complexity and comparisons

Let V include represented vertices/sources/targets, E the eligible directed arcs and L the output path length. With bounded-size IDs/rank comparisons:

- Adjacency build/duplicate checks: O(V+E) expected hash-table work. Deterministic adjacency/source ordering costs at most O(ElogE+VlogV).
- Lazy heap holds up to O(V+E) entries; successful relaxations may push duplicates. Core conservative bound including sorting: **O((V+E)log(V+E)) time and O(V+E) auxiliary space**. Reconstruction is O(L), with a minimum-cost positive-edge path containing no cycle.
- O((V+E)logV) is conventional for simple graphs (E≤V²), or appropriate indexed-heap variants; do not claim this code implements decrease-key or O(V)-only heap storage.
- These are kernel bounds, not an end-to-end HTTP/PostGIS latency guarantee. Mixed projection/candidate filtering, sorting, geometry work and response construction add costs. In particular the current source/target-priority comprehensions scan their candidate lists per candidate: O(A_s²+A_t²) worst-case preparation, plus layer sorting/scanning. No broad refactor or scalability benchmark was performed for submission.
- BFS computes minimum edges in O(V+E) for equal-weight graphs, so it would suffice for a pure unit-cost graph. SCNS deliberately reuses Dijkstra for both weighted and unit-cost routes; **BFS is not an additional production routing mode**.
- [Outdoor diagnostic reachability](../../backend/app/services/admin_graph.py) uses a list with `pop()` plus a visited set: DFS-style stack traversal, O(V+E) for one adjacency traversal. [Indoor reachability](../../backend/app/services/indoor.py) similarly uses a stack/set. These diagnose connectivity; they do not optimize physical routes. DFS alone does not generally find minimum-weight paths.
- An independent **Floyd–Warshall test reference** checks40deterministically generated weighted graphs of2–9vertices and all vertex pairs. Its O(V³) matrix calculation is test code, not the production route algorithm. It validates reachability, optimum cost, reconstructed edge sums and directed endpoints.

[Presentation walkthrough](presentation.md) · [evidence and honest limits](audit.md).
