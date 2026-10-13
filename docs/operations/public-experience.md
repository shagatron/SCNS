# Public experience redesign — local update and acceptance

This redesign is based on completed4C, independent of4D. Reports/PWA/other feature slices are not added. Application APIs, Dijkstra, schema, admin/permissions, public releases, closure and location rules remain unchanged. No existing data needs seeding/bootstrap/publication. The landing introduction uses actual public API records/counts; /#explorer enters the planner directly, and existing query links/#planner and /q/{opaque-id} remain supported.

## Windows PowerShell: update/start existing installation

Run this entire block **from your existing SCNS repository directory**, with Docker Desktop Linux containers running. It stops on failed native commands and refuses to switch with local file changes. Preserve your changes first if the guard stops. Existing.env/accounts/private uploads/volumes/drafts/releases/QRs/restrictions are retained. No reset, seed, bootstrap, volume removal or retained-draft publication. The forward migration command checks the existing head0016_closures; redesign adds no migration.

```powershell
$ErrorActionPreference = 'Stop'
function Invoke-ScnsStep {
    param([Parameter(Mandatory=$true)][scriptblock]$Action)
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "SCNS command failed (exit $LASTEXITCODE). Stop and inspect above."
    }
}
Invoke-ScnsStep { git status --short }
if (git status --porcelain) {
    throw 'Preserve or commit local changes before switching branches.'
}
Invoke-ScnsStep { git fetch origin }
$scnsLocalBranch = git branch --list redesign/public-experience
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect local branches.' }
if ($scnsLocalBranch) {
    Invoke-ScnsStep { git switch redesign/public-experience }
} else {
    Invoke-ScnsStep { git switch --track origin/redesign/public-experience }
}
Invoke-ScnsStep { git pull --ff-only origin redesign/public-experience }
Invoke-ScnsStep { docker compose build api frontend }
Invoke-ScnsStep { docker compose stop api frontend import-worker }
Invoke-ScnsStep { docker compose up -d --wait db }
Invoke-ScnsStep { docker compose run --rm --no-deps api alembic upgrade head }
Invoke-ScnsStep { docker compose up -d --wait --no-build api frontend import-worker }
Invoke-ScnsStep { docker compose ps }
Invoke-ScnsStep { docker compose exec -T api alembic current }
Invoke-RestMethod 'http://localhost:5173/api/v1/health/ready'
Start-Process 'http://localhost:5173/'
Start-Process 'http://localhost:5173/#explorer'
```

Expected: readiness success,0016_closures/head; new public composition and direct explorer; existing admin unchanged. A clean checkout without published data shows an honest empty-campus state. Do not seed your retained database to make the counts match cloud screenshots. Cloud test images use isolated invented fixtures; public counts exclude restricted records and depend on your release.

## Visual and functional acceptance

1. **Homepage:** open /, wait for the campus service status. Inspect the large SCNS headline, narrow yellow information panel and synthetic disclosure. Select your existing published campus if needed. No location prompt occurs on page load.
2. **Scrolling:** use the floating Home/Campus/How it works/Places/Explore navigation. On narrow mobile widths, Home/Places/Explore remain compact; the other sections remain in native scrolling order. Active sections update. Explore campus and /#explorer take you directly to controls/map; keyboard Tab→Skip to route planner→Enter reaches the planner even if data arrives later.
3. **Counts:** public destinations equal the selected release's search total; mapped buildings count complete permitted footprints within campus extent, and published floors count approved public floor views. Unavailable/truncated counts are omitted, not invented. Zero published floors is a legitimate value.
4. **Directory:** search `books`; choose **Route here** on Library. Controls open and Destination receives keyboard focus. Place details expose description/code/aliases and available indoor information. **Start here** changes the start and discards GPS confirmation as before. Category, pagination and alias/department search remain available.
5. **Baseline route:** Starting point **Main Gate**, Destination **Library**, preference **Shortest walking route**, distance policy **Verified metric paths**→Find walking route. With no overlapping applicable restriction, expect **256.88m /three stored edges**, UI **257metres /4min estimated**. Black selected polylines, labelled start/destination and ordered directions follow stored paths. Different active restrictions can legitimately change or prevent this route.
6. **Controls/text:** toggle **Route controls** closed/open. The map and result directions remain available independently. **Hide map** retains text directions. Clear route works. Reload a computed manual link: revalidate the current release/overlay before recomputing, never reuse stale route geometry.
7. **Conservative failures:** Main Gate→Quiet Garden gives no permitted route. Step-free Main Gate→East Exit gives no verified step-free route. Unknown accessibility remains unknown. Existing closures/lift outages still exclude affected paths; estimated end does not reopen them. DevTools Network→Offline disables new routes and hides results that cannot claim current restrictions. Reconnect/check restrictions and calculate again.
8. **Indoor:** if your indoor demo is already published, exercise existing18m/36m/57m cases and building/floor controls. Follow ordered entrance/connector/floor transitions. Unknown distance/ETA and directions-only qualification remain visible. Do not publish/reseed retained ACA drafts to make floors appear.
9. **QR:** open an existing marker URL. Inspect the matching SCNS layout and readable label/state; **I am at this marker now** remains mandatory. Its confirmed notice appears beside the explorer. Reload requires fresh confirmation. Existing revoked/planned/reassigned behavior and manual fallback remain unchanged; do not create/modify retained signs just for a screenshot.
10. **Location simulation:** in desktop Chrome DevTools Protocol Monitor command editor select **Main (http://localhost:5173)**, command **Emulation.setGeolocationOverride**; latitude`0.0002`, longitude`0.00015`, accuracy`5`, then click the blue send arrow. Click **Use my location**, Allow, physically confirm Gate **for this synthetic simulation**, and calculate Library. Expect257m/4min with approach excluded. Default60s expiry requires a new request/confirmation or manual start. Remove simulation using **Emulation.clearGeolocationOverride**. Exact invalid-fix cases remain in [geolocation guide](geolocation.md). This is simulated-browser evidence, not GPS hardware/physical travel.
11. **Responsive/accessibility:** inspect320,360,768,1440px DevTools widths. No page overflow, clipped forms or obscured focused controls. Navigate with keyboard; controls/links have visible focus and labels. Windows accessibility animation settings or DevTools Rendering→prefers-reduced-motion reduce should remove reveals/smooth scrolling while keeping everything visible. Actual Windows/physical-phone/human screen-reader redesign testing remains unverified until reported.
12. **Admin:** /admin retains its previous visual layout, session handling and permissions. No reports entry point or new feature-milestone controls should appear.

Prior owner Windows4C simulation at604ace8 is separate evidence and does not constitute a redesign acceptance pass. [Design decisions](../design/public-experience.md), [verification](../testing/verification.md), [progress](../progress.md).
