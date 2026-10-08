# Smart Campus Navigation

A working outdoor and indoor navigation demo built with React, TypeScript, Vite, Tailwind, TanStack Query, Leaflet, FastAPI, SQLAlchemy, Alembic, PostgreSQL and PostGIS. Milestones 0, 1, admin/import/graph/review slices 2A–2C and indoor floorplan foundations 3A, visual same-floor tracing 3B and indoor/mixed routing 3C, plus Milestone4 QR (4A) and closure/lift-outage (4B) slices, of the [master specification](docs/product/master-spec.md) are implemented. See the [requirements checklist](docs/product/requirements-checklist.md) and [verification report](docs/testing/verification.md) for scope and evidence.

**Demo Campus is wholly synthetic.** Its coordinates near (0°, 0°), buildings, paths, access conditions and accessibility evidence are invented. It is not the owner's campus and must not be used for real navigation. Public navigation requires no account, paid services, API keys or external map tiles. Administrator accounts are explicitly provisioned; there is no public deployment.

## What works

- Public directory and search by name, code, category and aliases; place details and pagination.
- Responsive phone/desktop route planner, manual starts/destinations, swap, clear, selectable map markers, fit-route control and map-free text directions.
- Heap-based Dijkstra over **stored directed graph edges**, selecting the cheapest eligible combination of entrance anchors. PostGIS measures the complete path polylines; baseline walking ETA uses a configurable 1.4 m/s speed.
- Honest handling of one-way paths, closed/restricted edges, isolated destinations, unmapped entrances, same-place arrival and unknown step-free accessibility. The step-free example tests synthetic eligibility only.
- Database-backed draft/release separation, frozen rows protected by triggers, atomic active-release selection, release IDs on responses and stale-release errors.
- Campus-scoped admin login, one-time bootstrap, dashboard, private draft catalog CRUD, optimistic concurrency and append-only audit at `/admin`. See [admin setup and workflow](docs/operations/admin.md).
- Private staged CSV/JSON/GeoJSON imports with field mapping, row diagnostics, change previews, stable IDs, explicit upsert, idempotent retries and atomic audited draft application.
- Visual outdoor draft graph editing and exact-content independent validation/review/publication/rollback.
- Same-floor and cross-floor public routes with floor switching, release-pinned reload, conservative step-free and fastest-supported estimates; unknown distance/ETA stay explicit. See [indoor routing and Windows updates](docs/operations/indoor-routing.md).
- QR inventory, installation verification, revocation/reassignment, printable SVG/PNG/PDF signs and explicit confirmed outdoor/indoor starts. See [QR workflow and Windows update](docs/operations/qr-markers.md).
- Draft floors, private isolated PDF/PNG/JPEG page processing, masks, responsive local preview and evidence-bound calibration with independently approved sanitized immutable display assets. Reviewed floor capabilities, explicit stairs/lifts/ramps/entrances and mixed indoor/outdoor routes are available; see [3A workflow and Windows updates](docs/operations/floorplans.md).

The supplied repository contained no C code. `legacy/c-prototype/` records that fact and is reserved for the original prototype if supplied.

For an existing installation, the [one-command unpublished synthetic 3C setup](docs/operations/synthetic-3c-demo.md) prepares a separate demo draft using the real worker and your existing owner/reviewer accounts, preserving existing mapping and the public release.

## Local development

Prerequisites: Docker Engine/Desktop with Compose v2, Python 3.12 or 3.13, `uv` (tested 0.12.19), Node 24 (minimum 22.12), npm, Make, Bash. Dependency versions are locked in `backend/uv.lock` and the **root** npm workspace `package-lock.json`.

From the repository root:

```bash
make setup                # frozen Python dependencies, npm ci, preserve/create local .env
make demo                 # start PostGIS, apply migrations, explicitly seed Demo Campus
make dev                  # API + frontend + private import worker; Ctrl-C stops all
```

On your own machine open `http://localhost:5173`. The API runs on port 8000, interactive API docs are at `http://localhost:8000/docs`, readiness is `/api/v1/health/ready`, and PostGIS is on localhost:54329. These are local addresses, not a published site. In a cloud workspace use its supported browser/port access tooling. No onboarding preview is created.

