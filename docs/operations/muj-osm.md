# Local MUJ OSM setup and staged draft import

The cloud and Windows databases are separate. This updates your existing local installation and **adds a distinct, unpublished MUJ campus**. It does not rename Demo Campus, copy synthetic indoor data, reset/seed data, create accounts/passwords, remove volumes, approve sources or publish. Existing accounts, `.env`, uploads, drafts, releases, QR markers and restrictions stay in place.

You need Docker Desktop running Linux containers, the existing SCNS checkout, an existing **system administrator** account for one of your campuses, and the original attached `map (1).osm`. Keep it in Downloads; if saved elsewhere, substitute its full path. Do not save passwords in this script, command history, environment variables or files. The container prompts through a terminal with hidden password entry and logs out at the end.

## Exact PowerShell update and first import

Open PowerShell **in your existing SCNS repository folder**. Preserve any local edits first; these commands stop if they find changes. They do not reset or discard anything. Run:

```powershell
$ErrorActionPreference = 'Stop'
function Invoke-ScnsStep {
    param([Parameter(Mandatory=$true)][scriptblock]$Action)
    & $Action
    if ($LASTEXITCODE -ne 0) { throw "SCNS command failed (exit $LASTEXITCODE). Stop and inspect the output." }
}
Invoke-ScnsStep { git status --short }
if (git status --porcelain) { throw 'Preserve/commit local changes before switching. Nothing reset.' }
Invoke-ScnsStep { git fetch origin feat/muj-osm-import }
$scnsMujBranch = git branch --list feat/muj-osm-import
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect local branches.' }
if ($scnsMujBranch) {
    Invoke-ScnsStep { git switch feat/muj-osm-import }
} else {
    Invoke-ScnsStep { git switch -c feat/muj-osm-import FETCH_HEAD }
}
Invoke-ScnsStep { git pull --ff-only origin feat/muj-osm-import }
$scnsOsmFile = Join-Path $env:USERPROFILE 'Downloads\map (1).osm'
if (-not (Test-Path -LiteralPath $scnsOsmFile -PathType Leaf)) { throw 'Put the attached map (1).osm in Downloads, or set $scnsOsmFile to its full path.' }
& .\scripts\setup-muj-osm.ps1 -OsmPath $scnsOsmFile
if (-not $?) { throw 'Setup stopped; retain its progress and inspect the reported error.' }
Invoke-ScnsStep { docker compose ps }
Invoke-ScnsStep { docker compose exec -T api alembic current }
Invoke-RestMethod 'http://localhost:5173/api/v1/health/ready'
Start-Process 'http://localhost:5173/admin'
```

The one setup/import command, once on this branch:

```powershell
.\scripts\setup-muj-osm.ps1 -OsmPath (Join-Path $env:USERPROFILE 'Downloads\map (1).osm')
```

Pinned MUJ JSON/GeoJSON files use repository `eol=lf` attributes so Windows `core.autocrlf=true` cannot invalidate their checksums. Do not open/save the original export with an editor that changes its bytes. `git check-attr eol -- data/muj/batch-001.json` should report `lf`.

It builds API/frontend from frozen locks, stops application services, starts the retained database, runs normal `alembic upgrade head`, restarts API/frontend/real import worker, then starts the interactive helper. There is no new schema migration in this integration; existing installations still need to be on0016. No bootstrap, seed, `down -v`, volume removal or publication occurs.

Enter your existing system-administrator username and hidden password. The helper verifies/reproduces the pinned original conversion before any campus provisioning. It creates/reuses one audit-identified MUJ campus and one specific draft. Campus creation, owner role grant, initial draft and **unapproved** OSM coverage source registration are one transaction. The source, converter and full preparation checksums are pinned; conflicting existing MUJ code/provenance or reviewed/frozen preparation stops without overwrite. A different user must have an explicitly assigned MUJ system-administrator role to resume; no privilege is silently inherited just because they administer another campus.

For each of **three batches**, the real worker produces a preview and the helper prints its job ID, counts and draft version. Open `/admin` in a browser, sign out/in if it was already open, select **Manipal University Jaipur (OSM preparation)** under **Assigned campus**, select the draft UUID printed by the helper, and choose **Data imports**. Inspect the complete paginated preview and **Download error report** (including warnings). Only after inspection type **APPLY** into PowerShell for that batch. This applies solely to drafts using normal validation, version checks, transaction and actor audits. It does not acknowledge release warnings or make any source approval/publication decision. Do not edit the same draft during the sequence; stale edits stop with a conflict rather than overwrite input.

Expected clean first run: additions400,400,306; all invalid/conflict counts0;51building records,55destinations,290nodes,688directed edges,21anchors. No synthetic floor/floorplan/QR/tracing/cost data is copied. Final saved graph validation has0errors and actionable warnings requiring review. It computes five **software-only** draft route checks, writes their outcomes and graph diagnostics privately to `/app/storage/private/muj/latest-validation.json`, and stops without review submission, approval or release publication. Distances are calculated by stored graph traversal, not fixed by this helper.

## Interruptions and reruns

After the original has been retained successfully, rerun with or without `-OsmPath`:

```powershell
.\scripts\setup-muj-osm.ps1
```

Exact committed jobs are recognized without duplicate writes, extra versions/audits or another APPLY prompt. Uploaded/parsing jobs are polled; completed uncommitted previews are refreshed and must be inspected/confirmed again. A new unrelated edit makes a stale preview fail; no auto-rebase/overwrite. Successfully applied earlier batches remain when later work stops. Failed/cancelled jobs, exhausted worker attempts, changed source/preparation, foreign ownership or a submitted/frozen draft require explicit investigation in **Data imports**, not an automatic replacement or reset. If the initial source-copy step was interrupted, supply the original file again. Always resume with the same owner when possible; a different uploader creates separately audited jobs, and manual mapping/policy changes can intentionally prevent exact original submission replay.

