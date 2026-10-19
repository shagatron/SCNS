# MUJ local publication results and routing-policy wording update

Owner report,16October2026: the existing Windows MUJ draft was published locally through the normal workflow and appears in the public explorer. All requested public acceptance checks passed: three metric routes, unavailable Library/cross-campus and verified step-free journeys, OSM attribution and retained Demo Campus baseline. The source/submission/approval identities were separate application accounts **all operated by the owner**. This demonstrates application-account separation, not independent human review, institutional endorsement, a physical survey or accessibility certification. The agent has not inspected the Windows database or its active release ID.

| Route / policy | Owner-reported Windows public result |
|---|---|
|University Entrance → Mapped entrance 10828149259, metric shortest|Approximately513m (earlier exact stored result513.10m/13edges)|
|Same endpoints, Directions only|Approximately799m/9edges; UI explicitly says “fewest eligible traversals”|
|Hostel Entrance → GHS Entrance, metric shortest|Earlier documented23.62m/3edges; owner reports public acceptance passed|
|Hostel Entrance → Faculty Block Entrance, metric shortest|Earlier documented163.28m/6edges; owner reports public acceptance passed|
|Hostel Entrance → Central Library|Unavailable|
|University Entrance → Hostel Entrance|Unavailable|
|Hostel Entrance → GHS Entrance, verified step-free|Unavailable|
|Demo Main Gate → Library|Retained synthetic baseline passed; previously256.88m/3edges, UI257m/4min|

These are **owner-reported Windows software results**, separate from automated synthetic tests. No real-device GPS, sign scanning/printing, physical path/door inspection or independent human/institutional approval is inferred. No new publication/reimport is needed for the wording update.

## Confirmed implementation semantics

`backend/app/services/routes.py` preserves the outdoor metric-distance implementation and uses the mixed engine for directions-only, fastest, QR/GPS, enabled indoor routing and restriction-aware cases. `backend/app/routing/mixed.py` assigns:

- **Metric + shortest:** each eligible traversal costs its stored distance in metres; minimise total stored distance. Measured/calibrated lengths are accepted, with the existing exception for estimated outdoor edges. Metric indoor routing additionally requires the floor's metric capability. Choosing a metric policy is not evidence of a field measurement.
- **Metric + step-free:** minimise eligible stored distance after the verified-step-free filters. Stairs and unknown accessibility are excluded; eligible start/destination anchors/access records must also qualify.
- **Metric + fastest:** minimise supported baseline seconds. Traversals lacking supported times are excluded; outdoor stairs without a supported time are excluded. These are model estimates, not live travel/queue prediction.
- **Directions only + standard (`profile=shortest` in the unchanged API):** every eligible outdoor/indoor/connector/entrance-transition arc has cost1. Minimise the number of eligible traversals, not metres or seconds. Unknown-distance arcs can be used; enabled directions-only indoor floors remain eligible. Known distance/ETA may still be displayed for the selected path; that does not turn them into the optimisation objective. Graph segmentation affects this traversal count.
- **Directions only + step-free:** minimise traversal count with the same verified-step-free eligibility requirements. Directions only does not bypass access or accessibility evidence. **Fastest is unavailable** for Directions only; the UI's existing switch from fastest to standard is preserved.

Both policies follow explicit directed stored connections and eligible mapped entrance/access candidates in one published projection. Private/restricted data, closed edges and ineligible bindings remain excluded. Connectors/transitions require enabled floor routing, available/verified connector/path/stop evidence and applicable open/verified anchor checks. Live restriction overlay/window filtering applies before route computation; unresolved restriction/freshness/release checks remain in force. Manual, confirmed QR and confirmed GPS starts retain their existing rules; GPS does not infer an indoor floor. Stable existing Dijkstra tie/priority rules are unchanged.

The two University Entrance results are therefore compatible: a13edge path may have a shorter stored length than a9edge path. **Do not expect513m under Directions only.** This change does not modify either result or recompute any published graph.

