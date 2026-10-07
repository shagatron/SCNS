# Architecture decisions — M0/M1 and M2A

## Scope

The user authorized Milestones 0/1 and subsequently the admin-only Milestone 2A slice. The numbered milestones govern sequencing; the master document's broader suggested prompt to continue later milestones is not additional authorization. M0/M1 deliver an executable outdoor vertical slice. Full demo rooms/floors, QR, uploads, operational closures and offline features are explicitly assigned to their later milestones in the requirements checklist.

Use the existing checkout. Cloud tasks are isolated already; do not create Git worktrees unless the owner requests one. There were no existing project instructions or C files; the initial commit held only a six-byte README.

## Runtime and boundaries

React/TypeScript + Vite + Tailwind; TanStack Query for server state; Zod for route form input; Leaflet for outdoor rendering. FastAPI/Pydantic exposes `/api/v1`, with SQLAlchemy sessions and Alembic migrations. PostgreSQL/PostGIS is the canonical data store. npm workspaces share one locked JavaScript dependency tree across frontend and browser tests. Python uses a committed uv lockfile. There is no Redis, separate graph database, paid API, public account requirement or tile dependency.

The public API has only reads and a route computation POST. It exposes no editor, uploader or filesystem server. The private `data/raw` and `storage` trees are ignored by Git and excluded from containers. Future source assets must pass authorization and derivative review before public delivery.

## Revision and release foundations

Campus-owned catalog/graph rows use `(dataset_revision_id, logical UUID)` keys; UUID identities survive later revisions. Composite foreign keys prevent anchors/edges from joining rows in different revisions, and revision/campus foreign keys prevent cross-campus joins. Buildings and places are distinct entities; graph junctions are not automatically searchable places. Places resolve through any number of anchors.

Dataset revisions have `draft`, `review`, `frozen` states, checksum, parent, version and timestamps. Database triggers reject mutation/deletion of frozen rows and unfreezing frozen revisions. A release must reference a matching frozen revision. The public audience has one active pointer per campus. Changing a synthetic bundle inserts a new revision and moves that pointer in one transaction; failed seeding rolls back every inserted row. The idempotency hash covers the validated full input bundle. **The checksum is an input revision checksum, not a claimed checksummed public downloadable artifact.** Artifact generation and review approval arrive in M2.

Public requests use PostgreSQL REPEATABLE READ transactions and read the active pointer once. All subsequent catalog/graph reads are restricted to that revision. No process-local graph cache risks mixing releases. Future caching must key campus/release/audience and a separately versioned closure overlay. `closure_overlay_version=0` means no live overlay is implemented; static closed edges are part of the release.

Public projections are explicit server-side visibility filters applied consistently to search, detail, map and routing, including endpoint-node visibility. Restricted and nonexistent place IDs return the same safe 404. Public responses exclude private evidence, source paths and draft records. M2A adds a separate protected admin API. Reviewed artifact projections and publication remain M2B/2C; draft tables are never exposed through the public API.

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

## M2A identity and draft administration

`/admin` lazily loads the admin React interface; `/api/v1/admin` holds the protected API. Identity/permissions are separate from public route calculation. Argon2id local passwords, hashed opaque database sessions, HttpOnly/SameSite cookies, expiry/revocation, exact Origin checks, session-bound CSRF, durable account/IP throttles and no-store responses provide the local session boundary. One-time trusted-host bootstrap supplies the initial campus administrator without a default password. Roles are live database grants, scoped to the requested campus, including system administrators. See [admin operation/security details](../operations/admin.md).

Administrative transactions use READ COMMITTED. A write conditionally increments the revision-wide `edit_version` with `If-Match`; losing writers return 409. Catalog reads hold a shared revision lock so their rows and version are coherent. Writes, reference changes, version changes and audit are one transaction. Draft creation is serialized per campus with the same advisory lock as demo seeding. It copies the current release, preserving graph topology/stable IDs, without changing the active pointer. Draft checksums become NULL; frozen revisions still require their checksum. No API can freeze, review, publish or roll back a revision in 2A.

Departments and place links are revision scoped. Canonical normalized alias rows synchronize a legacy JSON/search-text projection inside the draft. Anchors include private evidence notes, required when editing a verified step-free anchor; no evidence is fabricated for old frozen rows. All cross-entity references use the same revision/campus. Deleting referenced places/buildings fails instead of silently cascading. Audit and bootstrap records reject database UPDATE/DELETE. These controls do not claim tamper resistance against a database superuser.

