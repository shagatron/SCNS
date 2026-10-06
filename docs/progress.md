# Project progress

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

## Unfinished at checkpoint / exact next steps

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

Pending commit/push at the time this file was prepared. The outcome will be updated after the Git operation; no push is claimed yet.
