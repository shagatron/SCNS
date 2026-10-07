# Milestone 3B: visual same-floor indoor tracing and canonical room catalog

Base: `feat/milestone-3a-floorplans` · Head: `feat/milestone-3b-indoor-editor`

Administrators can now trace canonical indoor destinations, explicit door access and same-floor paths onto the selected independently approved plan. Pixel coordinates stay separate from outdoor geography; calibrated full-polyline lengths require reviewed scale, and unknown scale requires explicit directions-only editing with NULL distance. Every save remains a private draft operation. Public search/maps/routes keep their active immutable release until a separate independent review and explicit publication; published rooms are honestly labelled catalog-only, with no indoor routing claim.

## Delivered behavior

- Additive `0013_indoor`: revision/campus/floor/frame/source-bound room, node, directed path and room-door tables; stable canonical catalog IDs/aliases/departments; NULL room geography and composite references. SQL guards protect frozen/submitted revisions, bounds, calibrated costs, paired edges and dependent floorplans/calibration/floors/buildings.
- Protected GET, non-mutating typed preview, atomic PATCH and actionable validation. Existing live campus grants, opaque sessions, Origin/CSRF, global draft CAS and append-only audit apply. Audit identifies actor, changes and exact selected frame/source/plan. Separate committed races have one winner; injected late audit failure rolls everything back.
- Responsive building/floor-scoped CRS.Simple editor: sanitized plan pan/zoom/Fit/opacity, room labels, corridor/junction/door nodes, explicit door links, stored polylines, one-way/paired paths, pointer/numeric editing, splitting, 2-reference-pixel snapping and deliberate intersection connections. Deletion previews dependencies, and door splits retain door kind only on legs touching an explicit door.
- Nullable accessibility/width/slope/steps/surface and dated provenance; nothing is inferred from drawings. Node/path changes clear affected survey assertions. Directed connectivity, unlinked doors, frame/bounds/reference/pair/code errors, unmapped crossings, unknown step-free and stale evidence have inspectable diagnostics. Bounded spatial work blocks incomplete validation rather than claiming success.
- Undo/redo, bounded same-tab raw-input recovery, failed-save preservation and explicit three-way record conflict decisions; changed plans require reference comparison. Private recovery clears on logout/expiry/revocation, with generation guards against queued writes from ended sessions.
- Exact-content hashes/review/contributor separation, cloning, immutable permitted indoor projection and retained rollback integrate with the existing lifecycle. Restricted entities/private evidence/actors/source metadata stay absent from public artifacts. Existing historical release bytes/hashes are untouched.
- Invented 600×400 tracing fixture (3 rooms, 6 nodes, 10 directed paths, 3 door links), strict JSON schema/example, coordinate/API/ownership contract and complete data-preserving Windows/manual walkthrough. Existing staged CSV/JSON/GeoJSON imports and outdoor editor/navigation remain intact.

## Verification

- Ruff lint/format, TypeScript/ESLint, Vite production build and Python compilation pass.
- **77 Python units, 35 frontend tests and 143 PostGIS integrations pass**, no skips. Covers campus/role/draft/CSRF boundaries, invalid atomic writes, directed/paired geometry, unknown-scale modes, frame/provenance/dependency guards, true committed concurrency, rollback, review/clone/hash/projection and public isolation.
- Fresh/M1 downgrade/re-upgrade through 0013, bootstrap and model alignment pass on guarded disposable databases.
- **48 source desktop/mobile Chromium journeys pass**: four new indoor workflows plus all 44 existing public/admin/session/import/graph/floorplan/review journeys. Indoor tests exercise pointer placement, canonical aliases, room/door/path creation, one-way and paired split, dependency deletion/undo/redo, raw input/reload, conflict decisions, reviewer read-only, logout clearing, independent publication and public exclusions.
- Nine generated contracts reproduce byte-for-byte; original 11-place/13-node/27-edge synthetic outdoor bundle validates.
- **20 final built nginx/API/actual-worker desktop/mobile journeys pass**, including private two-page PDF/masks/page replacement and >6MiB valid image processing, indoor workflows and public regressions. Both final images built; readiness/privacy checks and owned cleanup pass.
- Data-retaining local 0013/image update preserves all 28 original table counts, floor counts, active pointers, release checksums and `.env` hash. Four new indoor tables are empty. Main Gate→Library remains 256.88m/three stored edges on the original release. No developer seed/reset/bootstrap/publish/rollback.

Details: `docs/testing/verification.md`. Exact PowerShell update and complete fixture walkthrough: `docs/operations/indoor-editor.md`. Data/API contract: `docs/data/indoor-editor.md`; fixture: `data/demo/indoor/synthetic-ground.json`; patch schema/example: `data/templates/indoor-v1/`.

## Limits and scope

Owner-reported Windows ACA Ground Floor at 0.05m/reference-pixel with separate source/calibration approval is prior 3A evidence from a separate database, not cloud verification. Actual Windows execution/owner manual run, physical phones/non-Chromium/human assistive technology, official plans/rights/field survey/accessibility, Linux ARM, large-campus throughput/production security/load/backup restoration/process-kill chaos and remote Actions remain unverified. Uniform rectified plans only. Diagnostics have documented record/patch/finding/pair budgets; exhausted spatial validation blocks completeness. Recovery is 2MB/two hours/30 actions, not durable server undo.

No 3C connectors/cross-floor edges/end-to-end indoor-outdoor route generation or public floor picker. No later milestone, ML, broad redesign, live closures, deployment/cloud publication or merge. All tested publication/rollback uses disposable synthetic fixtures; no developer reseed/reset/bootstrap/publish/rollback, volume/private-upload/.env deletion or credentials in this PR.
