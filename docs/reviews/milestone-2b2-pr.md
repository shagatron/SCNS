# Milestone 2B2: visual outdoor draft graph editor

Adds a responsive Leaflet editor for private campus draft nodes, stored directed path polylines and place entrance anchors. Editors can move nodes with incident geometry/length updates, edit paired two-way or one-way paths, draw/move/remove vertices, split paths, deliberately connect intersections, preview dependent deletions, and undo/redo local actions. Unknown width/slope/step-count/surface and accessibility values stay unknown until entered from evidence; renewed step-free assertions require dated source notes.

Graph batches reuse campus authorization, CSRF, draft-wide optimistic concurrency, transactional reference/geometry validation and append-only audit. Stale saves retain input and require explicit reconciliation. Per-account/campus/draft tab recovery autosaves unsaved graph and coordinate text; server saves are explicit. Graph quality diagnostics and heap-Dijkstra draft route tests operate on stored draft data. Public search/map/routing retain the immutable published release; imports never publish.

Migrations `0007_graph_node_evidence` and `0008_outdoor_accessibility` add provenance notes and nullable outdoor measurements. Existing release pointers/geometry remain unchanged. Operations, templates, progress, checklist, architecture and verification documentation describe exact startup/update commands, recovery limits and remaining scope.

Validation:

- `make check build test-unit test-integration test-migrations validate-dataset`: passed; 35 Python unit, 19 frontend and 74 real PostGIS tests, including 24 graph cases.
- `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e`: all 38 desktop/mobile journeys passed (10 graph, 12 admin/session, 6 imports, 10 public navigation); graph axe/overflow checks passed.
- Contract/schema regeneration reproduced byte-for-byte.
- Both images built; Compose migrations/startup, protected/private endpoints, worker queue and built Chromium login smoke passed. Built isolated authenticated API smoke passed CSRF, atomic graph move, concurrency rejection, quality/route tests, public isolation and logout revocation.
- Main Gate → Library remains 256.88m over three stored edges on the existing public release. Source/container graph-service hashes match; `git diff --check` passed.

Limits: per-tab recovery (two hours, 30 undo snapshots), 500 records/save, 15,000 records/layer, diagnostic/spatial caps are documented. Official maps/rights/surveys, owner manual testing, physical phones, non-Chromium browsers, human assistive-technology review, load/chaos/pentest/backup and remote Actions are unverified. Full authenticated browser journeys ran against isolated source API/Vite; built nginx received smoke checks. Synthetic notes do not certify physical accessibility. Production login throttles remain unchanged; only the disposable browser runner increases its shared-IP test budget.

Targets `feat/milestone-2-imports` from verified `4444c68`. Do not merge as part of this task. Review/publication/rollback (2C), indoor navigation, live closures and deployment are outside this PR. Existing `.env`, database volumes and private uploads are preserved; no public deployment/cloud environment publication occurred.
