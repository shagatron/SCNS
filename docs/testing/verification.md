# Verification evidence

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
