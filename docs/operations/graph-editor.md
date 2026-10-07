# Outdoor draft graph editing (Milestone 2B2)

Use `/admin` → assigned campus → create/select draft → **Outdoor graph**. Editors and campus system administrators edit; reviewers inspect/validate/test routes; operations users have no graph access. Existing cookie, expiry/revocation, Origin and CSRF checks apply. All reads/writes are campus/revision scoped. Public APIs still read the immutable active release. Nothing in this workflow publishes or approves a draft.

## Updating and starting locally

Keep the existing `.env`, database volume and private-upload volume. From this checkout:

```bash
cd /workspace/SCNS
git switch feat/milestone-2-graph-editor
git pull --ff-only
make setup
make db migrate seed-demo
# Stop local Compose app services before running source services; keep DB/volumes.
docker compose stop api frontend import-worker
make dev
```

`make dev` starts API (8000), frontend (5173) and import worker with the same private storage; Ctrl+C stops them together. Open the local frontend `/admin`. Existing assigned accounts remain valid. If this is a fresh database, choose your own password using the trusted one-time [bootstrap procedure](admin.md); no default account/password is supplied. Demo seeding is explicit and idempotent for unchanged synthetic data; it does not apply an edited draft.

For containers after stopping source services:

```bash
python scripts/cloud-build.py  # cloud proxy/CA-aware build; ordinary hosts: make containers
docker compose run --rm --no-deps api alembic upgrade head
docker compose up -d --wait --no-build api frontend import-worker
```

There is no additional worker/service/dependency for graph editing. Migrations `0007_graph_node_evidence` and `0008_outdoor_accessibility` add node provenance notes and nullable width/slope/step-count/surface measurements; existing nodes default to blank notes and measurements remain unknown. It does not change stored public geometry, costs or release pointers. Never use `down -v` for updating this application.

## Coordinates and actions

Outdoor points/polylines use EPSG:4326 GeoJSON **[longitude, latitude] in degrees**. The shared adapter converts them once to Leaflet latitude/longitude. Node coordinates can be entered numerically or moved by selecting a node and clicking with the Move tool. Node movement updates incident path endpoints in the same transaction, preserves interior bends, resets affected accessibility to unknown and distance status to estimated. Length is recomputed from the whole stored line using PostGIS geography; supplied scalar lengths are not accepted.

Select a path on the map or in the searchable feature lists. Use endpoint selectors, Draw tool (map clicks insert interior vertices), Move vertex tool, Remove vertex, or editable coordinate array. Endpoint coordinates must match selected nodes exactly. Invalid text stays available for correction; Apply coordinates stages local changes, **Save graph to draft** persists them. Snapping uses the closest existing node within 2m for map drawing; it snaps coordinates, not topology. Select endpoints explicitly. Selecting an existing node during drawing inserts its position as a vertex without silently splitting/interconnecting the graph.

Two-way paths consist of two stored directed edges with one physical-path UUID. Editing either direction updates its reverse together. One-way removes only the reverse; the displayed from → to direction remains. Paths may be walkway/ramp/stairs, public/restricted, and statically open/closed in the draft. Static state is not a live-closure feature. Unknown accessibility is the default and is excluded from verified step-free routing. A renewed verified step-free assertion requires source notes and a valid non-future `YYYY-MM-DD` date; stairs cannot qualify. Existing imported undated evidence remains readable and is flagged for review. Width (metres), slope (percent), step count and surface are nullable; blank means unknown. Values never imply step-free verification automatically; a verified path cannot have a positive step count. Synthetic evidence never certifies physical accessibility.

**Split** at an interior vertex creates a node and two physical-path segments, preserving paired directions. Add a vertex first if needed. To connect two intersecting paths deliberately, split the first, then split the other at the same existing intersection node (within 1m of its chosen vertex). The second path bends/snaps to that chosen node. Crossing polylines alone never become adjacent. Near duplicates and apparent crossings receive diagnostics for editor review; bridges/overlaps may legitimately remain disconnected.

