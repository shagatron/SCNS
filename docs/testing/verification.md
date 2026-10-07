# Verification evidence

## M2B1 final verification — 7 October 2026 (Asia/Kolkata)

Scope: staged CSV/JSON/GeoJSON draft imports only, based on `9f0e489`, with pushed checkpoints `790bc4a` and `6e54e5f`. No implementation restart. The latest resume preserved all UI/cache-refresh changes before further verification. Milestone 2B2, review/publication and deployment are outside this result.

| Executed check | Observed result |
|---|---|
| `make check` (latest rerun after the added worker test) | Ruff/format **44 files**, TypeScript, ESLint passed |
| `make build` on final application code | Vite build and Python compilation passed |
| `make test-unit` | **35 Python unit + 14 frontend tests passed**; no skips |
| `make test-integration` (final full run) | **50 PostGIS tests passed**, including 28 existing regressions and 22 import cases; no skips |
| New worker test alone, then final full integration run | Passed: committed stale parsing lease recovers, retry ceiling holds, cancelled job is not processed, expired original/orphan cleanup preserves fresh orphans and DB history |
| `make test-migrations` | Fresh/reset, downgrade to M1/re-upgrade through `f420e55f937e`, alias backfill/frozen guard, release/checksum preservation, schema alignment and one-time trusted CLI bootstrap passed |
| `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e` | **28 passed**: six import, twelve admin/session and ten public-navigation journeys across desktop/360px mobile |
| `make validate-dataset` | Original 11-place/13-node/27-edge outdoor fixture valid; no data imported |
| `make generate-api` + before/after SHA-256 verification | OpenAPI, generated TS, original dataset schema and new import-bundle schema reproduced byte-for-byte |
| Offline import validation CLI | Parsed all ten synthetic bundle records without writes; CLI clearly distinguishes parsing from authoritative staged/reference validation |
| `python scripts/cloud-build.py` | Both images built with existing proxy/CA/dependency verification; no verification bypass |
| Compose migration/startup and worker `once` | API/frontend/worker started; migrated durable queue readable; API/worker share private volume and API image |
| Built nginx/API/browser smoke | Protected session/import endpoints 401; private data/storage paths 404; normal fresh admin login, zero alerts, exactly one session check |
| Stored route before/after imports and built smoke | Public release `4eb587e6-5607-48ed-a8ca-f5c0d8f1c505`, Main Gate → Library **256.88m / three stored edges**, preserved |
| Container/source SHA-256 | Import service identical inside/outside API image |
| Host `make dev`, functional readiness/route/queue check, SIGTERM shutdown | All three services started; ready PostGIS and computed route succeeded; API/web ports closed and worker children stopped; Compose restored afterward |
| Empty built private-volume cleanup | Zero files removed; job-history retention command completed |
| `git diff --check` and ignore/staged-file review | Passed; secrets, raw source files, dependencies, database files, build outputs and browser artifacts excluded |

Integration import evidence covers all supported catalog/outdoor entity types, JSON bundle ordering, CSV mapping and GeoJSON geometry; strict JSON/CSV/CRS/coordinate/boundary/metadata/byte/row/quota failures; duplicate IDs/codes, explicit adoption/upsert and unchanged template replay; campus/role/CSRF isolation; checksum/private-path protection; stale previews; real simultaneous distinct-job application (one commit/one conflict) and same-job replay (one apply audit); injected second-row rollback of entities/bindings/version/audits; existing-node dependent-graph integrity; unchanged public search/map/routes. Diagnostic export units escape formula-like values. Worker tests use actual committed leases/transactions in the disposable test database, not sleeps or mocked successful writes.

Browser evidence covers upload → processing → preview → comparison/download → validate → explicit apply; catalog refresh after application; repeat unchanged import; CSV column mapping/conflict/policy reprocessing/cancellation; GeoJSON stale preview rejection/refresh; responsive overflow and axe checks. Random credentials/private files stay in isolated test environment/storage; admin traces/screenshots/video are disabled. The full run used source API/Vite/worker on 8001/5174 and took 2.1 minutes. It did **not** exercise all authenticated journeys against built nginx; the built stack received the smoke checks listed above.

