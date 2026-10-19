# Public homepage and route-planner polish

Presentation-only follow-up to completed4B, not another milestone. Public-scoped styles improve typography/spacing/status, aligned controls, distance/ETA/directions and map-section discoverability. Algorithms, API/schema/permissions/publication, synthetic/accessibility disclosures, QR confirmation and restriction freshness retain4B behavior. No dependencies added or admin redesign.

## Windows PowerShell update

Run from the existing SCNS directory with Docker Desktop Linux containers running. The block also forward-updates inherited4B services/schema if your local installation is older; this polish introduces no migration. Existing accounts/QRs/restrictions/drafts/releases/.env/uploads/named volumes are retained. Do not run seeds, bootstrap, demo setup, publication or volume-removal commands.

```powershell
$ErrorActionPreference = 'Stop'
function Invoke-ScnsStep {
    param([Parameter(Mandatory=$true)][scriptblock]$Action)
    & $Action
    if ($LASTEXITCODE -ne 0) { throw "SCNS command failed (exit $LASTEXITCODE). Stop and inspect above." }
}
Invoke-ScnsStep { git status --short }
if (git status --porcelain) { throw 'Preserve or commit local changes before switching branches.' }
Invoke-ScnsStep { git fetch origin }
$scnsLocalBranch = git branch --list polish/public-route-planner
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect local branches.' }
if ($scnsLocalBranch) {
    Invoke-ScnsStep { git switch polish/public-route-planner }
} else {
    Invoke-ScnsStep { git switch --track origin/polish/public-route-planner }
}
Invoke-ScnsStep { git pull --ff-only origin polish/public-route-planner }
Invoke-ScnsStep { docker compose build api frontend }
Invoke-ScnsStep { docker compose stop api frontend import-worker }
Invoke-ScnsStep { docker compose up -d --wait db }
Invoke-ScnsStep { docker compose run --rm --no-deps api alembic upgrade head }
Invoke-ScnsStep { docker compose up -d --wait --no-build api frontend import-worker }
Invoke-ScnsStep { docker compose ps }
Invoke-ScnsStep { docker compose exec -T api alembic current }
Invoke-RestMethod http://localhost:5173/api/v1/health/ready
Start-Process http://localhost:5173/
Start-Process http://localhost:5173/admin
```

Expected0016_closures/head, readiness success and the refreshed public homepage. Actual Windows execution is unverified; Linux PowerShell parser/mocked command guards are separate evidence. The Docker app stays on existing localhost bindings; no phone/LAN/public access is enabled.

## Short synthetic walkthrough and visual checklist

Use the existing synthetic campus and current published release. Any existing restrictions remain in force; the exact baseline below assumes no overlapping active incident.

1. At desktop and360px/320px widths, check aligned source/destination/preference/distance-policy fields, readable status/disclosures and no horizontal page overflow. Tab through controls; focus must be visibly outlined.
2. Main Gate → Library, Shortest walking route / Verified metric paths → Find walking route. Unchanged original synthetic release:256.88m/three stored edges, displayed257metres/4min estimated. Instructions: Courtyard→West→Library, then arrival. No real navigation/accessibility claim.
3. Click Show outdoor section and change Building and floor view to Outdoor campus. Hide map: directions/summary remain usable. Clear route retains normal existing behavior.
4. Main Gate → Quiet Garden, shortest/metric: No permitted walking route. Main Gate→East Exit, step-free/metric: No verified step-free route. Main Gate→Main Gate: You’re already there/zero distance.
5. Calculate a route, devtools Network→Offline: previous route hidden, new routing disabled. Return online→Check restrictions, wait for completion, then calculate again. Existing incident reasons/state and estimated-end qualifications remain visible; do not modify restrictions just for this visual pass.
6. If your3C synthetic indoor demo is already published, room101→102 is18m,101→201 shortest36m stairs/step-free57m lift unless an outage blocks it. Check floor-selector and departure/arrival section buttons; do not publish/reseed retained ACA work to expose floors. Unknown distance remains labelled unknown and ETA unavailable. Existing QR link still requires explicit location confirmation/reconfirmation; no automatic positioning.

Source and built Chromium desktop/mobile emulation are not physical-device or actual Windows testing. Automated contrast/focus checks are not human assistive-technology certification. Existing comprehensive4B incident tests and owner4A evidence remain in [verification](../testing/verification.md); this pass does not implement4C.
