# Milestone 2A administration

Milestone 2A adds local administrator identity and **private draft catalog editing**. The public directory, map and Dijkstra service keep reading their existing immutable active release. No admin endpoint publishes a release, imports files, edits graph paths, approves a review or creates live closures in this milestone.

## Setup and first administrator

From the repository root, install locked dependencies and migrate/seed the explicit synthetic campus:

```bash
make setup demo
cd backend
UV_CACHE_DIR=/tmp/scns-uv-cache uv run --frozen python -m app.cli.admin bootstrap-admin \
  --username campus-owner --display-name "Campus owner" --campus DEMO
```

The command prompts twice for a **new password of 12–128 characters** without echoing it. There is no default administrator or password. Choose a unique password. Passwords are Argon2id hashes; passwords are not accepted as command-line arguments or stored in Git. `--password-stdin` supports a trusted secure pipe (one line); do not put a literal password in shell history or commit it in a script.

Bootstrap is atomic and one-time across the database, guarded by a transaction advisory lock and an immutable consumed record. It fails if bootstrap has been consumed or any user already exists. It assigns `system_admin` to the specified existing campus only. Do not delete bootstrap records or reset the development database to provision more users.

Start with `make dev` from the repository root and open the app's `/admin` path. Sign in with the account just created. Use the dashboard's **Users and roles** section to create campus accounts and replace a member's campus roles. Changes take effect on the next request. Replacing roles replaces the complete set for that campus; other campuses are unaffected. Removing the last active system administrator is rejected.

For an existing user who needs another campus grant, a trusted host operator can run:

```bash
cd backend
UV_CACHE_DIR=/tmp/scns-uv-cache uv run --frozen python -m app.cli.admin grant-role \
  --username campus-owner --campus DEMO --role system_admin
```

Replace the campus code with an existing campus code when appropriate. This CLI requires trusted database access, adds one role idempotently, and audits the grant. An administrator of campus A cannot use the HTTP API to grant access in campus B. Global password resets, account deactivation UI, institutional SSO and recovery tooling are not part of 2A; do not imply they exist.

If using the built Compose stack, rebuild first; a running M1 image does not contain these features:

```bash
make containers
# In this cloud workspace use: python scripts/cloud-build.py
# Apply the new migration before starting the new API image:
docker compose run --rm --no-deps api alembic upgrade head
docker compose run --rm --no-deps api python -m app.cli.dataset seed-demo ../data/demo/campus.json
docker compose run --rm --no-deps api python -m app.cli.admin bootstrap-admin \
  --username campus-owner --display-name "Campus owner" --campus DEMO
docker compose up -d --wait api frontend import-worker
```

Skip bootstrap if already consumed. Host and Compose commands use the same local development database. Stop existing host services before starting Compose on ports 8000/5173, or stop Compose `api`/`frontend`/`import-worker` before `make dev`. Browser tests use separate ports and need neither stopped.

## Permissions delivered in 2A

All grants are campus-scoped; there is no implicit global system-administrator bypass.

| Role | Dashboard | Read drafts | Create/edit drafts | Campus audit | Campus users/roles |
|---|---|---|---|---|---|
| `editor` | Yes | Yes | Yes | No | No |
| `reviewer_publisher` | Yes | Yes | No | Yes | No |
| `operations` | Yes | No | No | No | No |
| `system_admin` | Yes | Yes | Yes | Yes | Yes |

Reviewer publication and operations closure capabilities are reserved for later milestones. Hiding controls is only a convenience: every API action checks a live session and the required campus grant server-side. Unknown and unauthorized campus requests return the same 403. A revision or related record from a different campus/draft cannot be used to cross the boundary.

## Catalog workflow

1. Select an assigned campus. The dashboard shows the current public release and permitted drafts.
2. **Create draft from published release** copies revision-scoped catalog, frames, nodes and edges with stable logical IDs. If no release exists, the new draft is empty. Graph nodes are read-only in 2A.
3. Select the draft and a catalog tab. Create, read, update and delete buildings, places, departments (with place associations), aliases and place anchors. References must be in that draft. Referenced buildings/places cannot be deleted until explicitly unlinked; all changes are audited.
4. Buildings accept WGS84 footprint coordinate rings as JSON, longitude first, with closed rings. Places use numeric longitude/latitude and a building selector. Anchors select existing stored graph nodes and default to unknown accessibility. Marking an anchor verified requires source/date/observation notes server-side; it does not create graph geometry or certify real paths.
5. Save using the version captured when the form opened. Every successful write increments the **whole draft's** edit version. This deliberately detects simultaneous edits even to different entities. Missing `If-Match` returns 428; stale versions return 409. Failed writes roll back both version and audit.
6. On conflict, input is preserved. Load the latest record for comparison, reconcile the input, explicitly accept that version, and save again. A deleted record cannot be updated. Switching sections/campus/draft or cancelling discards unsaved input. Reloading the page also discards it.
7. Audit records show actor, campus/revision/resource, timestamp, request ID and before/after data. They are append-only at the database layer. Passwords, session tokens and CSRF tokens are excluded.

