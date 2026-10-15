# Update the MUJ diagnostic and dataset wording safely

This update changes diagnostic tooling and notices, **not MUJ's prepared data**. It preserves the v1 manifest/source receipts, imported records and owner edits. No correction bundle exists to apply. **Do not rerun `setup-muj-osm.ps1`, import an upsert, recreate the draft, or publish MUJ for this update.** No password is needed by the offline diagnostic. Normal admin login remains required to inspect drafts.

The owner's Windows campus/draft are reported as `afcf4f1a-635f-563b-af5b-3d7efd2ed84c` / `d1a8bb10-cd34-4fe3-905b-53996334dd40`. They are not assumed to exist in the cloud database. Existing accounts, `.env`, original/private uploads, volumes, drafts, releases, QR markers and restrictions are retained. Run from your existing SCNS folder with Docker Desktop using Linux containers.

## Complete PowerShell update

```powershell
$ErrorActionPreference = 'Stop'
function Invoke-ScnsStep {
    param([Parameter(Mandatory=$true)][scriptblock]$Action)
    & $Action
    if ($LASTEXITCODE -ne 0) { throw "SCNS command failed (exit $LASTEXITCODE). Stop and inspect the output." }
}
Invoke-ScnsStep { git status --short }
if (git status --porcelain) { throw 'Preserve/commit local changes before switching. Nothing reset.' }
Invoke-ScnsStep { git fetch origin feat/muj-connectivity-review }
$scnsReviewBranch = git branch --list feat/muj-connectivity-review
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect local branches.' }
if ($scnsReviewBranch) {
    Invoke-ScnsStep { git switch feat/muj-connectivity-review }
} else {
    Invoke-ScnsStep { git switch -c feat/muj-connectivity-review FETCH_HEAD }
}
Invoke-ScnsStep { git pull --ff-only origin feat/muj-connectivity-review }
Invoke-ScnsStep { docker compose build api frontend }
Invoke-ScnsStep { docker compose stop api frontend import-worker }
Invoke-ScnsStep { docker compose up -d --wait db }
# Normal migration command; no new migration in this update, expected head0016.
Invoke-ScnsStep { docker compose run --rm --no-deps api alembic upgrade head }
Invoke-ScnsStep { docker compose up -d --wait --no-build api frontend import-worker }
Invoke-ScnsStep { docker compose exec -T api alembic current }
Invoke-ScnsStep { docker compose ps }
Invoke-RestMethod 'http://localhost:5173/api/v1/health/ready'
Start-Process 'http://localhost:5173/admin'
```

Do not use `down -v`, seed/reset/bootstrap, discard local changes, or remove a volume. API/frontend are briefly stopped for the normal migration/start sequence; no new database tables, automatic imports, source approvals or publications occur. If a command fails, stop and keep its output; existing data remains, and later commands should not be run blindly.

## Exact manual checks

