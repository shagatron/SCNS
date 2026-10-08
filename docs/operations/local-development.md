# Local service operations

`make setup demo dev` prepares local development and runs API, frontend and the private import worker. Stop Compose `api frontend import-worker` before source development; database workers must share the same storage root. `make containers` builds API and nginx/frontend images; the README has explicit Compose migration/seed commands. PostGIS uses a named volume; API/import worker share a separate private source volume. Start built services with `docker compose up -d --wait api frontend import-worker`. Stop services with `docker compose stop` without removing data. Never use `docker compose down -v` on data you need to retain.

`GET /api/v1/health/live` checks process liveness; `GET /api/v1/health/ready` checks a real PostGIS query and the migrated schema. Readiness does not require demo seeding: an empty database has an honest empty-campus UI. Migrations are controlled steps; API workers do not migrate or seed at startup. The source host and containers share the same localhost-published development database when run on this machine.

Use `.env.example` for development settings. `DATABASE_URL` and `TEST_DATABASE_URL` are server-only. Tests reject database names not ending `_test`. Setup and seeding never reset developer data. `make test-e2e` and `make test-migrations` explicitly reset their dedicated `_e2e_test` and `_migration_test` databases; do not store valuable data in them. If a future migration is destructive, supply explicit backups/recovery first.

No public deployment, TLS/domain, hosting account, paid provider, institutional approval, asset publication, production backup or restoration drill has occurred. These are M5 gates. Production mode refuses startup. Database and source-asset backups must eventually be consistent with release pointers and separately versioned closures; do not treat a database-only dump as a verified full service backup.

In constrained cloud filesystems, Make uses writable temporary uv/npm cache directories. `python scripts/cloud-build.py` uses a writable Docker configuration directory, forwards proxy variables by name, resolves that configured proxy into the build network and mounts existing CA trust through BuildKit secrets. It is needed for this workspace's isolated Docker builds; standard local builds use Compose directly. The installed `/usr/bin/chromium` can be selected with `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`; no verification bypass is needed. Public browser traces/screenshots are generated under `frontend/test-results` and ignored. Admin traces, screenshots and video are disabled. See [admin setup, permissions and test isolation](admin.md).

Outdoor graph updates require `make migrate` (or the built API migration command) through `0008_outdoor_accessibility`. Keep existing volumes/uploads/.env. See [graph operations](graph-editor.md) for exact update commands, per-tab recovery, limits and stale-edit reconciliation. No graph worker or publication service is added.

## M2C update

Exact-content validation, independent review, public artifacts, atomic publication and explicit rollback are available on `feat/milestone-2-publication`. Draft workflows remain private; submitted revisions lock edits and must be returned to draft before changes. Follow [publication operations and data-retaining Windows Docker Desktop updates](publication.md). Existing volumes, .env, accounts and public seed release IDs remain intact.

## M3A floorplan update

Draft floors, private PDF/PNG/JPEG processing and evidence-bound calibration are available. The existing import worker also handles floorplan jobs; migrate through `0012_floorplans` before using the new images. [Floorplan workflow, limits and exact data-retaining Windows PowerShell update](floorplans.md) preserves .env/accounts/volumes/active release. Indoor tracing/connectors/routing remain unfinished 3B/3C.

Milestone3C indoor/mixed routing documentation: [data contract](../data/indoor-routing.md), [data-preserving Windows update and manual fixtures](../operations/indoor-routing.md). The earlier3A/3B milestone descriptions above describe those delivered slices; enabled reviewed3C floors now add explicit routing capability. Current3C verification is recorded separately in progress/testing evidence.

## M4A QR update

QR inventory and confirmed stored-node route starts use migration0015_qr and current published nodes. Follow [the exact data-preserving Windows update, synthetic inputs and expected results](qr-markers.md). `.env`, accounts, drafts, release pointers and upload/database volumes stay intact; no seed/bootstrap/draft publication is needed to update. `PUBLIC_APP_URL` configures canonical signage; default local loopback HTTP is a demo exception, nonlocal origins requireHTTPS. [QR contract](../data/qr.md), [remaining M4 slices](../product/milestone-4-plan.md).

## M4B restrictions update

Migration0016_closures adds initially empty operational history/version tables. Use [complete data-preserving Windows commands and exact outdoor/lift manual cases](closures.md); do not run seeds/bootstrap/demo helpers or publish drafts to update. Existing worker/image services are reused. [Restriction API, temporal and privacy contract](../data/closures.md) documents conservative scheduling and explicit operator-verified reopening. Actual4B Windows/device/physical checks remain unverified until owner-reported separately.