Alternatively use three terminals: `make api`, `make web` and `make worker`. Stop Compose `api`, `frontend` and `import-worker` before source development so only workers sharing the same private storage serve a database. To stop PostGIS without deleting its data: `docker compose stop db`. The named volume survives restarts; no reset/drop is performed by normal setup.

The commands can also be run explicitly:

```bash
docker compose up -d --wait db
cd backend
uv sync --frozen
uv run --frozen alembic upgrade head
DEMO_ENABLED=true uv run --frozen python -m app.cli.dataset seed-demo ../data/demo/campus.json
uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
# In another terminal from repository root:
npm ci
npm run dev --workspace frontend -- --host 127.0.0.1
```

## Full stack in Compose

This serves the built frontend through nginx and proxies `/api` to FastAPI. Migrations and seeding are explicit one-off steps, never per-worker startup side effects.

```bash
docker compose up -d --wait db
docker compose build api frontend
docker compose run --rm --no-deps api alembic upgrade head
docker compose run --rm --no-deps api python -m app.cli.dataset seed-demo ../data/demo/campus.json
docker compose up -d --wait api frontend import-worker
```

Stop host `make dev` processes first because Compose uses the same ports. Compose binds ports to loopback and uses **local development credentials only**. Production mode intentionally refuses startup until the deployment milestone is completed. The API and bounded import worker share a private named storage volume; originals are outside nginx and never published.

## Test and build

```bash
make check                # Ruff lint/format, TypeScript, ESLint
make build                # frontend production build + Python compilation
make test-unit            # Python algorithms/data/coordinates + Vitest components
make test-integration     # provision scns_test, migrate it, run real PostGIS/API tests
make test-migrations      # reset dedicated scns_migration_test; rehearse fresh/upgrade migrations

# One-time standard browser installation:
cd frontend && npx playwright install --with-deps chromium && cd ..
make test-e2e             # reset scns_e2e_test; isolated API/web/worker and private storage

# This cloud workspace already has Chromium; use this instead of downloading:
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e

make generate-api         # regenerate OpenAPI, JSON schema, checked-in TypeScript contracts
make containers           # build both runnable container images
```

