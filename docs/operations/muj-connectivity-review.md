# Update MUJ safely: versioned source correction and dataset wording

This update corrects notices, adds reproducible diagnostics and delivers a **separate versioned v2 source-segment correction**. Original v1 preparation/source receipts remain unchanged. Do not rerun`setup-muj-osm.ps1` or upload full v2 bundles over your existing draft. Use the guarded correction below: preview22operations, explicitly APPLY one normal authenticated graph transaction. No source/review approval or publication occurs. No automatic upsert/deletion of owner work.

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

## Recover the already-applied Windows correction (receipt bug)

The owner reported that APPLY committed, then `client.session["user"]["id"]` raised `KeyError: 'user'`. A subsequent owner-run `--plan-only` verified **already_applied, draft version6,20additions/2deletions**. This is owner-reported Windows evidence, not an inspection of that database by the agent. **Preserve that committed correction. Do not type APPLY again, rerun setup or reimport bundles.**

The actual authenticated login/session JSON has top-level `user_id`, `username`, `display_name`, `csrf_token`, `expires_at`, `grants`; there is no nested `user`. The fixed CLI validates the authenticated identity before any graph write. The full update block above rebuilds/restarts services without replacing data; this fix adds no migration. After that update, run this **read-only graph recovery** from the same repository PowerShell:

```powershell
$scnsMujDraft = 'd1a8bb10-cd34-4fe3-905b-53996334dd40'
Invoke-ScnsStep { docker compose run --rm --no-deps api python -m app.cli.muj_update --draft $scnsMujDraft --recover-receipt }
```

Enter the existing MUJ owner/editor username and hidden password. Do not use `-T`, pipe credentials or put passwords in arguments. Recovery never prompts APPLY and sends **no graph POST**. Normal login/logout still create/revoke a session; recovery creates only private local preview/verification files. It verifies all correction records/deletions, affected dependencies, pinned manifest and saved draft version. On the reported unchanged Windows state expect:

- `Correction already_applied: {'add': 20, 'update': 0, 'delete': 2}`. These counts describe the correction already present; **zero new graph operations** occur.
- `Verified already_applied at draft version 6; no graph writes.` Version6 stays6 unless a separate legitimate edit has occurred.
- A private `verification-v6-<manifest-prefix>.json` under `/app/storage/private/muj-updates/d1a8bb10-cd34-4fe3-905b-53996334dd40/`. Reruns safely refresh this verification file; existing application receipts/import jobs remain untouched.

The receipt has `receipt_type: state_verification`, `verified_by` (the current verifier), `graph_writes_this_run: 0`, saved version and manifest/record evidence. It deliberately has **no `requested_by` or `audit_request_id`**: recovery cannot establish the original application actor/request from current graph state. The original server audits remain authoritative; no new application audit or reconstructed evidence is inserted. A successful new application receipt separately uses the actual session `user_id` and POST response request ID.

If the correction is absent, partially applied, changed at an affected record/dependency, or source pins differ, recovery stops rather than repairing/overwriting anything. Unrelated owner edits are preserved and can legitimately advance the verified version. If private storage is unwritable, fix disk space/permissions without deleting retained files, then repeat **only `--recover-receipt`**. A failed receipt save after a successful graph transaction explicitly says the graph succeeded. An interrupted API response may also have committed: verify using the same read-only recovery command before any further decision. `--plan-only` remains preview-and-exit and does not save a verification receipt.

Optional receipt summary (no credential values printed):

```powershell
Invoke-ScnsStep { docker compose exec -T api python -c "from pathlib import Path; import json; p=max(Path('/app/storage/private/muj-updates/$scnsMujDraft').glob('verification-*.json'),key=lambda p:p.stat().st_mtime_ns); r=json.loads(p.read_text()); print(p.name); print({k:r[k] for k in ('receipt_type','state','revision_version','counts','graph_writes_this_run','evidence_limit')})" }
```

Reload the existing MUJ draft in admin: unchanged preparation has295nodes/700directed edges/22anchors, unpublished. Recovery neither approves sources nor publishes releases. The reported version6 is preserved; the cloud test fixtures use separate disposable versions, not this Windows draft.

## Exact manual checks

