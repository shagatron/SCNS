# Educational indoor demonstration: Docker update and presentation

Branch `feat/muj-indoor-demo`, directly from accepted `polish/muj-homepage` at `ee683e1a61a6584147c3e39b121a8765db5e46ba`. No `feat/native-windows` commits are included. Docker remains the runtime.

**Demonstration layout — not an actual MUJ floorplan.** This qualification appears beside the new MUJ entry, before the planner, inside the viewer and in the footer. The educational building and generic room identities are fictional. The supplied Nalanda drawing pages7/10/11 were inspected only for general school organization; their blueprints, geometry, dimensions, room identities, branding and title blocks are not shipped, traced or displayed. The two rectangular SVG schematics are original SCNS illustrations, reproducible with `scripts/generate-educational-indoor.py` (standard library only).

## Context, graph and limits

The **Indoor navigation demo ↗** entry is added to the existing MUJ introduction when published metadata is `code=MUJ` and `is_demo=false`. It removes/replaces none of the original controls, sections or actions. It opens `/indoor-demo?returnCampus=<selected-campus-UUID>`. Return to campus explorer restores that campus. `/indoor-demo` also works directly, with a generic return link.

This is **self-contained educational application content**, not a campus dataset, draft, public release or approval. No owner activation, login, import, review, publication, database writes or background processing is required. Deploying these local Docker builds merely serves the authored demo code/assets; it never publishes or changes campus data. Normal permissions, source/review/publication guards and public release contracts remain untouched. The API has its own read-only namespace:

- `GET /api/v1/educational/indoor-school`: versioned floor/room descriptions.
- `POST /api/v1/educational/indoor-school/routes`: computes directions from `source_id`, `destination_id`, `expected_version`. It rejects stale versions, foreign room IDs and unsupported extra options. POST computes a response only; it performs no administrative write.

The Python-authored graph has **15 nodes and26 directed connections**: seven rooms and eight corridor/stair nodes, with each connection authored in both directions. The existing production **`app.routing.dijkstra.shortest_path`** computes each route. The demo does **not** call the mixed-release eligibility pipeline or fabricate verified connector/source/reviewer flags to satisfy it. It reuses the existing floor-coordinate adapter, Leaflet indoor renderer, stored per-floor geometry and route-segment schema. The route response has no campus/release identity. Virtual building/floor/frame/image IDs identify illustration objects only.

All edge costs are **one traversal**, not a measured metre or second. The engine's internal numeric cost is used solely to choose the fewest eligible traversals. The API returns `distance_m=null` and `estimated_duration_s=null` even for a same-room zero-traversal path; UI says **Distance unknown · ETA unavailable**. Floor coordinates are illustration pixels, x right/y down, with no calibration or scale. Routes never draw a line between different floor frames; stair markers and explicit transition instructions link the sections.

No accessibility evidence, verified step-free route, lift, outdoor campus link, GPS/QR position, live closure or institutional/physical-survey approval is claimed for this educational graph. Those existing public campus features remain in the ordinary explorer. This deliberately small tree topology is for explaining routing, not real-world navigation or complex building operations. Room selectors/text directions remain usable when the map is hidden or its image fails. Fit-to-floor may require zooming to read room text on a narrow phone; +/−, drag, keyboard pan/zoom and Fit floor plan are available. Physical phone/Windows/assistive-technology acceptance remains owner-run.

## Complete Windows PowerShell update/start

Use ordinary PowerShell and your existing checkout with Docker Desktop in **Linux containers** mode. Change only the checkout path if needed. Save local edits before switching; these commands refuse dirty/divergent Git state. Existing `.env`, Docker/native directories, accounts, uploads, journals, volumes, drafts and releases remain. No native-Windows scripts are run. The existing temporary phone override is preserved on disk but **excluded** for laptop-only startup; no LAN/firewall access is enabled.

