# Dark public map explorer: retained-data Windows update

Branch `redesign/map-explorer`, based on verified `a30810d5b73ffd2d757f2c05de1ed2a59f2e39aa` of `feat/muj-connectivity-review`. This is a public explorer presentation update, not another numbered milestone or campus publication. Existing homepage and admin remain; APIs, algorithms, schema, permissions and release data are unchanged. No migration, account bootstrap, seed/reimport, helper replay, approval or publication is needed. Preserve `.env`, private uploads, volumes, QR markers, restrictions, accounts, drafts and existing releases, including the owner-published E22 name.

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

## Compact manual acceptance walkthrough

1. Open `http://localhost:5173/`. Confirm the existing scrolling homepage, campus overview, process and about section remain. Choose **Explore campus** or **Explore ↗**. In the explorer, **Explorer campus** controls the same campus as the homepage selector. Keep the selected campus's synthetic/OSM disclosure and source attribution visible.
2. Choose your already published MUJ campus. Click **Browse places**, search **TMA Pai Auditorium entrance**, then select its row. The same place's map pin is selected and the card displays its existing public name/details, without a fabricated main-entrance or accessibility badge. Close it or press Escape; keyboard focus returns to the selecting control. E05 and other unresolved identities must remain unchanged.
3. Search **Mapped entrance 10828149259**, select **Route here**, and choose **Starting point → University Entrance**, **Route preference → Shortest walking route**, **Distance policy → Metric · stored path distances**, then **Find walking route**. The expected retained owner-reported baseline is approximately **513m**. The mint route must follow stored geometry, with readable start/end and independent text directions. This update must not change topology or route objective.
4. Switch **Distance policy → Directions only · unknown distance allowed**. Standard preference now says **Fewest eligible traversals**. Calculate again: the earlier owner-reported baseline is approximately **799m /9edges**, not513m. Distances/ETA retain all original estimate/unknown qualifications. Unsupported Library, cross-campus and verified step-free journeys must not acquire invented connections.
5. Choose **Demo Campus**, **Starting point → Main Gate**, **Destination → Library**, shortest/metric, then calculate: approximately **257m /4min**, three stored edges. **Hide map** preserves full directions. **Quiet Garden** under standard/metric should give no permitted route; **East Exit** with step-free should give no verified step-free route. Use Swap/Clear, reload an existing manual route link, and verify selections/route recovery still work.
6. At narrow width, campus/search/mode controls stay above the map; the results/planner panel is below. Use **Collapse panel / Expand panel** without dragging; restriction state, route safety and confirmed GPS expiry remain visible. Search with the on-screen keyboard, scroll normally, verify no sideways scrolling, hidden attribution, clipped fields or keyboard-focus loss. Automated emulation/resizing is not an actual-device keyboard test; record your phone/browser results separately.
7. Select a list row and a map pin by keyboard (Enter or Space); both select the same entity. **Route here** opens/focuses Destination; **Set as start** opens/focuses Starting point. Fit/zoom and repeated expand/resize should not blank the map or unexpectedly refit it. Search/filter/Previous/Next retain results and selections.
8. If your current release has approved indoor floors, choose its actual **Building and floor view** and use direction section buttons. Floor images must retain original colours/alignment, connectors and accessible text instructions. No floor/room is inferred from GPS. QR and **Use my location** still require explicit confirmation; location is requested only on button action. For deterministic desktop GPS checks use the existing [4C guide](geolocation.md); do not claim actual GPS/field verification from simulation.
9. Simulate offline/network failure using browser developer tools if desired. New routes pause; stale restriction/release results must hide rather than imply safety. Existing selected fields/text fallback remain. A failed map API/image or renderer must not prevent text navigation; an explicitly reloaded viewer requires fresh GPS confirmation. Do not change real restriction records just to test presentation.

The Windows E22 publication/acceptance recorded earlier is **owner-reported**, predating this redesign. It does not verify this redesign on Windows or a phone. The new release UUID and artifact checksum were not supplied; none are invented here. No additional independent human, institutional, physical-route or accessibility approval is claimed.

## Local verification commands (disposable databases only)

Frozen installation: `npm ci`; `cd backend` then `UV_CACHE_DIR=/tmp/scns-uv-cache uv sync --frozen`. Do not run `make setup` merely to overwrite local configuration. Frontend: `npm run check --workspace frontend`, `npm run test --workspace frontend`, `npm run build --workspace frontend`. Existing contract checks: from backend, `uv run --frozen pytest -q tests/unit/test_floorplan_contract.py tests/unit/test_qr_contract.py tests/unit/test_publication_contract.py tests/unit/test_indoor_contract.py tests/unit/test_closure_contract.py`.

Use documented isolated source runner `cd backend; uv run --frozen python -m tests.browser_runner` with existing test-database prerequisites; it explicitly owns/resets only a `_e2e_test` database and temporary fixture storage, never the retained developer database. In the managed cloud, use `DOCKER_CONFIG=/tmp/scns-docker python scripts/cloud-build.py` for the frozen API/frontend build: it forwards the existing proxy, proxy DNS and CA trust without printing credentials or disabling TLS. After those builds, `python scripts/smoke-publication-containers.py` owns its uniquely named test DB/network/temporary storage and cleans those resources only. The default runner includes all existing workflows plus explorer/source-visual fixtures. After a presentation-only correction, `python scripts/smoke-publication-containers.py --explorer-only` reruns explorer, source-response simulation and public-experience checks with the same disposable DB/storage and private/readiness boundaries; it does not replace the initial full regression. Do not run these against Windows developer data. Evidence and limits are recorded in [verification](../testing/verification.md); screenshots are in [the preview index](../previews/map-explorer/README.md).