Connect place entrance creates an anchor; select the draft place and graph node, accessibility/evidence and draft open state. Public places require public nodes. Node deletion previews all incident directed-edge and entrance-anchor IDs/counts and stages their explicit removal; path deletion previews both stored directions. Confirm before saving. Server-side missing-reference/visibility/pair/geometry guards reject incomplete batches. Indoor connector and QR-marker references do not exist yet; their tools/checks belong to later milestones.

## Recovery, concurrency and audit

Each editing action supports local undo/redo (30 prior snapshots). Saved server batches form an audit history, not a reversible publication history. The indicator distinguishes **recovery autosaved in this tab** from **draft saved on server**. Per-account/campus/draft `sessionStorage` recovery holds the base version, local graph, unapplied coordinate/polyline text and undo/redo snapshots for up to two hours. Draft/tab selection is retained separately. It contains no passwords, cookies, CSRF tokens or upload contents. Recovery is private to this browser tab/origin, may be unavailable/full, and is cleared on deliberate sign out. Closing a tab ends its normal session-storage lifetime; no cross-device/cloud recovery is promised. Established-session expiry hides the UI; the same account can sign in again and recover retained edits. Do not use a shared browser for confidential editing. Storage failure produces a warning; keep the tab open until save succeeds.

Saves contain at most 500 affected records with stable UUIDs. Read responses and diagnostics carry a coherent revision-wide version. `If-Match` CAS serializes graph/catalog/import writes; one competing write succeeds, losers receive 409. The UI retains input, loads latest, merges independent records and shows before/proposed fields for same-record conflicts. Choose server or your proposal for each conflict, then explicitly save the reconciled batch. Server validation remains authoritative. A failed/ambiguous network request can be retried; stable IDs and the unchanged optimistic version prevent accidental extra records. No silent version bump or overwrite occurs.

Deletes, creates, moves (including implicit incident-path changes), anchor changes, lengths and audit share one database transaction. Audit identifies actor, campus, revision, resource, before/after and request ID. Failed writes leave records/version/audit unchanged. New edits invalidate displayed validation/route results. There are no approval records/checksums/publication operations in this milestone.

## Quality and routing diagnostics

Validate the **saved** graph for geometry/boundary/endpoint/reference/frame/visibility/accessibility errors, repeated vertices, direction-pair consistency, unusually long (>500m) paths, near duplicate nodes (1m), unconnected crossings, missing/stale (>365 days)/future evidence, weak components and directed searchable-destination reachability. Standard and verified step-free profiles are checked separately; legitimate isolated/restricted areas may be documented for later review. Findings identify feature IDs and actions; inspect buttons select graph features. Up to 500 findings and 100 spatial pairs per category are displayed, with explicit truncation/caps. The editor loads at most 15,000 records per layer and returns an actionable limit error above this; large-campus throughput is unverified.

The route test console runs the existing heap Dijkstra against stored **draft** directed edges and eligible entrance anchors, never hardcoded results. It highlights stored path geometry and shows metres/edge count or no eligible route. It does not change public search/map/routing, store approval evidence or publish. The editor renders campus boundary and stored features without external tiles by default. Existing owner-configured `VITE_BASEMAP_URL` plus `VITE_BASEMAP_ATTRIBUTION` enables a permitted background overlay; tile failures leave vectors/coordinates usable. The private source-asset approval register remains later administration work.

## Verification

```bash
make check build test-unit test-integration test-migrations validate-dataset
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e
make generate-api
```

Browser/migration runners reset only their explicitly disposable `_e2e_test`/`_migration_test` databases. Integration tests use rollback fixtures and uniquely scoped committed concurrency records. See [actual verification evidence](../testing/verification.md); physical campus maps, owner manual testing, real phones and production deployment remain unverified.