The helper never automatically retries invalid imports as upserts. Do not change policies merely to suppress a real conflict. Download row diagnostics, inspect the relevant source ID and preserve the editor's work before choosing an explicit correction. Current per-upload5MiB/2,000rows,30s processing/60s child timeout and normal quotas apply. Each bundle is atomic; all three together are a resumable preparation. Do not publish partial data.

Inspect retained evidence (public OSM-derived content and draft diagnostics, no credentials):

```powershell
docker compose exec -T api python -c "from pathlib import Path; print(Path('/app/storage/private/muj/latest-validation.json').read_text())"
docker compose logs --tail 40 import-worker
```

Do not expose `/app/storage` over a web server, attach a private original to a public issue or print environment variables. Import history/audits are available through normal campus-scoped admin screens.

## Exact manual viewing and routing checks

1. Sign in at `http://localhost:5173/admin`; select **Manipal University Jaipur (OSM preparation)** and the helper's draft. Under **Data imports**, all three jobs should be **committed**. Rerunning the helper should identify each committed batch without duplicate records. A clean first draft is version1/edit-version5 (initial1 + source1 + three applies); ordinary later edits legitimately change that value.
2. Choose **Outdoor graph** and **Fit draft campus**. Expect real WGS84 geography near **longitude75.56°,latitude26.84°**, academic paths to the east and hostel paths to the west. No demo geometry near0°,0° appears. This existing editor displays draft paths/nodes/places/anchors and the enclosing display extent; the exact two campus coverage polygons and building footprints are preserved in the source/catalog, not an automatically downloaded basemap. Select a node/edge to inspect its original source IDs/evidence and complete stored polyline. Do not save edits just to run these checks.
3. **Validate saved graph**: expect0errors/111warnings (not truncated), warnings for disconnected components/unanchored destinations/unconnected crossings/unknown accessibility as applicable. These are mapping/review work, not automatically acknowledged. The raw preparation report has29weak components; no academic↔hostel connection is asserted.
4. **Draft route start = Hostel Entrance**, **Draft route destination = GHS Entrance**, **Draft route profile = Standard shortest**, then **Compute draft test route**: expect **23.62m over three stored OSM edges** (software result23.624997727885383m). Use the exact verified distance/edge count in [verification evidence](../testing/verification.md); this is a software result, not a surveyed route measurement.
   Also try **Hostel Entrance → Faculty Block Entrance**, Standard shortest: expect **163.28m over six stored edges** (software result163.28135622236027m), using the retained mapped hostel-road loops.
5. Change start to **University Entrance**, destination to **Hostel Entrance**, same profile: expect **No eligible draft route**. Their mapped components are disconnected in this conservative preparation. No invented cross-road/subway shortcut should appear.
6. Start **Hostel Entrance**, destination **Central Library**, same profile: expect **No eligible draft route** because the Library has no justified entrance anchor. Its display point remains searchable in draft catalog; do not promote it into an entrance.
7. Start **Hostel Entrance**, destination **GHS Entrance**, profile **Verified step-free**: expect **No eligible draft route**. Unknown accessibility does not become verified from OSM wheelchair tags.
8. In draft **Catalog**, inspect real **Central Library**, **Academic Block -3** and **Lecture Hall Complex (LHC)** destinations. No synthetic rooms or invented floorplans/floors/connectors should exist for MUJ. Room/level descriptors remain quarantined in `data/muj/report.json`.
9. Open the public homepage in another tab. MUJ **must not** appear in the public campus selector until a separately reviewed publication. Select existing **Demo Campus**, manual **Main Gate → Library**, Standard shortest/metric. The unchanged synthetic baseline computes256.88m/three stored edges, UI257m/4min; existing Windows indoor, QR, restrictions and GPS remain in that campus only.

Actual Windows/Docker Desktop and physical campus walking/accessibility checks are **not claimed** by cloud automated tests. Read [source/scope/attribution/counts and publication prerequisites](../data/muj-osm.md). Independent MUJ source and exact-content release review remain required; this task does not publish or deploy.

## Developer verification commands

```bash
make check build test-unit test-integration test-migrations
make generate-api
cd backend
DOCKER_CONFIG=/tmp/scns-docker PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium UV_CACHE_DIR=/tmp/scns-uv-cache uv run --frozen python -m tests.browser_runner muj.spec.ts navigation.spec.ts imports.spec.ts admin.spec.ts graph.spec.ts
cd ..
DOCKER_CONFIG=/tmp/scns-docker python scripts/cloud-build.py
DOCKER_CONFIG=/tmp/scns-docker python scripts/smoke-3c-demo-containers.py --muj
DOCKER_CONFIG=/tmp/scns-docker python scripts/smoke-publication-containers.py
```

Only test runners reset their explicitly disposable test databases. Owned built test containers share an owned temporary private directory so the actual worker can read staged files. Cleanup removes only those owned test resources/files, never retained volumes. Normal setup/import touches no test database and never resets your developer dataset. See the verification log for actual counts and failed-run corrections rather than assuming every documented command has passed on every platform.

## Existing imported drafts: connectivity/wording follow-up

If you already completed the three batches, use [the connectivity-review update](muj-connectivity-review.md). It preserves this exact v1 preparation and existing draft: **no setup-helper rerun, correction import, deletion/upsert, review approval or publication**. Read the [exact-ID source gap report](../data/muj-connectivity-review.md) before changing access/boundary/floor assumptions. The owner's completed Windows import/validation/routes are recorded separately from automated evidence; the UUIDs identify that Windows database, not the cloud developer database.
