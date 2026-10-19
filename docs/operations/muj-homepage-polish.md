# MUJ homepage polish: frontend-only Windows update

Branch `polish/muj-homepage`, parent `feat/muj-path-connectivity` at4fbc61663add1a31df0cda66e065e73a542f6fed (includes restored8798fa3). This is visual-only: original sections/directory/planner/navigation/actions/defaults/errors/QR/GPS/closures/indoor/admin and all published data remain. No API/schema/permission/algorithm or dependency change. Do not replay any setup/import/naming/publication helper. No migration is needed.

The owner-supplied ZIP contains `muj.jpg` (736×414) and transparent `muj_logo.png` (250×289). Exact originals are retained with hashes; only the photo is optimized/cropped without upsampling. This differs from the earlier inline preview/expected filenames; the actual ZIP originals are used without substitutes. MUJ branding applies only to published metadata `code=MUJ` and `is_demo=false`. Demo/other/loading campuses do not request these assets. Visible student-project attribution avoids claiming university endorsement; photos do not approve maps, paths or accessibility. Source photo resolution limits large-screen sharpness. [Asset provenance and reproduction](../../frontend/public/branding/muj/README.md).

## Complete PowerShell update/start

Use your existing repository and Docker Desktop Linux containers. This is explicitly **laptop-only loopback** startup. Existing `$env:TEMP\scns-phone.override.yaml` stays on disk unchanged and is deliberately **excluded**, so a stale hotspot IP cannot prevent startup. Explicit `-f compose.yaml` avoids automatically loading an alternate Compose file. No LAN/firewall/HTTPS configuration is created or expanded. The shell's previous PUBLIC_APP_URL is restored; the running API is configured for the actual loopback browser origin.

```powershell
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath 'C:\Users\Aaditya Shah\SCNS'
function Invoke-ScnsStep {
    param([Parameter(Mandatory=$true)][scriptblock]$Action)
    & $Action
    if ($LASTEXITCODE -ne 0) { throw "SCNS command failed (exit $LASTEXITCODE). Stop and preserve existing data." }
}
Invoke-ScnsStep { git status --short }
$ScnsDirty = git status --porcelain
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect repository; stop.' }
if ($ScnsDirty) { throw 'Preserve/commit local changes before switching. Nothing reset.' }
Invoke-ScnsStep { git fetch origin refs/heads/polish/muj-homepage:refs/remotes/origin/polish/muj-homepage }
$ScnsBranch = git branch --list polish/muj-homepage
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect branches.' }
if ($ScnsBranch) {
    Invoke-ScnsStep { git switch polish/muj-homepage }
} else {
    Invoke-ScnsStep { git switch --no-track -c polish/muj-homepage refs/remotes/origin/polish/muj-homepage }
}
Invoke-ScnsStep { git pull --ff-only origin polish/muj-homepage }
Invoke-ScnsStep { git merge-base --is-ancestor 4fbc61663add1a31df0cda66e065e73a542f6fed HEAD }
Invoke-ScnsStep { git rev-parse HEAD }
$ScnsPhoneOverride = Join-Path $env:TEMP 'scns-phone.override.yaml'
if (Test-Path -LiteralPath $ScnsPhoneOverride) {
    Write-Host 'Existing phone override preserved; excluded for laptop-only startup.'
}
$ScnsPreviousAppUrl = $env:PUBLIC_APP_URL
try {
    $env:PUBLIC_APP_URL = 'http://localhost:5173'
    # Rebuild only the frontend. Reuse your installed API image and retained data.
    Invoke-ScnsStep { docker compose -f compose.yaml build frontend }
    Invoke-ScnsStep { docker compose -f compose.yaml up -d --wait --no-deps --no-build db }
    Invoke-ScnsStep { docker compose -f compose.yaml exec -T db pg_isready -U scns -d scns }
    # Recreate process only to make its origin match loopback, without API build/migration.
    Invoke-ScnsStep { docker compose -f compose.yaml up -d --wait --no-deps --no-build --force-recreate api }
    Invoke-ScnsStep { docker compose -f compose.yaml up -d --wait --no-deps --no-build --force-recreate frontend }
    Invoke-ScnsStep { docker compose -f compose.yaml ps db api frontend }
    Invoke-RestMethod 'http://localhost:5173/api/v1/health/ready'
    Invoke-ScnsStep { docker compose -f compose.yaml exec -T api alembic current }
    Start-Process 'http://localhost:5173/'
} finally {
    $env:PUBLIC_APP_URL = $ScnsPreviousAppUrl
}
```