Earlier failing import browser selectors were corrected to accessible control roles. Browser assertions then caught stale cached catalog data after apply; the UI now invalidates the affected draft/dashboard. Those journeys and the full suite subsequently passed. No test assertion, permission boundary or public-isolation expectation was disabled to get a pass. The newly added recovery test was verified on resume; unchanged full unit/build/browser/migration runs were retained instead of needlessly repeated.

Non-failing upstream warnings remain: Starlette TestClient recommends `httpx2`, the cloud helper's `UV_NATIVE_TLS` spelling is deprecated, and Playwright reports color-environment conflicts. No warnings were suppressed. No admin is bootstrapped in the developer database. Synthetic coordinates/evidence do not validate physical campus navigation or accessibility.

**Not verified:** owner manual testing, physical phones, Safari/Firefox, human screen readers, official maps/source rights/field surveys, process-kill chaos/large-campus throughput, production penetration/TLS/load/backup restoration or remote GitHub Actions. Completion commit `485f3758a33d5ac316a5febe6dc4eaa4e1083925` and both checkpoints are pushed. The actual 2B1 `gh pr create` then failed with `Post "https://api.github.com/graphql": Forbidden` (exit 1), returning no PR URL. No merge occurred. Git HTTPS pushes work. Prepared body: `docs/reviews/milestone-2b1-pr.md`; [compare/open the PR](https://github.com/shagatron/SCNS/compare/feat%2Fmilestone-2-admin...feat%2Fmilestone-2-imports?expand=1). The cloud startup draft is saved for future review; no new environment snapshot was published.

## M2B1 unfinished verification checkpoint — 7 October 2026 (Asia/Kolkata)

The implementation follows pushed backend checkpoint `790bc4a` on `feat/milestone-2-imports`. The remaining local UI/cache-refresh work is being preserved in an explicitly unfinished checkpoint. Executed and passing: `make check build test-unit test-integration test-migrations validate-dataset` (**35 Python unit, 49 real PostGIS integration, 14 frontend tests**), and `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e` (**28 desktop/mobile tests**, including the original ten public-navigation regressions). No skips or remaining failures in those runs. Initial browser selector and stale-catalog-cache failures were fixed and rerun successfully.

`python scripts/cloud-build.py` built both images. Compose migration/startup, worker `once`, empty-volume retention cleanup, built route/private-path/protected-endpoint smoke and an anonymous built admin browser check passed. Main Gate → Library stayed 256.88m over three edges on release `4eb587e6-5607-48ed-a8ca-f5c0d8f1c505`; fresh login had zero alerts and exactly one session check. Import-service SHA-256 matched inside/outside the API image. Full authenticated journeys ran against isolated source API/Vite/worker, not the built stack.

A new committed-lease/retention test in `backend/tests/integration/test_import_worker.py` is added but **not run yet**. Final active setup documentation, contract reproducibility evidence, milestone delivery and PR creation remain pending. See `docs/progress.md` for exact next steps. No 2B2 implementation, public deployment or credentials provisioning in the developer database occurred.

## M2A admin session follow-up — 7 October 2026 (Asia/Kolkata)

The inspection issue is fixed on `feat/milestone-2-admin`, based on `bdbc2c4`. A fresh anonymous `/session` 401 now resolves to a stable logged-out query result, without an expiration notice. Previously, the global 401 event cleared/recreated that same observed query and incorrectly displayed “Your session ended”. A known session rejected on recheck or a protected request still ends, cancels pending admin work, and removes private data. Anonymous focus/reconnect events do not initiate new checks. Successful login and deliberate logout reset the notice; cancelled older checks cannot override a newer login. Public query data is retained.

| Executed check | Result |
|---|---|
| Original-code regression reproduction | The fresh-visit test failed on the unwanted session-ended alert with the previous UI/API restored; fixed files were restored afterward |
| `make check` | Ruff/format, TypeScript and ESLint passed on final source |
| `make build`; final `cd frontend && npm run build` | Vite and Python compilation passed; final lazy admin bundle built |
| `make test-unit`; final `cd frontend && npm test` | **21 Python unit + 14 Vitest tests passed**, including 7 session lifecycle regressions |
| `make test-integration` | **28 passed**, including server expiry, revocation, disabled-user, Origin/CSRF and campus-permission checks |
| `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e` | **22 passed**: 12 admin + 10 original public journeys, desktop and 360px mobile; no failures/skips in final suite |
| `python scripts/cloud-build.py`; `docker compose up -d --wait api frontend` | Images built and local stack healthy; frontend serves the fix |
| Headless Chromium against the built nginx app | `/admin` reached network idle, showed normal login with no alert, made exactly one session request, and made no additional request on focus |
| `git diff --check` | Passed |

The new frontend tests cover fresh anonymous/StrictMode behavior, known-session 401 handling, private-data cleanup while preserving public data, protected-request invalidation, cancellation of a pending older session check, CSRF 403 without logout, renewed login, quiet deliberate logout, and network errors without false expiry claims. Browser regressions use actual server logout outside the UI to revoke an established session, then verify focus recheck, one end notice, re-login and quiet logout. Admin traces remain disabled and passwords/tokens remain ephemeral.

During test development, a non-bubbling synthetic visibility event was sent to `document`, while TanStack Query listens on `window`; the fixture now dispatches at the correct target. A first run also overlapped a source edit and Vite hot reload. The final full run used stable source and passed all 22 journeys. The expected failing old-code reproduction is not counted among passing tests.

Backend authentication, cookies, expiry/revocation, throttles, permissions, CSRF and migrations were unchanged. No migration downgrade/rehearsal was repeated for this frontend-only fix; its prior evidence remains below. Physical-device/manual owner testing and remote Actions remain unverified. Existing GitHub API/PR access limitations are unchanged. No Milestone 2B work or public deployment occurred.

## Milestone 2A — 7 October 2026 (Asia/Kolkata)

This is the final local automated validation of the admin-only 2A slice, based on M0/M1 commit `86e1591`. Earlier failures were diagnosed and fixed before the results below; no failed/skipped case is counted as passed.

| Executed check | Observed result |
|---|---|
| `make check` | Ruff lint/format, TypeScript and ESLint passed |
| `make build` | Vite production build and Python compilation passed |
| `make test-unit` | **21 Python + 7 Vitest tests passed** |
| `make test-integration` | **28 real PostGIS tests passed**: 13 public/core regressions, 14 admin cases, 1 real concurrent-transaction case |
| `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e` | **18 passed**: 8 admin + 10 public journeys, split across desktop and 360×800 mobile Chromium; no skipped cases |
| `make test-migrations` | Fresh schema, downgrade to M1/re-upgrade through `0005_anchor_evidence`, canonical alias backfill, frozen protection, preserved active release/checksum and Alembic model alignment passed |
| Actual `bootstrap-admin --password-stdin` CLI on disposable migration database | First invocation succeeded, second rejected as already consumed; random credential was not printed |
| `make generate-api` with before/after SHA-256 comparison | OpenAPI, TypeScript and dataset schema reproduced byte-for-byte |
| `make validate-dataset` | 11 places, 13 nodes, 27 edges valid |
| `python scripts/cloud-build.py` | API and frontend images built; TLS/dependency verification remained enabled |
| Compose migration, startup and built nginx/API smoke | Healthy; admin lazy bundle served, admin session returned 401/no-store, private paths returned 404; public Main Gate → Library remained **256.88m / 3 edges** on release `4eb587e6-5607-48ed-a8ca-f5c0d8f1c505` |
| `git diff --check` and tracked/unignored file review | Passed; no local secret files, dependency trees, databases, build outputs or browser artifacts staged |

The permission tests cover all four campus roles, live revocation, foreign-campus/revision rejection, first-admin consumption, last-admin protection, durable account throttles, CSRF/Origin, hashed sessions, rotation/logout, expiry/disabled accounts and credential-free audit. CRUD tests cover all five entity types, same-revision references, visibility checks, delete/duplicate rollback, expected audit counts and unchanged public search/map/route results. Two simultaneous READ COMMITTED transactions using the same draft version produce exactly one commit and one 409 conflict. Affirmative step-free anchor edits require private evidence notes.

Browser tests use a reset `scns_e2e_test` database and isolated ports 8001/5174; they generate ephemeral credentials and never reuse the developer app. The admin journeys cover all five creation forms, place updates/deletion ordering, audit display, session logout, role-specific controls, user provisioning/role changes, preserved conflict input and explicit latest-version reconciliation. The admin state and public route state pass axe WCAG A/AA checks on both viewports. Admin traces/video/screenshots are disabled. The final full browser run took 55.5 seconds.

Initial browser failures were selector ambiguity in nested labels and identical anchor labels. Selectors now use accessible control roles, anchors show associated place names, and mutation buttons wait for current catalog data. The initial backend test compared volatile route IDs/timestamps and encountered a shared test-session identity-map cache; comparison now excludes only those volatile fields and draft reads refresh model state. These failures did not require suppressing assertions or weakening permission checks.

Current compressed build sizes: main JavaScript 103.61kB, lazy admin JavaScript 7.44kB and admin CSS 0.84kB, lazy map JavaScript 45.76kB. Admin code is not part of the public initial load. No large-campus throughput or production latency claim is made.

**Blocked/not verified:** GitHub REST and GraphQL requests returned `Forbidden`; `gh pr create` failed before returning any PR URL. Git HTTPS read/push is available, but opening the PR and observing remote Actions require GitHub API access or owner action. A ready PR body is in `docs/reviews/milestone-2a-pr.md`. Owner manual app testing, physical phones, Safari/Firefox, human screen readers, security penetration/load testing, SSO, production TLS/proxy configuration, backup/recovery and official campus field validation were not performed. No M2B/2C implementation or public deployment occurred. The built stack received smoke checks; the 18 full browser journeys ran against the isolated source API/Vite stack.

Upstream warnings remain non-failing: Starlette recommends moving its TestClient from `httpx` to `httpx2`; uv warns that the build helper’s `UV_NATIVE_TLS` spelling is deprecated; Playwright workers report conflicting color environment settings. No warning was suppressed to obtain a pass.

## Historical M0/M1 evidence

Run date: 6 October 2026 (Asia/Kolkata). This records executed checks on the synthetic dataset, not field verification. The original checkpoint is `007d87a` on `feat/milestones-0-1`; latest follow-up changes were retested as described below.

## Environment and commands

Debian Linux x86_64; Python 3.12.14 on host (3.12.15 API image), uv 0.12.19, Node 24.19.0, PostgreSQL 17/PostGIS 3.5 container, and system Chromium 151.0.7922.173 controlled by locked Playwright 1.63.0. Installed dependencies are frozen from committed locks.

| Executed check | Outcome |
|---|---|
| `make setup` | Passed frozen uv sync and root npm workspace `ci`; existing `.env` preserved |
| `make check` | Passed Ruff lint/format, TypeScript and ESLint |
| `make build` | Passed Vite production build and Python compilation |
| `make test-unit` | **21 Python tests + 7 Vitest tests passed** |
| `make test-integration` | **13 tests passed** against isolated real PostGIS `scns_test`; no skipped tests |
| `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e` | **10 tests passed** (5 desktop + 5 at 360×800 mobile viewport), including the built nginx/Compose stack |
| `make validate-dataset` | Validated 11 places, 13 nodes and 27 directed edges |
| `make generate-api` + Git diff for generated outputs | Passed; OpenAPI, TypeScript and JSON schema reproduce without changes |
| Fresh Alembic upgrade; test-only downgrade to base and re-upgrade through `0003_frame_dimensions` | Passed; development database untouched |
| `python scripts/cloud-build.py` | API + frontend images built with dependency/TLS verification intact |
| Compose one-off migration + two identical demo seeds | Passed; both seeds returned release `4eb587e6-5607-48ed-a8ca-f5c0d8f1c505` |
| Built frontend → nginx proxy → API → PostGIS functional request | Passed; Main Gate → Library: 3 connected edges, **256.88m**, **183.5s** baseline ETA |
| Built server private paths | `/data/raw/floorplans/private.pdf` and `/storage/uploads/private.pdf` returned 404 |
| Development launcher startup/shutdown | Passed: `make dev` reached API readiness and Vite; termination released both 8000/5173 and stopped child process groups |

No required automated suite was skipped. Python's test client reports an upstream Starlette deprecation warning recommending `httpx2`; the current locked `httpx` path passes. The deprecated ESLint 9 toolchain was upgraded to compatible supported ESLint 10 and its checks rerun. No warnings were suppressed or reported as test failures.

## What the tests establish

- Weighted shortest paths, directed asymmetry, cycles, disconnected anchors, same-place zero arrival, multiple anchors and invalid costs. Forty deterministic random graphs are independently checked against Floyd–Warshall, including every returned edge and total cost.
- Stairs, unknown accessibility, restricted paths and closures are hard exclusions when applicable. Unavailable step-free paths never fall back to stairs.
- PostGIS measures bent polyline length rather than endpoint distance. Longitude/latitude adapters roundtrip, image axes invert correctly, unknown calibration fails, mixed local frames fail, and indoor image bounds/dimensions are enforced.
- An edited bundle closing the short stairs path creates a new release and changes actual API route distance/edges. Old release rows stay frozen. Draft places do not appear in search/detail; cross-revision references and publication of a draft are rejected.
- Idempotent seeding and failed-import transaction rollback; public projection excludes restricted records in catalog/map/routing. Runtime errors are safe and correlated, route responses are `no-store`.
- Browser search → select → API computation → displayed polylines and text; keyboard route, no-route/same-place/step-free states, swap, no horizontal overflow at 360px, API recovery, empty search, failed-map fallback and offline request prevention.
- axe checked WCAG A/AA rules on both tested viewports with no violations in the tested state. This does not certify WCAG compliance or substitute for screen-reader/physical-device testing.

## Build measurements

Latest Vite output (gzip): app JavaScript **103.49kB**, lazy Leaflet/map chunk **45.76kB**, application CSS **4.16kB**, map CSS **6.36kB**, HTML **0.36kB**. Combined compressed initial-plus-map assets are approximately **160.1kB**, below a provisional 200kB budget for this slice. No large-campus latency/load claim is made.

## Diagnosed setup failures and corrections

- Home cache paths were read-only: use workspace/temporary uv/npm/Docker caches.
- PostGIS extension-owned tables initially appeared during migration generation: reflection excludes non-application tables; no extension tables were dropped. Spatial indexes are explicitly created once. Fresh upgrade and downgrade/reapply verify the final migration.
- Browser download host was denied by policy: use the already-installed Chromium. No network policy was broadened, TLS disabled or artifact checks bypassed.
- Duplicate Playwright installations and an old Vite process caused initial browser failures: one npm workspace lockfile, server restart, strict port selection and group-based development-process cleanup fixed the cause. Complete journeys subsequently passed against development and built servers.
- Isolated Docker builds could not resolve the configured proxy or use its trust chain: `scripts/cloud-build.py` forwards existing proxy names and temporarily mounts the existing CA bundle. Both images and their functional startup subsequently passed.

## Not run / not claimed

GitHub Actions execution has not been inspected remotely; its equivalent local checks passed. Safari/Firefox, physical phones, human screen-reader testing, throttled-network/load benchmarks, official basemap provider access, institution field routes, real accessibility surveys, production backup/restore and public deployment were not run. No official campus data was available. Those are later milestone/field obligations, not substituted by synthetic test results.