Browser tests run desktop Chromium and a 360px mobile viewport. Integration tests require `TEST_DATABASE_URL` with a database name ending in `_test`; each test uses rolled-back transactions. They never reset development data. If using your own database server, provision a separate empty `_test` database with PostGIS extension permissions and override the URL. Browser tests reset a dedicated database named `scns_e2e_test`, generate ephemeral administrator credentials and run separate API/web servers on ports 8001/5174. They never reuse developer services. Admin browser traces, video and screenshots are disabled to avoid retaining authentication data. See [the test isolation details](docs/operations/admin.md#repeatable-verification).

The cloud environment has read-only home caches. Make directs uv/npm caches to `/tmp`. For direct commands set `UV_CACHE_DIR=/tmp/scns-uv-cache` and `npm_config_cache=/tmp/scns-npm-cache` if needed. For container builds **in this cloud workspace**, use `python scripts/cloud-build.py` in place of `docker compose build api frontend`: it resolves the already-configured proxy for the isolated build and mounts existing CA trust temporarily. No credential values are printed or copied into images, and TLS/lockfile verification stays enabled. On a normal local Docker installation, the standard Compose build command works without this helper.

## Data and configuration

Read [data/README.md](data/README.md), the [data dictionary](docs/data/dictionary.md) and [architecture](docs/architecture/design.md). `.env.example` documents active settings. `VITE_*` settings are intentionally public; never put secrets there. A permitted basemap URL **and attribution** may be supplied to Vite; default blank values make no tile requests. Basemaps are not preloaded or cached for offline use.

```bash
make validate-dataset
make validate-dataset DATASET=/absolute/path/to/outdoor-bundle.json
# Create a revised synthetic release after editing a COPY of the fixture:
make seed-demo DATASET=/absolute/path/to/modified-demo.json
```

Validation performs no database writes. The demo seed command only accepts `DEMO_ENABLED=true`, `is_demo=true`, code `DEMO`, and name `Demo Campus`. The first identical seed is a no-op; an edited bundle creates a new immutable revision/release and atomically advances the public pointer. Existing releases remain frozen. Repeating an old bundle does not roll back the current release. This is a **local synthetic fixture importer**. Use the private staged imports and independent review workflow for authorized data; do not reseed an existing installation during routine updates.

## Next milestone and limitations

Milestone **2A** delivers campus-scoped admin authentication, catalog CRUD, audit and optimistic concurrency. The [one-time `bootstrap-admin` command](docs/operations/admin.md) is working. Milestones **2B1/2B2** deliver staged CSV/JSON/GeoJSON imports, the outdoor draft graph editor, graph diagnostics and draft route tests. **2C** delivers exact-version independent review, publication/rollback and approved asset projection. **3A** delivers private floorplan processing, draft floors and calibration; **3B** delivers canonical indoor destinations/explicit doors and the same-floor visual graph editor; **3C** delivers explicit connectors, entrances and indoor/mixed routing. Milestone4A adds QR lifecycle/signs/confirmed starts; Milestone4B adds live restrictions; location and saved/offline packs remain planned later slices. Real-data `import-dataset`, `export-release`, and backup/restore commands will be delivered with their relevant milestones.

Indoor floorplan foundations are delivered in 3A; same-floor room/corridor tracing is delivered in 3B; connectors and indoor navigation are delivered3C; QR is slice4A; live closures and lift outages are slice4B. Geolocation4C, reports4D and saved-route offline/PWA4E remain planned. [Closures/Windows update/manual checks](docs/operations/closures.md) document the separate operational overlay and conservative scheduled window; estimated ends never reopen paths. Recurring opening hours and time-dependent queues remain unsupported. No real campus accessibility, physical path accuracy, load benchmark, screen-reader certification or deployment is claimed. Official maps and ownership/licensing decisions remain external inputs. No code license has been chosen on the owner's behalf; see [CONTRIBUTING.md](CONTRIBUTING.md).

## Staged draft imports (2B1)

See [the import setup and workflow guide](docs/operations/imports.md) and [executable import-v1 templates](data/templates/import-v1/README.md). `make dev` now starts the private DB-backed import worker with API/frontend; Compose requires `docker compose up -d --wait api frontend import-worker`. Imports never publish and public navigation stays on the existing release.

## Outdoor draft graph editor (2B2)

See [graph update/startup instructions, editing controls, recovery and concurrency](docs/operations/graph-editor.md). Node, paired directed-edge and entrance edits remain private drafts. Width/slope/steps/surface are unknown until provided; geometry changes never automatically certify accessibility. Per-tab recovery autosaves local input, while saving to the server is explicit. Graph validation and Dijkstra test routes do not publish.

Milestone 2C adds exact-version validation/review, independent approval, immutable public artifacts, atomic publication and audited rollback. [Workflow and Windows Docker Desktop update commands](docs/operations/publication.md) preserve existing installation data; no deployment is authorized. Source/projection templates: [publication-v1](data/templates/publication-v1/README.md).

## Indoor floorplan foundations (3A)

[Data-retaining Windows PowerShell/Docker Desktop update and complete admin workflow](docs/operations/floorplans.md), [reference pixels/calibration/release contract](docs/data/floorplans.md), and [executable floorplan-v1 templates](data/templates/floorplan-v1/README.md). The existing import worker also processes floorplans. Originals stay in protected DB storage; only exact independently approved sanitized display PNGs are release assets. All 3A floors are explicitly display-only, including calibrated ones; no indoor route or physical survey claim.

## Indoor visual editor (3B)

[Data-preserving Windows update and complete synthetic manual walkthrough](docs/operations/indoor-editor.md), [typed local coordinate/catalog/topology/review contract](docs/data/indoor-editor.md), [API schema/example](data/templates/indoor-v1/README.md), and [invented 600×400 room/door/corridor fixture](data/demo/indoor/synthetic-ground.json). Independently approved sanitized plans/calibration precede metric tracing; explicit directions-only mode preserves unknown scale. Draft saves require exact selected plan and global revision version. The 3B slice leaves rooms catalog-only; the 3C capabilities below enable eligible reviewed floor/connector routes. Public navigation continues using the immutable published release.

Milestone **3C**: [data contract](docs/data/indoor-routing.md), [data-preserving Windows update and manual fixtures](docs/operations/indoor-routing.md). The earlier 3A/3B milestone descriptions above describe those delivered slices; enabled reviewed 3C floors now add explicit routing capability. Current 3C verification is recorded separately in progress/testing evidence.