The UI captures an edit version when opening a form, preserves unsaved input on conflicts, displays the latest record and requires explicit reconciliation. It has manual save, no autosave or browser-persisted draft recovery; full map-editor recovery belongs to later editing work. The browser suite uses a disposable database and separate API/frontend ports, ephemeral credentials and disabled admin traces. Migration rehearsal uses another disposable database and tests backfill against already frozen M1 data.

## M2B2 outdoor editing

The protected graph API reuses `draft_read` and `catalog_edit` campus permissions, shared revision read locks, draft-wide conditional version updates and the existing admin transaction/audit boundary. A bounded typed batch expresses explicit node/edge/anchor creates/updates/deletes; combined state validation precedes dependency-ordered writes. Node moves update incident endpoints atomically; lines use exact database endpoint points rather than rounded GeoJSON copies. PostGIS recomputes full geodesic lengths; audits capture persisted results. Frozen release tables/pointers are never changed. Catalog and import regressions remain mandatory.

The Leaflet draft view reads protected stored graph rows, not public map data. Paired directions share physical-path IDs. Splitting creates explicit topology; snapping positions alone never connects crossing paths. Nullable dimensions retain unknown states; dated evidence is required for renewed accessibility assertions. Quality diagnostics use reference/geometry/pair checks, spatial warnings and standard/step-free reachability; draft test routes reuse authoritative heap Dijkstra. No review approval/publication operation is provided.

Local undo/redo and account/campus/draft-scoped sessionStorage recovery preserve unsaved graph and unapplied text. Recovery is bounded to the current tab/two-hour lifetime and cleared on deliberate logout; no session/credential data is persisted. Selection preferences survive reload. Revision conflicts retain input, merge independent records, and require explicit same-record decisions before another guarded save. The detailed limits and startup/operation contract are in [graph operations](../operations/graph-editor.md).

## M2C exact-content review and atomic publication

Authorized separately from 2B2. Protected publication routes add source rights/derivative approval, immutable validation runs/decisions, review submissions and idempotent release actions. Submission locks entity writes in `review`; independent approval remains review-locked, rejection/withdrawal returns `draft` at a fresh edit version, confirmed publication becomes permanently `frozen`. Revision CAS and full canonical content hash bind validation/review; later edits cannot reuse evidence/approval. Campus editor submits, campus reviewer approves/publishes/rolls back; system administrators obey contributor separation. Live reviewer/source grants are checked before publication. Queued publication/rollback and streamed source registration reauthorize after campus-lock waits, with active accounts refreshed from the database.

An immutable monotonic publication order distinguishes release history from draft creation order. One campus advisory lock (same ordering as draft creation/seeding), revision row lock and expected active pointer guard serialize publication/rollback/retries. Artifact generation, freeze, immutable release/public projection, pointer change, action record and audit share the admin transaction. No external artifact upload can partially succeed; artifacts are canonical public JSONB served as exact immutable UTF-8 bytes, source originals private bounded BYTEA with exact UTF-8 file bytes, safe names/media types and hashes (inline object registrations use canonical bytes). Injected generation/audit failures demonstrate complete rollback. Historical synthetic seed IDs/checksums remain unchanged; new release content checksum and separate public artifact checksum are documented in [publication operations](../operations/publication.md).

Public search/map/detail/routing retain explicit visibility-filtered frozen-revision queries, matching the reviewed artifact projection. Department projection removes private links; public overlay map geometry comes only from the immutable approved artifact. Optional expected-release IDs on map/search/directory complement route stale checks. Frontend acquires a release first, pins all data reads, keys state by release and clears stale route/selection state before refreshing. Successful polling/focus or manual metadata refresh completes recovery; pre-recovery cached metadata cannot restore old results. Online polling/on-focus and stale response handling work across API workers without a process-local graph cache. Private source routes require campus authorization; no raw storage URLs/static mounts exist.

Floorplan images/PDF/calibration remain M3; closure overlay reconciliation, QR and offline packs remain M4. No publication/deployment of this cloud environment is authorized. Full contributor test commands and data-retaining PowerShell/Docker Desktop updates are in the operations guide.
