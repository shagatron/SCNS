# Draft validation, review, publication and rollback (M2C)

Use the existing checkout. Application-level publication switches local public data; this is not public deployment. Real campus rights/survey inputs remain external. Demo Campus is still invented and labelled synthetic. Never infer real accessibility from its fixtures.

## Update an existing Windows Docker Desktop installation

Open PowerShell **in your existing SCNS repository folder**, with Docker Desktop using Linux containers. Inspect `git status --short` first. If switching branches is blocked by local edits, preserve/commit them; do not reset or discard them. The project name remains `scns`, retaining its existing named database and private-import volumes.

```powershell
git status --short
git fetch origin
git switch feat/milestone-2-publication
git pull --ff-only origin feat/milestone-2-publication
docker compose stop api frontend import-worker
docker compose build api frontend
docker compose up -d --wait db
docker compose run --rm --no-deps api alembic upgrade head
docker compose up -d --wait --no-build api frontend import-worker
docker compose ps
Invoke-RestMethod http://localhost:5173/api/v1/health/ready
Start-Process http://localhost:5173/admin
```

These commands preserve `.env`, existing accounts/drafts/releases, `postgres-data` and `private-imports`. Do **not** run `down -v`, volume removal, database reset or seeding during an existing-install update. No new password is configured. Continue using your existing administrator; provision a **different** campus reviewer through Users and roles when needed. The publisher/approver cannot be a contributor to the submitted revision, even with system administrator permission.

If an image build or migration fails, stop and retain logs; do not start mismatched old workers against a partly upgraded schema. Alembic runs transactionally. Inspect `docker compose logs --tail 100 api import-worker` after startup (do not share secrets). `docker compose stop api frontend import-worker` stops application processes without deleting data. Ordinary startup after a successful update is `docker compose up -d --wait --no-build db api frontend import-worker`.

New migrations are `4c587825d90b` and `0010_release_order` after `0008_outdoor_accessibility`. It adds review/source/artifact/action tables and extends entity protection to review-locked revisions; it does not rewrite existing releases or consume a bootstrap. Existing release rows gain an unambiguous monotonic publication order (independent of draft version); trusted synthetic seed release IDs and checksums remain valid, with `artifact_checksum=null` because historical seed releases have no generated public artifact. Database/schema downgrade is a development rehearsal on disposable databases, not a Windows rollback procedure. An application map rollback uses the authorized workflow below and does not downgrade code/schema.

## Workflow

1. Create/select a draft from the active release. Catalog, graph and staged imports stay draft-only. Save graph/local changes before review; submitting locks edits.
2. Open **Review and releases**. Inspect the parent diff, projection counts, sources and applied import metadata. Register rights, provenance and public attribution for the intended audience. A different reviewer inspects and approves each proposed source/derivative. An authorized/clearly synthetic approved source is required. Restricted originals never become display assets.
3. Optionally attach a bounded `.json`/`.geojson` original. Choose **Propose a sanitized outdoor display overlay** only for permitted outdoor vectors. The reviewer inspects the exact derivative and can download the original privately. Features need explicit `properties.public=true`; others are excluded. Only plain labels and Point/LineString/Polygon coordinates survive projection; arbitrary original properties are discarded. Image/PDF/floorplan conversion is M3. No URL fetching is supported.
4. Select distinct public start/destination places, expected standard and step-free outcomes, an optional upper distance bound and a reason. **Run authoritative validation** computes stored Dijkstra routes and combines catalog, canonical alias/search, import provenance, geometry/cost/boundary/frame/reference, physical direction pairs, entrance visibility/connectivity and accessibility/evidence checks. The two profiles are mandatory; expected no-route results need an explicit coverage reason. Every additional route fixture can be supplied through the API (maximum 50).
5. Fix blocking errors and revalidate. Material warnings (including unknown accessibility, legitimate disconnection/unmapped entrances, stale evidence and import provenance) need individual IDs and substantive reasons. The UI can apply a reviewed reason to all displayed warnings, then edit individual reasons. Submission cannot bypass errors. The reviewer records its own acknowledgements, not implicit acceptance of the submitter's reasons.
6. **Submit exact validated version for review**. The revision becomes `review`, locking entity writes at both API and DB levels. The review packet includes exact checksum/version, diff, errors/warnings, public counts, sources/derivatives and computed route evidence. A submitter can withdraw; a reviewer can reject (with notes), returning it to `draft` at a new version. Historical evidence/decisions remain. Any return/edit requires fresh validation/submission/approval; stale validation and old approval cannot publish.
7. An independent campus reviewer approves with notes and warning reasons. Submission status becomes `approved`; revision stays review-locked. Contributors include draft creators, catalog/graph editors, import appliers and source registrars/removers. System administrators have the same separation rule. Role/session/CSRF checks remain server-side and live. Revoked/inactive approval/source reviewers block publication.
8. **Prepare publication**, inspect the captured active release and exact approved version, then explicitly confirm. The operation freezes the revision, creates the canonical public artifact and release, records publisher/review/version/checksums, and moves the active pointer in **one transaction**. Failure in generation, writes or audit retains the prior pointer and approved draft state. Retries use the same action key and payload; they return the prior result without another release/audit. A changed payload/key collision or stale active pointer/version returns conflict.
9. Public search, directory, map and routing read one active frozen revision per REPEATABLE READ request. Frontend reads pin the selected release; maps/directory/routes reject stale expected IDs. On an active change, the UI clears earlier routes/selections, refreshes coherent destinations/map, and explains that a new route must be calculated. Online release metadata is rechecked every 30 seconds/on focus and immediately after a stale response. A failing refresh shows an error instead of mixing release data.
10. Inspect **Release history and rollback**. Download checksummed approved public JSON artifacts at immutable URLs. Choose an earlier eligible immutable release by publication order, supply a reason, prepare and explicitly confirm rollback against the captured current pointer. It changes only that pointer, preserves releases/artifacts/decisions and records an audit/action result. A foreign/current/later target, corrupt artifact or stale pointer fails without changing the active release. Legacy earlier trusted synthetic releases are eligible only for demo campuses. Rolling back never edits drafts or deletes data.