## Small public frontend change

The standard **Route preference** option reads **Shortest walking route** in metric mode and **Fewest eligible traversals** in Directions only mode. Its API value remains `shortest`. **Distance policy** now calls metric **Metric · stored path distances**, replacing the misleading public label **Verified metric paths**. Both controls reference a visible accessible description explaining objective and measurement limits. The admin validation form retains its existing **Verified metric paths** label; that is still a metric-eligibility selection, not a field-survey claim. The existing result message “Directions only · fewest eligible traversals. This is not a shortest-distance or fastest route.” remains.

## Exact data-preserving Windows update

Open PowerShell in the existing clean repository with Docker Desktop running Linux containers. This is a frontend rebuild only. It neither runs the helper nor modifies the API/database/release pointer. The existing API must remain healthy; `--no-deps` leaves it and the worker/database alone.

```powershell
$ErrorActionPreference = 'Stop'
function Invoke-ScnsStep {
    param([Parameter(Mandatory=$true)][scriptblock]$Action)
    & $Action
    if ($LASTEXITCODE -ne 0) { throw 'SCNS command failed. Stop here; preserve existing data.' }
}
Invoke-ScnsStep { git status --short }
if (git status --porcelain) { throw 'Preserve local changes first. Nothing reset.' }
Invoke-ScnsStep { git fetch origin feat/muj-connectivity-review }
Invoke-ScnsStep { git switch feat/muj-connectivity-review }
Invoke-ScnsStep { git pull --ff-only origin feat/muj-connectivity-review }
Invoke-ScnsStep { git merge-base --is-ancestor 278aed2 HEAD }
Invoke-ScnsStep { docker compose build frontend }
Invoke-ScnsStep { docker compose up -d --wait --no-deps --no-build frontend }
Invoke-ScnsStep { docker compose ps }
Invoke-RestMethod 'http://localhost:5173/api/v1/health/ready'
Start-Process 'http://localhost:5173/'
```

Hard-refresh Chrome with **Ctrl+Shift+R**. Do not rerun setup/import/correction/submit/approve/publish helpers. No migration, reseed, account change, volume removal or public hosting is required. Keep existing `.env`, accounts, uploads, QR markers/restrictions, drafts and immutable releases.

## Short manual check after the wording update

Owner subsequently reports the updated Windows controls work and confirms metric~513m versus Directions only~799m/9edges. This confirms those reported labels/results; it does not claim every keyboard/phone/fastest-switch subcheck below was manually repeated. See the separate [naming assessment/update](muj-naming.md) for the next bounded follow-up.

1. Select MUJ. **Distance policy → Metric · stored path distances**, **Route preference → Shortest walking route**. Choose **Starting point → University Entrance**, **Destination → Mapped entrance 10828149259**, then **Find walking route**. Expect approximately513m with the existing release/restrictions unchanged. The description explicitly says outdoor/OSM lengths may be estimated and metric eligibility is not field verification.
2. Choose **Distance policy → Directions only · unknown distance allowed**. Standard preference becomes **Fewest eligible traversals**, and fastest is disabled. Compute again: owner-reported baseline is approximately799m/9edges. The result still states fewest eligible traversals, not shortest distance/fastest. Different active restrictions or release can legitimately change the result; investigate rather than republish to force a match.
3. Switch back to metric: standard label returns to **Shortest walking route**; fastest becomes available and old results are cleared until recalculated. Switching from fastest to Directions only still selects the standard/traversal option. Step-free selection stays step-free when changing policy.
4. Under metric shortest, recheck Hostel→GHS (stored23.62m/3edges) and Hostel→Faculty (stored163.28m/6edges). Public cards can round to24m/163m. Library/cross-campus routes and verified step-free Hostel→GHS stay unavailable. Retain OSM attribution. Switch to Demo: Main Gate→Library remains257m/4min.
5. Check narrow-phone width and keyboard control labels/descriptions; no horizontal overflow. This update does not assert any new real-device, field or independent-review evidence.