1. Before applying the optional correction below, sign in with your existing owner account. Under **Assigned campus**, select **Manipal University Jaipur (OSM preparation)**. Under **Selected draft**, select the existing reported draft`d1a8bb10-cd34-4fe3-905b-53996334dd40`, verifying it is yours and still editable. If absent, stop and inspect; do not recreate/import to force this test.
2. Choose **Outdoor graph**. Under **Graph quality**, choose start **Hostel Entrance**, destination **GHS Entrance**, **Draft route profile → Standard shortest**, then **Compute draft test route**. Expected23.62m/3stored edges, with **“Draft-only computed Dijkstra preview. Not published; source and field-verification status must be reviewed.”** No synthetic assertion on MUJ. Existing node/edge evidence still identifies OSM/no field verification.
3. Change destination to **Faculty Block Entrance**: expected163.28m/6edges. University Entrance→Hostel Entrance, Hostel Entrance→Central Library, and verified-step-free Hostel Entrance→GHS Entrance should still have no eligible route. No field-access or accessibility certification is implied.
4. **Validate saved graph** on an otherwise unchanged v1 or corrected v2 draft: expected0errors/111warnings. Owner edits can legitimately change counts/warnings/routes; investigate differences, never overwrite the edits. Do not acknowledge warnings or submit review merely to match this evidence.
5. Select **Demo Campus** and an existing demo draft if available; Main Gate→Library remains256.88m/3edges and its draft notice explicitly says **Synthetic campus; invented data**. Do not create a draft solely to test the wording if none is desired.
6. Public `http://localhost:5173/`: only released campuses (the reported state has Demo Campus), synthetic label and **Step-free · synthetic verification only** remain. Search **books**, choose **Route to Library**, use **Main Gate**, shortest walking route, **Find walking route**: expected257m/4min. MUJ stays absent/unpublished. A real published campus would use **Step-free · verified access only**; this task does not publish MUJ to demonstrate that label.
7. Compare `docs/data/muj-connectivity/README.md` (preserved v1) with `docs/data/muj-connectivity-v2/README.md` and their SVGs. Both inventories list29components; unanchored places decrease34→33. Solid coloured paths are current preparation. Dashed red subway/corridor lines are **excluded OSM review candidates, not newly applied paths**. Read [the evidence collection list](../data/muj-connectivity-review.md#prioritized-owner-evidence-collection) before collecting anything. No sign printing/scanning/physical GPS/accessibility is verified by these checks.

## Preview and apply the source-supported v2 draft correction

**For a v1 draft that has not yet received the correction only. The owner-reported version6 is already corrected: use read-only recovery above instead.**

Close/save any unrelated unsaved editor input first. This workflow does not touch other drafts/releases and never resets your data. It preserves unrelated owner edits; changed affected edges, existing endpoints, the new anchor's destination, ID collisions or manual partial changes stop for reconciliation. Do not undo your survey/edit merely to force a match. A frozen/submitted draft must follow normal review controls; this helper cannot unfreeze it.

In the **same existing repository**, after the update above:

```powershell
$scnsMujDraft = 'd1a8bb10-cd34-4fe3-905b-53996334dd40'
Invoke-ScnsStep { docker compose run --rm --no-deps api python -m app.cli.muj_update --draft $scnsMujDraft }
```

Enter your existing **MUJ editor or owner** username/password; password input is hidden. No default password, credential argument, saved secret or approval bypass. The helper prints a private preview path and waits. **Do not type APPLY yet.** It should propose20additions/0updates/2deletions:5new source nodes,14directed edges,1explicit entrance anchor;2superseded directions of source way1154145951 removed, replaced by source-vertex-split arcs. The source/preparation hashes, original values, all proposed values and reference ordering are in the preview. No clipping/proximity/Library/subway connection is invented.

While it waits, open a **second PowerShell in the same SCNS folder** and inspect the private preview:

```powershell
$scnsMujDraft = 'd1a8bb10-cd34-4fe3-905b-53996334dd40'
docker compose exec -T api python -c "from pathlib import Path; p=max(Path('/app/storage/private/muj-updates/$scnsMujDraft').glob('preview-*.json'),key=lambda p:p.stat().st_mtime_ns); print(p.name); print(p.read_text())"
if ($LASTEXITCODE -ne 0) { throw 'Preview unavailable; do not apply.' }
```

Match the filename/version to the first terminal's printed preview. Inspect every before/after geometry, the two explicit removals and dependencies. These are OSM/source records, not passwords; keep receipts/private notes out of public issues. If another operator generated a different preview, inspect the exact printed file instead of assuming the newest is yours. Then return to the first terminal and type **APPLY** only after review. Any other input stops without a write. `--plan-only` can be appended to the helper command for preview-and-exit; a subsequent run creates/rechecks a fresh preview and must be reviewed again.

The helper sends exactly that versioned patch through the normal graph API. Server permissions, Origin/CSRF, draft-wide If-Match, full combined-state validation, ordered deletes/creates, transaction and audits remain enforced. Source/content/independent approval and publication are untouched. The final response/receipt records the server audit request ID and requesting actor; every newly created graph audit carries the v2 manifest marker. Private preview/receipt files use restrictive permissions under the retained private volume; credentials are never written there. If the network/receipt write is interrupted, use `--recover-receipt` above: exact target state reports`already_applied` with no additional graph writes/version/audits and a verification-only receipt; original application audit evidence is not reconstructed. Other partial/manual differences stop. A different version before application requires a new preview/review, not automatic overwrite. The original v1 helper is refused on the corrected original draft and rechecks immutable correction history immediately before each pending-batch apply; If-Match protects a concurrent change after that check.

Expected otherwise unchanged result:51buildings/55destinations/**295nodes/700directed edges/22anchors**,29weak components/33unanchored; one edit-version increment (clean v1 version5→6),22normal actor audit events, no public MUJ release. Old C2/C17 join but another independent source run is retained; a lower component count is not the acceptance target. Original three import jobs/receipts stay unchanged, source remains unapproved and warnings unacknowledged.

Reload admin, reselect your MUJ draft, then **Outdoor graph**. University Entrance→**Mapped entrance10828149259** now has a computed shortest route (previously unanchored); use the exact label **Mapped entrance 10828149259** in the combobox. The five established checks in steps2–3 remain unchanged. Validate saved graph:0errors/111warnings on unchanged fixtures. Expected software result on unchanged v2: **513.10m/13stored edges** (actual513.0969783921546m), computed by stored-graph Dijkstra, never hardcoded by the helper. Public Demo remains257m/4min, MUJ absent. There is no new Library or cross-campus subway route and no verified step-free assertion.

## Optional: reproduce diagnostics offline with Docker

This diagnostic command is **read-only, with no apply step**; it is separate from the guarded draft correction above. Uses the exact original, not a downloaded replacement. No services/accounts/database or credentials are needed. It writes only under ignored`data/staging/`, separate from private retained original and committed preparation. The app image from the update above must exist.

```powershell
$scnsOsmFile = Join-Path $env:USERPROFILE 'Downloads\map (1).osm'
if (-not (Test-Path -LiteralPath $scnsOsmFile -PathType Leaf)) { throw 'Set $scnsOsmFile to the original attached export.' }
if ((Get-FileHash -LiteralPath $scnsOsmFile -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'd4b902b01fe944acb3161026679dabbab4898d6952bee22d7019f15fd15748de') { throw 'Original checksum differs; do not substitute a changed export.' }
$scnsDiagnosticOutput = Join-Path (Get-Location).Path 'data\staging\muj-connectivity-review'
New-Item -ItemType Directory -Force -Path $scnsDiagnosticOutput | Out-Null
Invoke-ScnsStep { docker run --rm --network none --mount "type=bind,source=$scnsOsmFile,target=/input/source.osm,readonly" --mount "type=bind,source=$scnsDiagnosticOutput,target=/output" scns-api python -m app.cli.muj_diagnostics /input/source.osm --preparation v2 --output /output }
Start-Process (Join-Path $scnsDiagnosticOutput 'components.svg')
Start-Process (Join-Path $scnsDiagnosticOutput 'subway.svg')
```

Expected: **Verified29components; diagnostics only, no database or preparation writes.** Use`--preparation v1` for the preserved original inventory. Outputs`diagnostic.json`, `README.md`, `components.svg`, `subway.svg`; safe rerun reproduces identical bytes for this pin. XML/checksum/preparation mismatches fail. This diagnostic command applies no corrections or deletion/upsert; only the separately reviewed authenticated helper can write the draft patch.

Source development equivalent from repository root:

```bash
cd backend
UV_CACHE_DIR=/tmp/scns-uv-cache uv run --frozen python -m app.cli.muj_diagnostics ../data/raw/muj/source.osm --output ../data/staging/muj-connectivity-review
UV_CACHE_DIR=/tmp/scns-uv-cache uv run --frozen pytest -q tests/unit/test_osm_conversion.py tests/unit/test_muj_diagnostics.py tests/unit/test_muj_update.py
cd ..
make check build test-unit
make test-db
cd backend
TEST_DATABASE_URL=postgresql+psycopg://scns:scns_local@localhost:54329/scns_test UV_CACHE_DIR=/tmp/scns-uv-cache uv run --frozen pytest -q tests/integration/test_muj.py tests/integration/test_muj_update.py tests/integration/test_admin_graph.py tests/integration/test_graph_concurrency.py tests/integration/test_imports.py
DOCKER_CONFIG=/tmp/scns-docker PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium UV_CACHE_DIR=/tmp/scns-uv-cache uv run --frozen python -m tests.browser_runner muj.spec.ts graph.spec.ts navigation.spec.ts qr.spec.ts
cd ..
DOCKER_CONFIG=/tmp/scns-docker python scripts/cloud-build.py
DOCKER_CONFIG=/tmp/scns-docker python scripts/smoke-publication-containers.py
DOCKER_CONFIG=/tmp/scns-docker python scripts/smoke-3c-demo-containers.py --muj
```

Integration command requires `TEST_DATABASE_URL` pointing to the dedicated test database (default`postgresql+psycopg://scns:scns_local@localhost:54329/scns_test`); never use the developer database as a test target. Browser/container runners enforce their disposable `_e2e_test` database naming and retain development volumes. Do not overlap browser runners on5174 or smoke DB-network attachments with integration runs. Commands are development verification, not an instruction to reset the owner's data. No migration/model/contract changes here; previous migration rehearsal remains applicable, and generated contracts are checked for no drift.

Actual cloud results and owner-reported Windows results are separately recorded in [verification](../testing/verification.md); the PowerShell sequence above was not executed on Windows by the agent. Independent source review, access clarification, route/entrance survey and explicit future publication remain separate actions.
