# Architecture decisions — M0/M1

## Scope

The user authorized Milestones 0 and 1 only. The numbered milestones govern sequencing; the master document's broader suggested prompt to continue later milestones is not additional authorization. M0/M1 deliver an executable outdoor vertical slice. Full demo rooms/floors, QR, admin, uploads, operational closures and offline features are explicitly assigned to their later milestones in the requirements checklist.

Use the existing checkout. Cloud tasks are isolated already; do not create Git worktrees unless the owner requests one. There were no existing project instructions or C files; the initial commit held only a six-byte README.

## Runtime and boundaries

React/TypeScript + Vite + Tailwind; TanStack Query for server state; Zod for route form input; Leaflet for outdoor rendering. FastAPI/Pydantic exposes `/api/v1`, with SQLAlchemy sessions and Alembic migrations. PostgreSQL/PostGIS is the canonical data store. npm workspaces share one locked JavaScript dependency tree across frontend and browser tests. Python uses a committed uv lockfile. There is no Redis, separate graph database, paid API, account requirement or tile dependency.

The public API has only reads and a route computation POST. It exposes no editor, uploader or filesystem server. The private `data/raw` and `storage` trees are ignored by Git and excluded from containers. Future source assets must pass authorization and derivative review before public delivery.

## Revision and release foundations

Campus-owned catalog/graph rows use `(dataset_revision_id, logical UUID)` keys; UUID identities survive later revisions. Composite foreign keys prevent anchors/edges from joining rows in different revisions, and revision/campus foreign keys prevent cross-campus joins. Buildings and places are distinct entities; graph junctions are not automatically searchable places. Places resolve through any number of anchors.

Dataset revisions have `draft`, `review`, `frozen` states, checksum, parent, version and timestamps. Database triggers reject mutation/deletion of frozen rows and unfreezing frozen revisions. A release must reference a matching frozen revision. The public audience has one active pointer per campus. Changing a synthetic bundle inserts a new revision and moves that pointer in one transaction; failed seeding rolls back every inserted row. The idempotency hash covers the validated full input bundle. **The checksum is an input revision checksum, not a claimed checksummed public downloadable artifact.** Artifact generation and review approval arrive in M2.

Requests use PostgreSQL REPEATABLE READ transactions and read the active pointer once. All subsequent catalog/graph reads are restricted to that revision. No process-local graph cache risks mixing releases. Future caching must key campus/release/audience and a separately versioned closure overlay. `closure_overlay_version=0` means no live overlay is implemented; static closed edges are part of the release.

Public projections are explicit server-side visibility filters applied consistently to search, detail, map and routing, including endpoint-node visibility. Restricted and nonexistent place IDs return the same safe 404. Public responses exclude private evidence, source paths and draft records. M2 will add authorization, reviewed artifact projections and audit controls rather than exposing draft tables through this public API.

## Coordinates

Outdoor geometry is PostGIS EPSG:4326. JSON positions are `[longitude, latitude]`; one frontend adapter converts to Leaflet `[latitude, longitude]`. `ST_Length(geometry::geography)` measures the full path polyline in metres; a database trigger verifies stored edge lengths and directed geometry endpoints. Curves and corners count toward length, and crossing lines do not imply graph adjacency.

The coordinate-frame table and node representation allow future floor-local points. Outdoor nodes contain a geographic point and no pixels. Indoor nodes contain x/y pixels and no geographic geometry; a trigger checks frame type/image bounds. Local origin is top left, +x right, +y down. The adapter produces `[height-y, x]` for a future **separate** `CRS.Simple` map. Scale is metres/pixel from verified calibration; unknown scales cannot produce metric paths. Local path utilities reject mixed frame IDs; cross-floor motion requires explicit connectors in M3. M1's import/edge schema deliberately supports outdoor frames only and rejects indoor bundles.

## Routing

An explicit adjacency list and binary heap implement multi-source Dijkstra. All permitted directions are individual stored edges; paired edges share a physical path UUID. Multi-source initialization and a set of destination anchors choose the cheapest reachable entrance combination. Predecessors reconstruct ordered stored edges and their own polylines. There are no hardcoded route lists, straight-line fallbacks, invisible cross-path intersections or building-centre shortcuts.

Eligibility precedes cost: public, open edges only; step-free additionally requires affirmative synthetic verification on edges and anchors and excludes stairs. Unknown is distinct from false and is excluded. The profile minimizes metres; ETA is total metres / `WALKING_SPEED_MPS` (default 1.4). It is not a fastest-route optimizer or a calibrated stairs/lift travel-time model. ETA uncertainty is disclosed. Same-anchor requests return zero; missing anchors, disconnected graph, and unavailable step-free routes have distinct codes.

Schedules/live closures are not implemented. `departure_at` accepts timezone-aware instants for the future contract, but static release eligibility applies regardless of requested time. Responses disclose this limitation. UTC timestamps are stored, and the campus has an IANA timezone. Graph reads are bounded to 50,000 nodes/150,000 edges; map extents at most 0.1° per axis and 1,000 features per layer; search pages at most 100 records. No large-campus performance benchmark has been claimed.

## Interface

Desktop uses a side planner; mobile stacks labelled controls above the map. Routes remain readable when maps are hidden or fail. Search results, validation failures, no-route cases and offline state are explicit. A stale expected-release error invalidates queries and asks the user to retry. Basemaps are optional; synthetic vector geometry and source disclosure always remain visible. There is no automatic geolocation, tracking, cached-route promise or continuous navigation claim.

## Publication/deployment

Local Compose binds to loopback. Production startup is explicitly gated. Only the owner may choose the eventual code license, permitted institutional map audience, service owner, hosting and paid providers. No public deployment was performed. M2 review/publication, M3 map calibration, M4 operational freshness and M5 pilot/backup/restore evidence remain prerequisites to real campus service.
