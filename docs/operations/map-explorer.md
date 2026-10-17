# Dark public map explorer: retained-data Windows update

Branch `redesign/map-explorer`, based on verified `a30810d5b73ffd2d757f2c05de1ed2a59f2e39aa` of `feat/muj-connectivity-review`. This is a corrected outdoor-map-only presentation update, not another numbered milestone or campus publication. The baseline homepage, complete directory, planner controls/actions/defaults/focus/scroll/recovery and admin are restored; APIs, algorithms, schema, permissions and release data are unchanged. No migration, account bootstrap, seed/reimport, helper replay, approval or publication is needed. Preserve `.env`, private uploads, volumes, QR markers, restrictions, accounts, drafts and existing releases, including the owner-published E22 name.

## Complete PowerShell update/start block

Run from the existing repository, with Docker Desktop Linux containers available. Stop on dirty Git status and preserve that work; do not reset it. The existing phone override at `$env:TEMP\scns-phone.override.yaml` is included **unchanged if present**, including when recreating the frontend. No hotspot IP, port, firewall or LAN/HTTPS setting is created or hardcoded by this update. If the override is absent, only the existing base Compose configuration is used; restore your own original override if you require its prior phone bindings. Phone reachability is not verified from cloud.

```powershell
$ErrorActionPreference = 'Stop'
function Invoke-ScnsStep {
    param([Parameter(Mandatory=$true)][scriptblock]$Action)
    & $Action
    if ($LASTEXITCODE -ne 0) { throw 'SCNS command failed. Stop and preserve existing work, data and volumes.' }
}
Invoke-ScnsStep { git status --short }
$ScnsDirty = git status --porcelain
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect working tree; stop.' }
if ($ScnsDirty) { throw 'Preserve local changes before updating; nothing reset.' }
Invoke-ScnsStep { git fetch origin refs/heads/redesign/map-explorer:refs/remotes/origin/redesign/map-explorer }
$ScnsExplorerBranch = git branch --list redesign/map-explorer
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect local branches; stop.' }
if ($ScnsExplorerBranch) {
    Invoke-ScnsStep { git switch redesign/map-explorer }
} else {
    Invoke-ScnsStep { git switch --no-track -c redesign/map-explorer refs/remotes/origin/redesign/map-explorer }
}
Invoke-ScnsStep { git pull --ff-only origin redesign/map-explorer }
Invoke-ScnsStep { git merge-base --is-ancestor a30810d HEAD }
$ScnsComposeFiles = @('-f', 'compose.yaml')
$ScnsPhoneOverride = Join-Path $env:TEMP 'scns-phone.override.yaml'
if (Test-Path -LiteralPath $ScnsPhoneOverride) {
    $ScnsComposeFiles += @('-f', $ScnsPhoneOverride)
    Write-Host 'Using your existing phone override unchanged.'
} else {
    Write-Host 'No phone override found; retaining base Compose settings.'
}
Invoke-ScnsStep { docker compose @ScnsComposeFiles build frontend }
Invoke-ScnsStep { docker compose @ScnsComposeFiles up -d --wait --no-deps --no-build db }
Invoke-ScnsStep { docker compose @ScnsComposeFiles ps db }
Invoke-ScnsStep { docker compose @ScnsComposeFiles up -d --wait --no-deps --no-build api }
Invoke-ScnsStep { docker compose @ScnsComposeFiles up -d --wait --no-deps --no-build --force-recreate frontend }
Invoke-ScnsStep { docker compose @ScnsComposeFiles ps db api frontend }
Invoke-RestMethod 'http://localhost:5173/api/v1/health/ready'
Start-Process 'http://localhost:5173/#explorer'
```

Start/check the **retained database first**. The earlier owner-reported API-only --no-deps startup hung on readiness/returned database503s when database/frontend were stopped; these commands explicitly start dependencies in order. If database health fails, stop and inspect it without deleting volumes, reseeding or replaying E22 helpers. Only the frontend image needs rebuilding; existing API/data contracts are unchanged. An absent existing image/service installation is a setup issue, not a reason to initialise a replacement database. No Windows commands in this guide were executed by the cloud agent.

## Baseline-preserving manual acceptance walkthrough

The former sidebar instructions are superseded by the preservation correction. No new Browse/Plan/Collapse panel, Explorer campus selector or selected-place card remains. The update command above still applies and preserves the existing temporary phone override unchanged; do not replay naming/publication/import helpers.