Normalized alias rows are canonical for draft CRUD; the legacy alias JSON/search-text projection is synchronized within that draft for future release compatibility. Existing frozen rows and release checksums stay untouched. Draft checksums are invalidated (`NULL`) on edits; generating/validating a publishable checksum is later work. The trusted synthetic seed CLI remains an explicit local demo release generator, separate from this admin workflow.

## Session controls

Opaque random session tokens live only in scoped `HttpOnly`, `SameSite=Strict` cookies. Only SHA-256 token digests are stored in the database. Absolute expiry defaults to eight hours. Logout revokes the session server-side; signing in again from the same account/cookie rotates it. Account activity and roles are checked on each request. A fresh unauthenticated session check settles on the normal login screen. Only a session previously established by successful login or restoration can trigger the session-ended notice. Established sessions are rechecked on focus/reconnect; anonymous pages do not refetch on those events. Logout quietly returns to login. Session invalidation cancels pending admin queries and removes private admin data without deleting the observed session query or public cache. Cancelled older checks cannot replace a newer successful login. Admin responses have `Cache-Control: no-store`; the UI does not persist credentials/session state in local storage.

Unsafe requests require an exact allowed `Origin` and a session-bound CSRF header; login also requires Origin. Requests from unlisted port-forward/preview origins are intentionally rejected. Configure `ALLOWED_ORIGINS` with the exact browser origin when running through an approved local access tool. Do not use `*`. Local HTTP uses `SESSION_COOKIE_SECURE=false`; TLS deployment must use secure cookies. Production mode remains disabled pending the deployment milestone.

Login has durable per-account and per-peer-IP throttles. Default limits are five failed account attempts and thirty total attempts per peer IP per fifteen minutes; successful login resets the account counter. The server does not trust forwarded IP headers, so the local nginx/Vite proxy shares a conservative peer-IP bucket. Trusted proxy/client-IP design is a later deployment obligation. Authentication events are recorded without passwords; campus audit views show campus administrative changes, while unscoped login/logout events remain database operator evidence.

## Repeatable verification

```bash
make check build test-unit test-integration test-migrations
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e
make generate-api
```

`make test-e2e` provisions and **resets only `scns_e2e_test`**, migrates/seeds it, creates random ephemeral browser credentials, and starts isolated API/Vite processes on 8001/5174 plus the bounded import worker with temporary private storage. It never reuses a running developer server. A non-default `E2E_DATABASE_URL` must name a database ending `_e2e_test`; the database must already exist. Credentials are passed only through child-process environment, and admin traces/video/screenshots are disabled. The isolated browser runner sets `LOGIN_IP_LIMIT=100` because the enlarged suite shares one proxy IP; the application default remains 30 and backend throttle protections retain their regression tests. Public journey artifacts remain ignored under `frontend/test-results`.

`make test-migrations` resets only `scns_migration_test`, exercises fresh migration, downgrade to M1 and re-upgrade with frozen demo data, checks alias backfill, active release/checksum preservation, frozen protection and model/schema alignment. `MIGRATION_DATABASE_URL` must end `_migration_test`. Both test commands are destructive to their dedicated test databases; never point them at valuable data. Integration tests use `scns_test` with rollback isolation; the concurrent-write case commits uniquely named temporary records and removes them afterward.

For a focused browser rerun after provisioning test databases:

```bash
cd backend
UV_CACHE_DIR=/tmp/scns-uv-cache PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium \
  uv run --frozen python -m tests.browser_runner --grep "stale edit"
```

No official maps, field validation, owner manual app test, physical-device/assistive-technology verification or deployment is implied by these synthetic automated checks.

Staged data imports are delivered in 2B1. See [import permissions, formats, worker startup and transactional workflow](imports.md). Outdoor graph editing, diagnostics and draft route tests are delivered in 2B2; see [graph operations](graph-editor.md). Review/publication remains later work.
