# Project progress

## Milestone 2A checkpoint — 6 October 2026

Branch `feat/milestone-2-admin` starts at `86e1591`. Authorized scope is now **Milestone 2A only**; Milestones 0/1 remain the baseline. No imports, map graph editor, review/publish workflow, operational closures or deployment are included.

Completed: migration for campus role grants, opaque hashed server sessions, durable login throttles, one-time bootstrap, normalized aliases/departments and append-only audit. Protected API supports draft copies, all five catalog CRUD types, version-conditional writes, role provisioning and campus-scoped reads. Public release pointers and projections are unchanged. Passwords use Argon2id; unsafe requests require allowed Origin and session-bound CSRF token.

Verified so far: 13 new PostGIS admin integration cases pass. The preceding combined run also passed all 13 existing integration cases; two new test assertions were corrected (volatile route metadata and stale fixture identity-map state). Backend Ruff and migration upgrade passed before tests were added. Generated OpenAPI/TypeScript contracts updated.

Unfinished: admin dashboard/forms are being connected, browser admin journeys and concurrent database transactions still need validation, final full lint/build/regression suite and migration roundtrip need running, setup/checklist/security docs need updating. No manual owner test or public deployment performed.

Exact next steps:
1. Complete `frontend/src/features/admin/` login, dashboard, catalog CRUD, conflict reconciliation, users/roles and audit interface.
2. Add isolated browser test database/ports and admin desktop/mobile journeys; add real concurrent write regression.
3. Run `make generate-api check build test-unit test-integration` and `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e`; fix failures. Check migration downgrade/reapply on a disposable test database.
4. Update setup, security, verification and requirements documents; commit/push final work and open an unmerged PR against the baseline branch if main does not yet contain it.

The backend checkpoint excludes unfinished frontend source files. No secrets, dependencies, databases or browser artifacts are staged.

## Milestones 0/1 history

Checkpoint: 6 October 2026 (Asia/Kolkata). Authorized scope: **Milestones 0 and 1** of `docs/product/master-spec.md`. Later milestones are not part of this delivery.

## Completed work

- Inspected the original repository/history: only README existed. No C prototype was supplied; `legacy/c-prototype/` records this and preserves the intended location.
- Built React/TypeScript/Vite/Tailwind/Leaflet frontend, FastAPI/Pydantic/SQLAlchemy backend, and Alembic/PostgreSQL/PostGIS persistence.
- Added synthetic data: 3 buildings, 10 public destinations plus 1 restricted place, 13 nodes, 27 directed edges and 11 anchors. No official campus geometry was invented.
- Implemented search/directory, details/filters/pagination, manual starts/destinations/swap, map polylines, text directions, mobile layout, error/no-route handling and baseline ETA.
- Implemented multi-source heap Dijkstra over stored graph edges. PostGIS measures complete directed polylines. Changed imported data changes actual routes; closed/restricted/stairs/unknown accessibility constraints are enforced.
- Added revision-scoped relationships, immutable releases, atomic active pointers, coordinate/calibration foundations, private upload spaces and data templates.
- Added dependency locks, generated API/schema contracts, Make commands, local Compose images, CI definition and setup/data/architecture/security documentation.

## Checks completed before this checkpoint

| Check | Observed result |
|---|---|
| Python unit tests | 21 passed |
| Real PostGIS/API integration tests | 13 passed |
| Frontend Vitest tests | 7 passed |
| Desktop + 360px mobile Chromium journeys | 10 passed, including keyboard and axe checks |
| Ruff, TypeScript, ESLint, Vite build, Python compilation | Passed |
| Fresh migrations and isolated test-database downgrade/reapply | Passed |
| Dataset validation and repeated seed | Passed |
| API/frontend container builds | Both built through the configured cloud proxy with verification enabled |

Since the full suite, a nullable indoor-frame dimension constraint/test, map resize refit, development-process cleanup and documentation were added. A subsequent container rebuild completed. Relevant checks for these changes remain next; earlier passes are not represented as a new final run.

## Work that remained at checkpoint

