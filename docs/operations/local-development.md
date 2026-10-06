# Local service operations

`make setup demo dev` prepares local development. `make containers` builds API and nginx/frontend images; the README has explicit Compose migration/seed commands. PostGIS uses a named volume. Stop services with `docker compose stop` without removing data. Never use `docker compose down -v` on data you need to retain.

`GET /api/v1/health/live` checks process liveness; `GET /api/v1/health/ready` checks a real PostGIS query and the migrated schema. Readiness does not require demo seeding: an empty database has an honest empty-campus UI. Migrations are controlled steps; API workers do not migrate or seed at startup. The source host and containers share the same localhost-published development database when run on this machine.

Use `.env.example` for development settings. `DATABASE_URL` and `TEST_DATABASE_URL` are server-only. Tests reject database names not ending `_test`. No routine command resets data. If a future migration is destructive, supply explicit backups/recovery first.

No public deployment, TLS/domain, hosting account, paid provider, institutional approval, asset publication, production backup or restoration drill has occurred. These are M5 gates. Production mode refuses startup. Database and source-asset backups must eventually be consistent with release pointers and separately versioned closures; do not treat a database-only dump as a verified full service backup.

In constrained cloud filesystems, Make uses writable temporary uv/npm cache directories. Use `DOCKER_CONFIG=/tmp/scns-docker` for a Docker build cache location if the normal home directory is read-only. The installed `/usr/bin/chromium` can be selected with `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`; no verification bypass is needed. Browser traces and screenshots are generated under `frontend/test-results` and are ignored.
