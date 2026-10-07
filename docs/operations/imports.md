# Staged campus-data imports (Milestone 2B1)

Imports are private draft operations. Public search, map and Dijkstra routing continue reading the frozen active release. Upload, preview, validation and application never create a release or change its pointer. Demo Campus and every supplied example remain wholly synthetic, with WGS84 coordinates near 0,0; they are not official maps or accessibility evidence.

## Setup and startup

From the repository root:

```bash
make setup
make demo                 # local PostGIS, migrate, explicitly seed synthetic data
make dev                  # API, frontend AND bounded import worker; Ctrl-C stops all
```

Follow [admin setup](admin.md) to bootstrap a chosen administrator password once. No default account/password is installed. In separate terminals you may run `make api`, `make web` and `make worker`. All three must share `DATABASE_URL` and `STORAGE_ROOT` (host default `../storage`, relative to backend).

Containers:

```bash
make containers
# This cloud workspace uses python scripts/cloud-build.py if proxy/CA forwarding is needed.
docker compose run --rm --no-deps api alembic upgrade head
docker compose run --rm --no-deps api python -m app.cli.dataset seed-demo ../data/demo/campus.json
docker compose up -d --wait api frontend import-worker
docker compose logs --tail=30 import-worker
```

API and worker share the `private-imports` named volume, outside nginx's web root. Do not remove data volumes to restart. No migrations, bootstrap or seed execute automatically at service startup. The worker has no public port or external provider.

## Complete admin workflow

1. Sign in, select the assigned campus, and create/select a draft. Open **Data imports**. Editors and campus system administrators can upload/apply; reviewers can inspect history/previews/reports; operations has no import access. Server checks every request, including downloads, against current roles and campus scope. Origin and session CSRF checks cover unsafe actions.
2. Download a CSV/JSON/GeoJSON template. Supply explicit rights/authorization and source/version/survey notes. Use the campus's exact code/timezone, `import-v1`, `WGS84_degrees_and_metres` and outdoor `[longitude, latitude]`. Existing campus boundaries remain authoritative. Geometry outside the target boundary is rejected.
3. Choose the format/default entity, optional renamed-column mappings and duplicate policy. Upload a nonempty UTF-8 file. The API accepts only plain `.csv`, `.json`, `.geojson` filenames and raw `application/octet-stream` bodies, generating its own private storage name. There is no URL importer, arbitrary file fetch or public original-file endpoint.
4. The durable worker transitions `uploaded → parsing → preview_ready`. Inspect additions, updates, unchanged records, conflicts, invalid rows, warnings, current/proposed fields, exact source rows and preview draft version. Download the diagnostics CSV. No draft catalog/graph changes occur during the savepoint dry run.
5. Correct the source and upload a new batch, or adjust mapping/policy and reprocess. Duplicate identities/codes require explicit resolution. A new source file is a new job; mapping/policy can change within an uncommitted job. Failed processing can retry at most three times. Queued/failed/uncommitted jobs can be cancelled.
6. Validate a clean preview, then confirm **Apply batch to draft**. All records, stable-ID bindings, draft version, job completion and audits commit together. Any late failure rolls everything back. Concurrent edits reject a stale preview; refresh it, inspect again, revalidate and explicitly apply. A repeated apply returns the already-committed job without writing again.
7. History shows jobs across the assigned campus, their target draft, uploader/applier IDs, checksum, state transitions and attempt count. Per-record and batch audits link the actor to the job, external IDs and before/after data. No import action publishes.

Default bounds: **5 MiB/file, 2,000 rows, 30 seconds of validation, 60-second worker child wall limit, three processing attempts and 100 MiB private upload storage**. `IMPORT_BYTE_LIMIT` (up to 10 MiB), `IMPORT_ROW_LIMIT` (up to 10,000), `IMPORT_PARSE_SECONDS` (up to 120), and `IMPORT_STORAGE_LIMIT` are server settings. nginx and the UI deliberately retain a 5 MiB limit; operators increasing the backend limit must also deliberately adjust those local bounds. Existing graph limits also apply. Split larger datasets into coherent bundles and review each draft application. These limits have functional tests; throughput/load targets are not measured.

## Format and identifier contract

Executable templates: [`data/templates/import-v1/`](../../data/templates/import-v1/README.md). The older root templates include preparation-only future indoor/QR fields; they are not all executable imports. Supported now: outdoor frames, buildings, places, nodes, directed edges, departments, department-place links, aliases and anchors. Floors, rooms, connectors, image/PDF conversion, graph editor and reviewer publication remain outside 2B1.

