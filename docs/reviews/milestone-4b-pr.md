Operational closures now exclude current published paths and connectors from both manual and confirmed QR routes without editing or publishing drafts. Operators can record a dated incident, retain an informational estimated end and explicitly verify reopening. A synthetic lift outage returns no verified step-free route when only stairs remain, while ordinary shortest routing retains the stairs route.

This delivers only the next recorded Milestone4 slice,4B, from verified4A75a87df31bbc485da32f9fca1f3b08576bd42711. Outdoor geolocation4C, reports4D, PWA4E and facility/performance4F remain unstarted.

The campus-scoped overlay has its own monotonic version, whole-overlay If-Match, stable incident IDs, actor-scoped idempotency receipts, normal live session/CSRF/permission checks and transactional audit. Stale admin forms retain their input; explicit reconciliation is required. Lost-response retries freeze fields and reuse the unchanged key to avoid duplicate incidents. Operations/system-admin can manage; editor/reviewer can inspect.

Public requests read release and overlay in one REPEATABLE READ transaction without process-local caches. Hard restrictions filter a request-local copy before existing Dijkstra. Online metadata polls/focus/reconnect checks hide stale route directions/geometry and retain selections; a failed, offline or stale check prevents claiming a current route. Scheduled incidents are conservatively excluded across at least a one-hour route window, expanded for longer ETA; unknown ETA excludes all unreopened schedules. Estimated ends never automatically reopen paths.

Publication/rollback retains matching physical outage targets or atomically marks changed/missing targets unresolved, increments the overlay and audits. Unresolved targets are publicly redacted and pause campus routing, including future incidents. Restoring map history never clears an unresolved outage. Explicit verified rebind keeps it closed. Existing independent approval, immutable release/private asset, QR lifecycle, import/editor and indoor/outdoor boundaries are preserved. Migration0016_closures adds initially empty tables and retained-history protections; no seeds, account bootstraps or developer publication.

Validation evidence and resolved failures are documented in docs/testing/verification.md:

- Ruff lint/format, TypeScript/ESLint, Vite/Python build;103Python/47frontend units passed.
-194full PostGIS regression cases plus14final affected closure cases (includes one additional actual committed-reader snapshot test). Roles/CSRF/campus isolation/live revocation, competing writers/retries/stale versions, audit rollback, scheduled/overlapping closures, normal independent two-floor lift publication, outage preservation/rollback/unresolved rebind and public/draft isolation.
- Fresh and retained migrations/model alignment through0016;14generated contracts reproduce without drift.
- Full source run60passed/2failed followed by passing14graph/closure and10navigation affected reruns covers all62distinct desktop/mobile journeys. Initial mobile coordinate/readiness test issues corrected; no assertions or application controls weakened.
- **34built nginx/API/actual-worker desktop/mobile journeys passed** (3.6minutes), including closure conflict/lost-response retry, outage/no stairs fallback/rollback, QR, actual PDF/image processing and independent floor approvals, indoor connectors, publication and public navigation. Readiness200/anonymous admin401/private originals404 passed; only uniquely owned smoke resources/test DB removed, no developer volume removed.
- Guarded Windows update parses and mocked branch/dirty-tree/migration-failure command checks pass on Linux PowerShell7.5.4; actual Windows4B not executed.
- Forward-only developer0015→0016 update preserved **38existing table counts plus3floor-table counts**, active pointers, release checksums and `.env` hash; three new tables empty. Existing postgres-data/private-imports volumes retained. Built readiness and public original release4eb587e6-5607-48ed-a8ca-f5c0d8f1c505/MainGate→Library256.88m/three edges/overlay0/no-store passed; anonymous admin401/private404 passed. No seed/bootstrap/reset/developer publication or outage created. This receipt covers this cloud developer DB, not the owner's Windows DB

Manual inputs and complete data-preserving Windows commands: docs/operations/closures.md. API/temporal/privacy limits: docs/data/closures.md. Generated request templates: data/templates/closures-v1. Progress/checklist/slice acceptance updated.

Owner-reported Windows4A update/readiness/planned/outdoor/revoke/reassign/indoor results are recorded separately from automation. Windows concurrency observation remains inconclusive; separate built-app investigation passed and no application fix was made. Owner sign downloads/physical scanning/printing remain unverified.

Actual Windows4B/physical devices/repairs/accessibility/real-campus surveys, Firefox/Safari/human AT, production-scale load and remote Actions remain unverified. No GPS test is claimed. Recurring hours/arrival-aware waiting/lift queues/historical operational reconstruction and history archival are unsupported. History limit2,000 and target menu limit5,000 fail safely and are documented. No merge/deployment/cloud publication, real MUJ import, reseed/reset or volume removal.

Base: feat/milestone-4a-qr-markers (verified75a87df31bbc485da32f9fca1f3b08576bd42711).
Head: feat/milestone-4b-closures.
Suggested title: Add live path closures and lift-outage routing safety (Milestone4B)