1. Checkpoint source/tests/docs on a working branch and push through existing GitHub access if supported. Exclude secrets, installed dependencies, database files, private input, build outputs and browser artifacts. Retain lockfiles and generated API contracts for reproducibility.
2. Validate the built Compose stack: run migrations, repeated synthetic seed, readiness and a functional route through nginx. Host servers were stopped to free ports 8000/5173; PostGIS remains running.
3. Rerun affected lint/build/unit/integration/browser checks, validate `make setup` and development startup/shutdown, and record final counts in `docs/testing/verification.md`.
4. Finish the requirements checklist and progress report, save reusable cloud startup instructions, and report any remaining limitations. No public deployment/publication is authorized.

From `/workspace/SCNS`:

```bash
docker compose run --rm --no-deps api alembic upgrade head
docker compose run --rm --no-deps api python -m app.cli.dataset seed-demo ../data/demo/campus.json
docker compose up -d --wait api frontend
make check build test-unit test-integration validate-dataset
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e
make generate-api
```

If images need rebuilding in this workspace, use `python scripts/cloud-build.py`. It forwards configured proxy variables by name and mounts existing CA trust as a BuildKit secret; it does not disable verification or write credentials into images. Standard Playwright download was blocked by network policy; installed Chromium ran all browser tests successfully.

## Subsequent milestones and external inputs

M2: scoped admin authentication, catalog editing, real staged CSV/JSON/GeoJSON imports, review/publication, concurrency and audit. M3: indoor floors/rooms/connectors. M4: QR, location, live closures, reports and PWA/saved routes. Official maps, source rights, surveys, owner/license decisions and field verification remain external inputs. They do not block the current synthetic outdoor slice. No paid services or public deployment have been used.

## Git checkpoint outcome

Checkpoint `007d87a` was created on working branch `feat/milestones-0-1` and successfully pushed to `origin/feat/milestones-0-1` on 6 October 2026. Secrets, installed dependencies, database files, raw uploads, caches, build output and browser artifacts were excluded. Lockfiles and generated API contracts were intentionally retained. The completion section below records validation performed after this checkpoint.

## Completion after checkpoint

Milestones **0 and 1 are implemented and verified**. The latest indoor-dimension constraint, map resize behavior and process cleanup were checked. Frozen dependency setup, lint/type/build, 21 Python unit tests, 13 real PostGIS integration tests, 7 frontend tests and 10 desktop/mobile browser tests passed. The browser suite also passed against the actual built nginx/Compose frontend/API stack. Fresh migration and downgrade/reapply through `0003_frame_dimensions` passed on the isolated test database.

Both images built with the cloud helper. The built server returned a real 3-edge route from Main Gate to Library (256.88m, 183.5s baseline ETA), returned 404 for private source paths, and preserved the release across repeated demo seeding. `make dev` startup/readiness and shutdown were exercised; both service process groups stopped and released their ports. The Compose app was restarted afterward and remains the running local stack.

Generated OpenAPI/TypeScript/schema artifacts reproduced without diff. Git ignore and credential-pattern checks confirmed that local `.env`, dependencies, caches, database files, raw uploads, traces and build output were excluded. The deprecated ESLint 9 version was updated to compatible ESLint 10. See `docs/testing/verification.md` for full evidence and unrun checks; all M0/M1 entries in the requirements checklist are accurate.

### Next steps

1. Run the current slice with `make setup demo dev` (stop the existing Compose `api`/`frontend` first if using host development). Or reuse the healthy local Compose services on port 5173.
2. Recheck with `make check build test-unit test-integration` and `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e` in this workspace.
3. Review the working branch. No merge, public deployment, paid service or environment publication was performed.
4. The **next implementation milestone is M2**: campus-scoped admin identity/roles, draft catalog/editor, staged real-data import preview and commit, validation/review/publication, audit and optimistic concurrency. Keep edits invisible to public APIs until review; use new real-campus IDs rather than renaming Demo Campus.
5. Owner can prepare authorized maps/rights/surveys using `data/README.md` and `data/templates/` while M2 is developed. These inputs do not block synthetic development. Indoor routes, QR, geolocation and offline saved routes remain M3/M4 work, as specified.

Reusable cloud configuration: `install_script` and `start_skill` were saved as an environment configuration draft. This saves instructions only; it does not publish the environment or deploy the app. To use a new reusable snapshot, review/save the draft in environment settings and publish the environment there. No runtime secret or network allowlist changes were added.