Expected readiness reports a ready database; `alembic current` is inspection only (existing head0016_closures). The earlier Windows API-only503incident is avoided by starting/checking the retained DB **before** API readiness. Missing existing API image/schema is a setup blocker, not permission to initialize replacement data. No seed/bootstrap/reimport/helper replay/approval/publication, `.env` edits, volume removal or destructive reset. Existing worker is unchanged; this update neither rebuilds it nor starts a new data job. Commands reviewed here, not executed on Windows. Existing phone override may be deliberately reused later after checking its IP/origin; this task does not validate phone access.

## Exact visual/manual checklist

1. Open `http://localhost:5173/`. Retain **Home / Campus / How it works / Places / Explore**, the original title, service status, original campus selector, full page sections and footer. Controls use warm cream/amber accents; the outdoor map remains dark with mint routes. **Places** must reach the full searchable directory, not a replacement sidebar or link-only section.
2. **Explore campus → Demo Campus**: synthetic disclosure remains, no university photo/emblem. Choose your already-published **Manipal University Jaipur (OSM preparation)** campus: supplied central-dome photograph becomes the hero background; original transparent emblem sits visibly on a cream backing; **Student project · not an official university service.** is readable. Existing campus name and source limitations remain. Switch back to Demo: university assets disappear and synthetic identity returns. If MUJ is absent, do not publish/create it merely to see branding.
3. Inspect320/360/390/768/1440px with Chrome device emulation/normal resizing. Dome/finial stay within the photo crop, logo proportions stay natural, long campus names wrap without widening the document. Every selector/action remains reachable by scrolling. Press Tab: skip link/navigation/selector/explore action and directory/planner focus remain visible. Reduced motion should retain static content; images are not lazy-loaded. Source photo has only736pxnative width; no higher-resolution image is invented.
4. In Demo **Places**, six full destination cards remain initially; **Next/Previous**, search **books**, **Category → Library**, descriptions/aliases/codes/access qualifications and **Start here / Route here** remain. Start at Library focuses **Starting point**; choose **Main Gate**, then Library **Route here** focuses **Destination**. **Find walking route** with **Shortest walking route / Metric · stored path distances** gives approximately257m/4min,3edges. No automatic calculation on merely choosing a place. Hide map/collapse controls: directions remain available. Reload the route URL: selections and route recover.
5. Demo **Main Gate → Quiet Garden**, shortest/metric: contextual **Route unavailable** beside planner, no lost selections or surprise page jump. Optional DevTools request blocking for `/branding/muj/*` tests both decorative photo and emblem failures: reload the MUJ view; title/selector/actions/status remain against dark fallback, with **University emblem unavailable**. Unblock and reload/switch campus to restore images. Never modify actual data to manufacture failure cases. Keep normal API/search retries beside their original controls.
6. Actual MUJ E22 remains **TMA Pai Auditorium entrance**; E05 and unresolved names stay unchanged. Prior owner-reported comparisons, if desired: **University Entrance → Mapped entrance10828149259**, metric shortest approximately513m/13edges; **Directions only / Fewest eligible traversals**, approximately799m/9edges. Hostel→GHSapproximately23.62m/3, Hostel→Facultyapproximately163.28m/6. Unsupported Library/cross-campus/verified step-free remains unsupported. These are prior owner reports/expected checks, not newly verified Windows results.
7. Existing QR confirmation/revocation/manual fallback, explicit GPS confirmation/expiry and restriction freshness messages remain in their existing places. Reviewed indoor/floor controls and map-independent directions remain. No live GPS or physical route test is required by this visual task. On a real phone, separately check the layout with the keyboard open; automated reduced-height viewport checks are a simulation, not a physical keyboard result.
8. `/admin`: original sign-in/dashboard/forms are unchanged; no university branding appears there. Existing accounts, drafts, uploads, private journals, volumes, releases and restrictions remain intact. No review/publication action is part of acceptance.

[Feature-preservation evidence](../testing/muj-homepage-preservation.md) · [Matched before/after captures](../previews/muj-homepage/README.md). Browser branding examples use deliberately labelled simulated MUJ metadata over isolated synthetic release fixtures; they do not inspect/publish the actual Windows MUJ dataset.