No live closures exist; overlay version is zero. M4 must add separate overlay reconciliation before closure-bearing releases can be rolled back. This delivery creates no closure table, reopen action, geolocation, QR, PWA, indoor editor or deployment.

## Storage, integrity and limits

Private source originals are bounded to **5MiB per registration and 100MiB per campus**, transactionally stored as protected PostgreSQL BYTEA with SHA-256; include the database in backups. They are not arbitrary filesystem URLs and do not affect the existing private import storage volume. Source registration takes a campus lock for quota/version consistency. Removing an unused source is an explicit audited draft operation; existing frozen copies remain immutable. Cloning a draft counts copied originals against the same campus quota and preserves approved source content and originals; changed sources must be replaced and independently reapproved. Source deletion/registration/approval consumes a draft version.

A complete full-dataset canonical checksum binds entities, coordinates, costs, visibility, source rights/provenance/derivatives and source approvals. `Release.checksum` is that reviewed content checksum for new releases; original seed checksums remain historical input hashes. Public artifact checksum hashes a **separate explicit projection** with sorted keys, UTF-8, compact JSON and finite numbers, excluding private originals/notes/evidence/identities, restricted entities/bindings and internal review/import data. Approved derivative geometry and attribution are included. This public checksum can be independently verified from exact download bytes. The release metadata exposes both, plus immutable artifact URL; active changes never mutate those URLs. Frozen revision/entity/release/artifact triggers and append-only validation/decision/action/audit triggers enforce immutability for application DB users (superusers remain trusted).

Publication supports at most 15,000 records per layer. Complete graph diagnostics must fit 500 findings and spatial warning categories below their 100-pair budget; otherwise validation blocks and requests a smaller/repaired dataset. Overlay originals have at most 500 features, 500 positions per line/ring and 10 polygon rings. Review displays the latest 30 validation/submission records and release history the latest 100; older append-only DB records remain. No large-campus load benchmark, real source license adjudication, physical survey or human accessibility certification is claimed.

## Verification commands

Linux source contributor checks remain `make check build test-unit test-integration test-migrations test-e2e generate-api validate-dataset`; use system Chromium via `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e` here. Tests guard disposable database suffixes, use ephemeral accounts/credentials, isolate publication campuses per viewport, and disable authenticated traces/screenshots/video. They never publish/rollback the developer dataset.

Windows can run core backend checks through the built API image against a **separate disposable test database**, not `scns`. Run static frontend checks/build on a host with pinned Node 24/npm dependencies, or use CI. Do not substitute deleting your development volumes for the documented isolated harness. Actual executed results and built-app browser verification are recorded in [verification](../testing/verification.md).