1. Open `http://localhost:5173/`. Confirm original intro, campus selector, overview, process, **Places worth finding** full card directory, explorer, about and footer. The **Places** navigation link must reach the actual search/cards/pagination, not an empty heading. Choose campus only with the original **Explore campus** selector.
2. In **Demo Campus**, verify six initial cards, **10 public destinations · showing1–6**, Previous disabled/Next available. Next shows7–10 with Next disabled; search/category resets to the first page. Search **books** or choose **Category → Library**: full Library heading/details/code/aliases/unknown-access disclosure and original **Route here / Start here** remain in the directory.
3. Click **Start here** on Library: Starting point focuses with Library selected. The directory's **Route here** action remains available without switching modes. Choose Starting point **Main Gate**, then Library **Route here**: Destination focuses, controls open, and no route calculates until **Find walking route**. Directly clicking Library's map pin has the same destination action, rather than opening a separate selection card. Pins add no tab stops; keyboard users retain the original directory actions and map pan/zoom controls.
4. In the original planner, **Route preference → Shortest walking route**, **Distance policy → Metric · stored path distances**, Main Gate→Library: approximately **257m/4min**, three stored edges. Outdoor route is mint on dark map vectors; planner fields/buttons, result metrics/directions and surrounding content retain baseline style/layout. Hide map and collapse **Route controls** separately: full directions remain below the grid. Fit/zoom/resize retain original bounds behavior. Reload the manual-route URL: fields and recomputed route recover normally.
5. Choose **Quiet Garden** as destination under shortest/metric: the original “No permitted walking route connects these locations…” message appears beside planner controls, selections stay, focus/scroll do not jump. Search, map, floor and shared-route lookup failures show retries beside the relevant controls. Do not change real data to manufacture failures; optional DevTools offline/request blocking can check text fallback. Search no-match/loading messages remain in the directory.
6. On your already-published MUJ campus, search **TMA Pai Auditorium entrance** in the full directory. E05 and unresolved names stay unchanged. University Entrance→Mapped entrance10828149259 retains owner-reported **metric~513m** versus **Directions only~799m/9edges**. Directions-only standard preference remains **Fewest eligible traversals**; this is not a shortest-distance/fastest objective. Unsupported Library, cross-campus and verified step-free journeys must remain unsupported. These are prior owner-reported baselines, not a new Windows verification claim.
7. Existing approved floor views, original floor controls and direction section buttons remain. Do not seed/publish floors merely for testing. Approved images keep their colours, coordinate alignment, original labels and image retry. QR confirmation/locked campus/revocation and explicit **Use my location**/expiry retain baseline behavior. Use the existing [simulated geolocation guide](geolocation.md) only when desired; no live tracking or actual GPS verification is implied.
8. At narrow widths, use the original ordinary page layout and anchors, keyboard/skip link and native details. Check no horizontal overflow or clipped controls/attribution. A simulated viewport is not an actual phone keyboard or human assistive-technology test. Existing phone access configuration is reused, never created or expanded by this update.

Earlier owner-reported E22 publication remains separate: both accounts were owner-operated, new release UUID/artifact checksum were not supplied. This correction does not change releases or claim independent human/institutional/physical/accessibility approval. Native Windows/phone checks are for the owner; none executed by the cloud agent.

## Local verification commands (disposable databases only)

Frozen installation: `npm ci`; `cd backend` then `UV_CACHE_DIR=/tmp/scns-uv-cache uv sync --frozen`. Do not run `make setup` merely to overwrite local configuration. Frontend: `npm run check --workspace frontend`, `npm run test --workspace frontend`, `npm run build --workspace frontend`. Existing contract checks: from backend, `uv run --frozen pytest -q tests/unit/test_floorplan_contract.py tests/unit/test_qr_contract.py tests/unit/test_publication_contract.py tests/unit/test_indoor_contract.py tests/unit/test_closure_contract.py`.

Use documented isolated source runner `cd backend; uv run --frozen python -m tests.browser_runner` with existing test-database prerequisites; it explicitly owns/resets only a `_e2e_test` database and temporary fixture storage, never the retained developer database. In the managed cloud, use `DOCKER_CONFIG=/tmp/scns-docker python scripts/cloud-build.py` for the frozen API/frontend build: it forwards the existing proxy, proxy DNS and CA trust without printing credentials or disabling TLS. After those builds, `python scripts/smoke-publication-containers.py` owns its uniquely named test DB/network/temporary storage and cleans those resources only. The default runner includes all existing workflows plus explorer/source-visual fixtures. After a presentation-only correction, `python scripts/smoke-publication-containers.py --explorer-only` reruns explorer, source-response simulation and public-experience checks with the same disposable DB/storage and private/readiness boundaries; it does not replace the initial full regression. Do not run these against Windows developer data. Evidence and limits are recorded in [verification](../testing/verification.md); matched screenshots are in [the preservation preview index](../previews/map-preservation/README.md); the [parity checklist](../testing/map-preservation-audit.md) records the complete source/test audit.
