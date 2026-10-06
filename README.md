# Smart Campus Navigation

A working outdoor navigation demo built with React, TypeScript, Vite, Tailwind, TanStack Query, Leaflet, FastAPI, SQLAlchemy, Alembic, PostgreSQL and PostGIS. Milestones 0 and 1 of the [master specification](docs/product/master-spec.md) are implemented. See the [requirements checklist](docs/product/requirements-checklist.md) and [verification report](docs/testing/verification.md) for scope and evidence.

**Demo Campus is wholly synthetic.** Its coordinates near (0°, 0°), buildings, paths, access conditions and accessibility evidence are invented. It is not the owner's campus and must not be used for real navigation. No paid services, API keys, public deployment, account or external map tiles are required.

## What works

- Public directory and search by name, code, category and aliases; place details and pagination.
- Responsive phone/desktop route planner, manual starts/destinations, swap, clear, selectable map markers, fit-route control and map-free text directions.
- Heap-based Dijkstra over **stored directed graph edges**, selecting the cheapest eligible combination of entrance anchors. PostGIS measures the complete path polylines; baseline walking ETA uses a configurable 1.4 m/s speed.
- Honest handling of one-way paths, closed/restricted edges, isolated destinations, unmapped entrances, same-place arrival and unknown step-free accessibility. The step-free example tests synthetic eligibility only.
- Database-backed draft/release separation, frozen rows protected by triggers, atomic active-release selection, release IDs on responses and stale-release errors.
- Private incoming-data directories, CSV/GeoJSON preparation templates, an executable versioned JSON validator and explicit idempotent demo seeding.

The supplied repository contained no C code. `legacy/c-prototype/` records that fact and is reserved for the original prototype if supplied.

## Local development

Prerequisites: Docker Engine/Desktop with Compose v2, Python 3.12 or 3.13, `uv` (tested 0.12.19), Node 24 (minimum 22.12), npm, Make, Bash. Dependency versions are locked in `backend/uv.lock` and the **root** npm workspace `package-lock.json`.

From the repository root:

```bash
make setup                # frozen Python dependencies, npm ci, preserve/create local .env
make demo                 # start PostGIS, apply migrations, explicitly seed Demo Campus
make dev                  # API + frontend; Ctrl-C stops these development processes
```

On your own machine open `http://localhost:5173`. The API runs on port 8000, interactive API docs are at `http://localhost:8000/docs`, readiness is `/api/v1/health/ready`, and PostGIS is on localhost:54329. These are local addresses, not a published site. In a cloud workspace use its supported browser/port access tooling. No onboarding preview is created.

Alternatively use two terminals: `make api` and `make web`. To stop PostGIS without deleting its data: `docker compose stop db`. The named volume survives restarts; no reset/drop is performed by normal setup.

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
docker compose up -d --wait api frontend
```

Stop host `make dev` processes first because Compose uses the same ports. Compose binds ports to loopback and uses **local development credentials only**. Production mode intentionally refuses startup until the deployment milestone is completed. No worker is included because M0/M1 have no background ingestion jobs.

## Test and build

```bash
make check                # Ruff lint/format, TypeScript, ESLint
make build                # frontend production build + Python compilation
make test-unit            # Python algorithms/data/coordinates + Vitest components
make test-integration     # provision scns_test, migrate it, run real PostGIS/API tests

# One-time standard browser installation:
cd frontend && npx playwright install --with-deps chromium && cd ..
make test-e2e             # seeds must already exist via make demo; starts API/web if absent

# This cloud workspace already has Chromium; use this instead of downloading:
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e

make generate-api         # regenerate OpenAPI, JSON schema, checked-in TypeScript contracts
make containers           # build both runnable container images
```

Browser tests run desktop Chromium and a 360px mobile viewport. Integration tests require `TEST_DATABASE_URL` with a database name ending in `_test`; each test uses rolled-back transactions. They never reset development data. If using your own database server, provision a separate empty `_test` database with PostGIS extension permissions and override the URL. Browser tests read the local demo and do not mutate its graph.

The cloud environment has read-only home caches. Make directs uv/npm caches to `/tmp`. For direct commands set `UV_CACHE_DIR=/tmp/scns-uv-cache` and `npm_config_cache=/tmp/scns-npm-cache` if needed. For container builds in this environment use `DOCKER_CONFIG=/tmp/scns-docker docker compose build api frontend`. Do not copy authentication files or disable TLS verification.

## Data and configuration

Read [data/README.md](data/README.md), the [data dictionary](docs/data/dictionary.md) and [architecture](docs/architecture/design.md). `.env.example` documents active settings. `VITE_*` settings are intentionally public; never put secrets there. A permitted basemap URL **and attribution** may be supplied to Vite; default blank values make no tile requests. Basemaps are not preloaded or cached for offline use.

```bash
make validate-dataset
make validate-dataset DATASET=/absolute/path/to/outdoor-bundle.json
# Create a revised synthetic release after editing a COPY of the fixture:
make seed-demo DATASET=/absolute/path/to/modified-demo.json
```

Validation performs no database writes. The demo seed command only accepts `DEMO_ENABLED=true`, `is_demo=true`, code `DEMO`, and name `Demo Campus`. The first identical seed is a no-op; an edited bundle creates a new immutable revision/release and atomically advances the public pointer. Existing releases remain frozen. Repeating an old bundle does not roll back the current release. This is a **local synthetic fixture importer**, not the authorized real-data import/review UI planned for Milestone 2.

## Next milestone and limitations

Milestone 2 adds campus-scoped admin authentication, CRUD, CSV/JSON/GeoJSON staged imports, outdoor editing, validation/review approval, audit, optimistic concurrency and publication/rollback tools. `bootstrap-admin`, `import-dataset` for real data, `export-release`, and backup/restore commands will be delivered with their relevant milestones; no placeholder command claims success today.

Indoor navigation/floorplans are Milestone 3; QR, geolocation, live closures, reports and saved-route offline/PWA support are Milestone 4. The present route policy uses static release state at request time and does not evaluate opening schedules. No real campus accessibility, physical path accuracy, load benchmark, screen-reader certification or deployment is claimed. Official maps and ownership/licensing decisions remain external inputs. No code license has been chosen on the owner's behalf; see [CONTRIBUTING.md](CONTRIBUTING.md).