- JSON uses one versioned bundle containing `records: [{entity, external_id, data, existing_id?}]`. Related records can appear in any order; processing orders references before dependents. This is the staged interchange format, distinct from the frozen demo seed `dataset-v1` CLI format. Use the documented import bundle, not a demo-seeding command, for real draft data.
- CSV imports one entity, with one record per row and unique headers. `external_id` is required. Field mapping maps target field → source column. Fields containing geometry or arrays are JSON, using ordinary CSV quoting. Use JSON bundles when several dependent files need one atomic transaction. For curved edges the full LineString is required in the quoted `geometry` cell; scalar distance columns cannot replace geometry. CSV row numbers include the header; JSON/GeoJSON numbers are 1-based record/feature indices.
- GeoJSON uses an RFC 7946 `FeatureCollection` with no legacy `crs`. Properties contain the same identity/entity fields; feature geometry maps to building `footprint`, place/node `point`, or edge `geometry`. A geometry may not mix indoor pixels with WGS84. References must already exist in the draft or be included in the same supported bundle.
- External IDs are stable, case-sensitive 1–120 characters `[A-Za-z0-9_.:-]`, unique per entity in the batch. New logical UUIDs are deterministic from campus + entity + external ID; immutable draft-scoped bindings retain explicit adoption across later imports and draft cloning. Reusing an external ID for a different logical record is rejected. Two external IDs cannot target one record within a batch. UUID references may identify existing records only in the target draft; non-UUID references use external IDs/bindings.
- Default `create_only`: new identities add; identical existing content is unchanged; differing content conflicts. `upsert` explicitly permits replacing the complete typed fields of the same stable identity. It is not a partial patch and never deletes catalog records. Required fields and documented defaults apply. Department `place_ids` omitted from an existing department preserves its links; explicit lists replace links. Separate department-place rows add/update explicit associations. Existing codes never silently choose a target: add `existing_id` containing the intended current draft UUID to adopt a legacy/admin-created record, inspect the update and choose upsert when content differs.
- Submission `Idempotency-Key` is scoped to campus/uploader and binds exact checksum/options/target revision. Reusing it for different content is 409. The UI retains the key for an unchanged failed submission. Separate unchanged batches may still create history/audit entries and advance the draft version, but never duplicate logical records. Replayed application of the same job does not advance the version or repeat its audit.
- Edge length is computed by PostGIS from the **entire directed polyline**, ignoring no geometry and trusting no supplied scalar length. The file must declare `estimated` or `measured` distance status and evidence; synthetic examples use `estimated`. Verified step-free status needs evidence and is forbidden for stairs. Unknown status remains unknown; imports do not certify accessibility.

## Worker, retention and offline checks

The worker uses database row locks with `SKIP LOCKED`, commits a durable parsing lease, and processes one job in a child with a hard wall timeout. Lost leases become eligible after 180 seconds, up to three attempts. Application uses a locked job plus whole-draft conditional version write. Cancellation and remapping serialize against processing. Progress/state history and staging previews live in PostgreSQL; raw files are private, SHA-256 checked before every parse and written mode 0600. Parsing is bounded and never fetches URLs or executes data.

```bash
cd backend
uv run --frozen python -m app.cli.imports once
uv run --frozen python -m app.cli.imports validate \
  --file ../data/templates/import-v1/catalog-bundle.json \
  --options ../data/templates/import-v1/options.json
uv run --frozen python -m app.cli.imports cleanup --retention-days 30
```

Offline `validate` checks encoding/format/version/metadata/row bounds without writing to a database; staged preview is authoritative for typed rows, draft references, geometry, duplicate conflicts and concurrency. The existing `app.cli.dataset validate` validates old demo/interchange v1 bundles separately. Neither offline command applies or publishes.

Cleanup deletes original files of committed/cancelled jobs older than the retention period and unregistered orphan files older than that period; it retains job history, previews and audits. It never removes active/failed retryable sources. Configure a trusted-host schedule when appropriate; no scheduler or deployment was installed. Disk/database backup consistency and production malware scanning belong to deployment requirements. Confidential sources are never sent to external scanners/services.

## Verification commands

```bash
make check build test-unit test-integration test-migrations validate-dataset
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e
make generate-api
```

Browser tests run API/frontend/worker on a disposable `_e2e_test` database, random ephemeral accounts and a temporary private storage directory. Admin traces/screenshots/video remain disabled. Migration tests reset only `_migration_test`. Integration fixtures require `_test`; concurrent import tests use independent real transactions and remove only their unique test records (including a test-owner-only audit-trigger bypass during cleanup). Developer/public data is preserved. See [verification evidence](../testing/verification.md) for actual results and unverified limits.