```powershell
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath 'C:\Users\Aaditya Shah\SCNS'
function Invoke-ScnsDemoStep {
    param([Parameter(Mandatory=$true)][scriptblock]$Action)
    & $Action
    if ($LASTEXITCODE -ne 0) { throw "SCNS command failed ($LASTEXITCODE). Stop and preserve existing data." }
}
$ScnsDirty = git status --porcelain
if ($LASTEXITCODE -ne 0 -or $ScnsDirty) { throw 'Preserve local Git changes before continuing. Nothing reset.' }
Invoke-ScnsDemoStep { git fetch origin refs/heads/feat/muj-indoor-demo:refs/remotes/origin/feat/muj-indoor-demo }
$ScnsLocalBranch = git branch --list feat/muj-indoor-demo
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect branches.' }
if ($ScnsLocalBranch) {
    Invoke-ScnsDemoStep { git switch feat/muj-indoor-demo }
} else {
    Invoke-ScnsDemoStep { git switch --no-track -c feat/muj-indoor-demo refs/remotes/origin/feat/muj-indoor-demo }
}
Invoke-ScnsDemoStep { git pull --ff-only origin feat/muj-indoor-demo }
Invoke-ScnsDemoStep { git merge-base --is-ancestor ee683e1a61a6584147c3e39b121a8765db5e46ba HEAD }
Invoke-ScnsDemoStep { git rev-parse HEAD }
$ScnsPhoneOverride = Join-Path $env:TEMP 'scns-phone.override.yaml'
if (Test-Path -LiteralPath $ScnsPhoneOverride) { Write-Host 'Existing phone override preserved and excluded for laptop-only startup.' }
$ScnsPreviousAppUrl = $env:PUBLIC_APP_URL
try {
    $env:PUBLIC_APP_URL = 'http://localhost:5173'
    Invoke-ScnsDemoStep { docker compose -f compose.yaml build api frontend }
    # Start/check the EXISTING database before waiting on API readiness.
    Invoke-ScnsDemoStep { docker compose -f compose.yaml up -d --wait --no-deps --no-build db }
    Invoke-ScnsDemoStep { docker compose -f compose.yaml exec -T db pg_isready -U scns -d scns }
    Invoke-ScnsDemoStep { docker compose -f compose.yaml up -d --wait --no-deps --no-build --force-recreate api }
    Invoke-ScnsDemoStep { docker compose -f compose.yaml up -d --wait --no-deps --no-build --force-recreate frontend }
    Invoke-ScnsDemoStep { docker compose -f compose.yaml ps db api frontend }
    Invoke-RestMethod 'http://localhost:5173/api/v1/health/ready'
    $ScnsDemo = Invoke-RestMethod 'http://localhost:5173/api/v1/educational/indoor-school'
    if ($ScnsDemo.version -ne 'indoor-school-v1' -or $ScnsDemo.floors.Count -ne 2 -or $ScnsDemo.rooms.Count -ne 7) { throw 'Unexpected educational demo response; stop and inspect.' }
    Start-Process 'http://localhost:5173/?campus=afcf4f1a-635f-563b-af5b-3d7efd2ed84c'
} finally {
    $env:PUBLIC_APP_URL = $ScnsPreviousAppUrl
}
```

Expected: retained database ready, API/frontend healthy, educational version `indoor-school-v1`, two floors/seven rooms. The existing worker is unchanged and is not recreated or assigned a demo job. Schema is unchanged; **do not run migration, seed, bootstrap, reimport, naming or publication helpers**. No volume/image/database removal is part of updating. Retry the same block after fixing a build/start failure: it has no application-data activation step to duplicate. Keep existing partial native setup on disk; downloading this separate branch does not use or alter it.

The final URL selects the owner's existing MUJ campus. If that campus is absent in another local database, do not create/publish one to manufacture the entry: `/indoor-demo` still opens the separate educational context. For repeat startup after an ordinary shutdown, reuse the same database-first `up`/`pg_isready`/API/frontend sequence with `--no-build`; a build is required only after updating code/assets. Keep the phone override excluded unless separately authorized and validated.

## Short presentation and manual inputs

1. On MUJ, point out the retained university photo/logo, full homepage, campus selector and **Indoor navigation demo ↗** link. Read its **not an actual MUJ floorplan** warning. Open it; point out the separate fictional building and Directions-only policy.
2. Keep **Start room → Demo Classroom A · Ground floor** and **Destination room → Demo Library · Ground floor**. Press **Find demo directions**. Expected: **3 authored traversals**, ground-floor path through authored corridor connections, arrival at Demo Library, **Distance unknown · ETA unavailable**. The path is calculated by the existing Dijkstra function, not a preselected highlighted line.
3. Set destination to **Demo Classroom C · First floor**, keeping start A. Calculate. Expected: **9 authored traversals**. Ground-floor section leads to **Demo Stairs**; text explicitly says **Take Demo Stairs from Ground floor to First floor**. Press **Show First floor** beside that stair instruction, or use **View demonstration floor → First floor**. Its highlighted section leads to Classroom C; no line is drawn across floor frames. Read arrival text independently of the map. Reload: selections, calculated route and chosen floor recover.
4. Reverse: start **Demo Classroom C · First floor**, destination **Demo Classroom A · Ground floor**. Calculate. Expected:9traversals, first-floor initial view and explicit stair descent. Optional **Demo Classroom A → Demo Classroom A**:0traversals, no invented zero-metre/ETA claim.
5. Set **Demo Classroom A → Demo Disconnected Room · Ground floor**. Calculate. Expected: contextual **Demo route unavailable**, explanation that no authored connection exists, retained selections and no highlighted route. This is a graph reachability result, not a wall-crossing shortcut. Explain: **nodes represent rooms/junctions; directed connections represent authored movement; Dijkstra sums traversal costs; an isolated node has no path.**
6. Use **Hide demonstration map** after a successful route; directions remain. Restore it, pan/zoom and **Fit floor plan**. Keyboard: Tab through labelled controls, Enter to calculate, focus map then arrow keys/+ or−. Narrow Chrome viewport: no horizontal page overflow; zoom for small plan labels. These are manual inputs/expected outcomes, not a claim that Windows/physical-device testing already passed.
7. **← Return to campus explorer** restores selected MUJ. Confirm its existing metric University Entrance→Mapped entrance10828149259 route remains approximately513m/13edges; Directions only remains approximately799m/9edges. Hostel→GHS23.62m/3 and Hostel→Faculty163.28m/6 remain expected. Demo Campus Main Gate→Library remains approximately257m/4min/3edges. Actual Windows database results are pending your local checks; cloud source-OSM/isolated fixture checks are separate evidence. No room from the educational graph should appear in the real campus directory.

[Rendered floors/route and provenance](../previews/educational-indoor/README.md) · [Verification and preservation checklist](../testing/educational-indoor-demo.md).
