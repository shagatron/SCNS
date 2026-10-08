# Milestone3C indoor and mixed routing contract

Dijkstra runs on the immutable permitted release projection. Draft connector edits never change public search, maps or routes. Routes include a release ID and selected floor descriptors with immutable approved PNG URLs. Every public request can pin the expected release; stale requests fail409 and the planner hides previous results while refreshing. Public deep-link lookups are campus-scoped. Reload recomputes from public IDs/profile/mode on the same release, rather than retaining geometry across release changes.

## Explicit topology and coordinates

`floor_routing`, `connectors`, `connector_stops`, `connector_paths`, `entrance_transitions` are revision/campus scoped. Composite references and deferred SQL guards complement typed server validation. Stops bind a group's building to an existing stored indoor node on an explicitly served floor, exact selected layer/frame/source. Indoor edges remain pixel polylines in one frame. Outdoor edges remain longitude/latitude GeoJSON. Abstract stairs/lifts/ramps and entrance transitions have **no fabricated mixed-frame geometry**; route segments return explicit departure/arrival local points for transition markers. Separate namespace keys prevent coincident UUIDs from implicitly joining indoor and outdoor nodes. Floor order does not imply vertical height or adjacency.

One directed row supports one-way travel. At most two rows share a physical-pair UUID; a reverse pair must reverse endpoints/direction and share costs, status and access attributes. Entrance transitions explicitly bind a building entrance anchor to an indoor entrance-kind node; rooms use explicit open door relationships. Proximity, room-label centres and line crossings never create access. Multiple doors/entrances are all evaluated; cost dominates, then explicit door/entrance priorities and stable graph IDs break ties. The router chooses no arbitrary default floor height/straight-line connector/implicit elevator stop.

## Eligibility, costs and ETA

| Choice | Eligible cost | Unknown handling |
| --- | --- | --- |
| Shortest + metric | Full stored measured/calibrated length | New connector/entrance estimated or unknown length excluded; original outdoor stored geodesic estimated edges remain compatible |
| Step-free + metric | Same distance, every eligible edge/access explicitly verified_step_free | Stairs, unknown accessibility, unknown/unavailable groups and unverified stops/links excluded |
| Fastest + metric | Supported baseline seconds | Missing required movement/wait estimate excluded; no fastest claim in directions-only |
| Explicit directions-only | One cost unit per eligible traversal | May use unknown physical distance; total distance/ETA remains NULL if any section is unknown; never labelled shortest metres or fastest time |

Floor policies default display-only. Enabling requires explicit dated evidence and approved current source; metric requires independently approved calibration. A directions-only floor may have unknown scale; pixels remain pixels. Missing width/slope/steps/surface/elevation/height stay NULL, not a fabricated compliant value. Dated evidence is an administrative assertion, not proof of an institutional survey.

Indoor horizontal seconds use configured walking speed against calibrated stored polyline length. Connector/entrance movement uses explicit baseline traversal seconds; lift ETA also requires baseline wait. Lift status is static available/unavailable/unknown; no live queue/load/fault inference. An ETA becomes unavailable if any selected section lacks supported time. Totals sum unrounded stored values; display rounds distance to centimetres and seconds to tenths. Known-distance subtotal is separately labelled and never presented as a complete total. No-route messages safely explain eligible cost/access/connection gaps without leaking restricted topology.

## Editing, review and isolation

Admin GET/preview/PATCH/validation endpoints end in `/admin/campuses/{campus}/drafts/{revision}/connections`. Edit permission is live `catalog_edit`, read is `draft_read`; operations has no editor and reviewer is read-only. Unsafe requests require Origin/CSRF and current quoted draft-wide If-Match. Preview is non-mutating; atomic PATCH writes all changes, one version increment and append-only actor/before/after audit. Stale retries conflict. Dependency deletion is explicit; a selected plan cannot be replaced/recalibrated/restricted beneath saved connector/floor-policy or tracing dependencies. Submitted/frozen revisions remain read-only.

Admin local forms retain raw invalid numeric text, staged edits, undo/redo and bounded same-tab reload recovery. Recovery lasts at most2hours/2MB/30 actions and is cleared on logout/expiry/revocation. Concurrent comparisons merge independent records; every overlapping record requires a mine/server choice. Selected-plan change requires explicit comparison and rebind acknowledgement; positions are never transformed. Server CAS remains authoritative after reconciliation.

Publication snapshots/checksums/cloning include all five new tables and evidence. Validation retains same-floor geometry/reference/connectivity diagnostics and adds connector completeness/status/verification/cost/pair/reference checks, prerequisites and bounded route evidence. Each enabled public floor needs successful standard and explicit step-free acceptance evidence; multiple destinations need same-floor evidence. Directed cross-floor pairs and indoor↔outdoor capabilities require both profiles and directions, including explained negative cases for unavailable/one-way/unknown step-free gaps. The review UI queues multiple route pairs (maximum250 cases). Independent exact-content review and confirmed publish remain separate operations.

Only permitted public rows and approved current sanitized plans enter the public artifact. Source originals, private evidence, actors, dates and restricted destinations/paths are absent. Public `verified` booleans convey eligibility without private evidence. `uncertainty_note` is explicitly public explanatory text. Rollback changes the active pointer only; frozen artifacts and historical approved PNG URLs remain available. No automatic developer publication occurs.

Templates: [connections-v1](../../data/templates/connections-v1/README.md). Synthetic fixture: [two-floor route data](../../data/demo/indoor-routing/README.md). Operational walkthrough: [indoor routing](../operations/indoor-routing.md). Official data/field verification, real lift behavior, production-scale performance, physical-phone testing and actual Windows execution remain external/unverified.