1. Sign in with your existing owner account. Under **Assigned campus**, select **Manipal University Jaipur (OSM preparation)**. Under **Selected draft**, select the existing reported draft`d1a8bb10-cd34-4fe3-905b-53996334dd40`, verifying it is yours and still editable. If absent, stop and inspect; do not recreate/import to force this test.
2. Choose **Outdoor graph**. Under **Graph quality**, choose start **Hostel Entrance**, destination **GHS Entrance**, preference **Shortest**, then **Compute draft test route**. Expected23.62m/3stored edges, with **“Draft-only computed Dijkstra preview. Not published; source and field-verification status must be reviewed.”** No synthetic assertion on MUJ. Existing node/edge evidence still identifies OSM/no field verification.
3. Change destination to **Faculty Block Entrance**: expected163.28m/6edges. University Entrance→Hostel Entrance, Hostel Entrance→Central Library, and verified-step-free Hostel Entrance→GHS Entrance should still have no eligible route. No field-access or accessibility certification is implied.
4. **Validate saved graph** on an otherwise unchanged v1 draft: expected0errors/111warnings. Owner edits can legitimately change counts/warnings/routes; investigate differences, never overwrite the edits. Do not acknowledge warnings or submit review merely to match this evidence.
5. Select **Demo Campus** and an existing demo draft if available; Main Gate→Library remains256.88m/3edges and its draft notice explicitly says **Synthetic campus; invented data**. Do not create a draft solely to test the wording if none is desired.
6. Public `http://localhost:5173/`: only released campuses (the reported state has Demo Campus), synthetic label and **Step-free · synthetic verification only** remain. Search **books**, choose **Route to Library**, use **Main Gate**, shortest walking route, **Find walking route**: expected257m/4min. MUJ stays absent/unpublished. A real published campus would use **Step-free · verified access only**; this task does not publish MUJ to demonstrate that label.
7. Open `docs/data/muj-connectivity/README.md` and the two SVGs. All29components have sizes/source IDs; all34unanchored places are listed. Solid coloured paths are current preparation. Dashed red subway/corridor lines are **excluded OSM review candidates, not newly applied paths**. Read [the evidence collection list](../data/muj-connectivity-review.md#prioritized-owner-evidence-collection) before collecting anything. No sign printing/scanning/physical GPS/accessibility is verified by these checks.

## Optional: reproduce diagnostics offline with Docker

This is **preview only, no apply step**. Uses the exact original, not a downloaded replacement. No services/accounts/database or credentials are needed. It writes only under ignored`data/staging/`, separate from private retained original and committed preparation. The app image from the update above must exist.

```powershell
$scnsOsmFile = Join-Path $env:USERPROFILE 'Downloads\map (1).osm'
if (-not (Test-Path -LiteralPath $scnsOsmFile -PathType Leaf)) { throw 'Set $scnsOsmFile to the original attached export.' }
if ((Get-FileHash -LiteralPath $scnsOsmFile -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'd4b902b01fe944acb3161026679dabbab4898d6952bee22d7019f15fd15748de') { throw 'Original checksum differs; do not substitute a changed export.' }
$scnsDiagnosticOutput = Join-Path (Get-Location).Path 'data\staging\muj-connectivity-review'
New-Item -ItemType Directory -Force -Path $scnsDiagnosticOutput | Out-Null
Invoke-ScnsStep { docker run --rm --network none --mount "type=bind,source=$scnsOsmFile,target=/input/source.osm,readonly" --mount "type=bind,source=$scnsDiagnosticOutput,target=/output" scns-api python -m app.cli.muj_diagnostics /input/source.osm --output /output }
Start-Process (Join-Path $scnsDiagnosticOutput 'components.svg')
Start-Process (Join-Path $scnsDiagnosticOutput 'subway.svg')
```

Expected: **Verified29components; diagnostics only, no database or preparation writes.** Outputs`diagnostic.json`, `README.md`, `components.svg`, `subway.svg`; safe rerun reproduces identical bytes for this pin. XML/checksum/preparation mismatches fail. No proposed draft correction is prepared/applied, no v2 records are silently substituted, and no deletion/upsert is performed.

Source development equivalent from repository root:

```bash
cd backend
UV_CACHE_DIR=/tmp/scns-uv-cache uv run --frozen python -m app.cli.muj_diagnostics ../data/raw/muj/source.osm --output ../data/staging/muj-connectivity-review
UV_CACHE_DIR=/tmp/scns-uv-cache uv run --frozen pytest -q tests/unit/test_osm_conversion.py tests/unit/test_muj_diagnostics.py
cd ..
make check build test-unit
make test-db
cd backend
TEST_DATABASE_URL=postgresql+psycopg://scns:scns_local@localhost:54329/scns_test UV_CACHE_DIR=/tmp/scns-uv-cache uv run --frozen pytest -q tests/integration/test_muj.py tests/integration/test_admin_graph.py tests/integration/test_graph_concurrency.py tests/integration/test_imports.py
DOCKER_CONFIG=/tmp/scns-docker PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium UV_CACHE_DIR=/tmp/scns-uv-cache uv run --frozen python -m tests.browser_runner muj.spec.ts graph.spec.ts navigation.spec.ts qr.spec.ts
cd ..
DOCKER_CONFIG=/tmp/scns-docker python scripts/cloud-build.py
DOCKER_CONFIG=/tmp/scns-docker python scripts/smoke-publication-containers.py
DOCKER_CONFIG=/tmp/scns-docker python scripts/smoke-3c-demo-containers.py --muj
```

Integration command requires `TEST_DATABASE_URL` pointing to the dedicated test database (default`postgresql+psycopg://scns:scns_local@localhost:54329/scns_test`); never use the developer database as a test target. Browser/container runners enforce their disposable `_e2e_test` database naming and retain development volumes. Do not overlap browser runners on5174 or smoke DB-network attachments with integration runs. Commands are development verification, not an instruction to reset the owner's data. No migration/model/contract changes here; previous migration rehearsal remains applicable, and generated contracts are checked for no drift.

Actual cloud results and owner-reported Windows results are separately recorded in [verification](../testing/verification.md); the PowerShell sequence above was not executed on Windows by the agent. Independent source review, access clarification, route/entrance survey and explicit future publication remain separate actions.
