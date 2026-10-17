# MUJ complete-path audit: data-preserving Windows preflight

This task found **no additional unambiguous source-supported graph correction** beyond already-applied v2. It supplies a complete inventory, numbered questions and **read-only** actual-release preflight. There is no APPLY mode, new preparation version, automatic draft selection/creation, naming replay, source approval, warning acknowledgement, submission or publication. Existing drafts, public MUJ/E22 and Demo releases remain active. [Findings/maps/route matrix](../data/muj-path-audit/README.md).

The original Windows release UUID and content/artifact checksum are **fetched**, not guessed from old documentation. Authenticate privately using your existing owner account (normal campus draft-read/audit permissions). The real SessionOut top-level `user_id` is required; passwords are never printed, saved or passed as command arguments. Keep reports private; they include normal source/review metadata, not passwords/session tokens.

## Complete PowerShell update and read-only run

Run from your existing repository with Docker Desktop using Linux containers. This block deliberately selects **laptop-only loopback** startup. It preserves `$env:TEMP\scns-phone.override.yaml` unchanged but **does not include it**, so an obsolete hotspot IP cannot prevent startup. Explicit `-f compose.yaml` also avoids an automatic alternate Compose file; normal `.env` data/settings stay on disk. Runtime PUBLIC_APP_URL is temporarily set to the actual loopback origin; the shell's prior value is restored afterward. No phone/LAN/firewall configuration is enabled or deleted. Your preserved override may be deliberately reused later after checking its IP/origin; this task does not validate phone access.

```powershell
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath 'C:\Users\Aaditya Shah\SCNS'
function Invoke-ScnsStep {
    param([Parameter(Mandatory=$true)][scriptblock]$Action)
    & $Action
    if ($LASTEXITCODE -ne 0) { throw "SCNS command failed (exit $LASTEXITCODE). Stop; preserve data and inspect output." }
}
Invoke-ScnsStep { git status --short }
$ScnsDirty = git status --porcelain
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect repository; stop.' }
if ($ScnsDirty) { throw 'Preserve/commit local changes first. Nothing reset.' }
Invoke-ScnsStep { git fetch origin refs/heads/feat/muj-path-connectivity:refs/remotes/origin/feat/muj-path-connectivity }
$ScnsBranch = git branch --list feat/muj-path-connectivity
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect branches.' }
if ($ScnsBranch) {
    Invoke-ScnsStep { git switch feat/muj-path-connectivity }
} else {
    Invoke-ScnsStep { git switch --no-track -c feat/muj-path-connectivity refs/remotes/origin/feat/muj-path-connectivity }
}
Invoke-ScnsStep { git pull --ff-only origin feat/muj-path-connectivity }
Invoke-ScnsStep { git merge-base --is-ancestor 8798fa35355bb292b0aef186f6f037dc58d0101a HEAD }
Invoke-ScnsStep { git rev-parse HEAD }
$ScnsPhoneOverride = Join-Path $env:TEMP 'scns-phone.override.yaml'
if (Test-Path -LiteralPath $ScnsPhoneOverride) {
    Write-Host 'Existing phone override preserved; deliberately excluded for laptop-only startup.'
}
$ScnsPreviousAppUrl = $env:PUBLIC_APP_URL
try {
    $env:PUBLIC_APP_URL = 'http://localhost:5173'
    Invoke-ScnsStep { docker compose -f compose.yaml build api frontend }
    # Retained database first; no API-only readiness wait against a stopped DB.
    Invoke-ScnsStep { docker compose -f compose.yaml up -d --wait --no-deps --no-build db }
    Invoke-ScnsStep { docker compose -f compose.yaml exec -T db pg_isready -U scns -d scns }
    Invoke-ScnsStep { docker compose -f compose.yaml up -d --wait --no-deps --no-build --force-recreate api }
    Invoke-ScnsStep { docker compose -f compose.yaml up -d --wait --no-deps --no-build --force-recreate frontend import-worker }
    Invoke-ScnsStep { docker compose -f compose.yaml ps db api frontend import-worker }
    # Base frontend is explicitly 127.0.0.1:5173; readiness matches that binding.
    Invoke-RestMethod 'http://localhost:5173/api/v1/health/ready'
    Invoke-ScnsStep { docker compose -f compose.yaml exec -T api alembic current }
    # Secure interactive terminal: no -T, redirected stdin or pasted passwords.
    Invoke-ScnsStep { docker compose -f compose.yaml run --rm --no-deps -e PUBLIC_APP_URL=http://localhost:5173 api python -m app.cli.muj_paths preflight }
    Start-Process 'http://localhost:5173/#explorer'
} finally {
    $env:PUBLIC_APP_URL = $ScnsPreviousAppUrl
}
```

There is **no migration** in this update (head remains0016_closures); `alembic current` only inspects. No seed, bootstrap, setup/import/naming/publication helper replay, `down -v`, database reset or volume removal. Existing private storage is mounted normally by Compose; only the new private report is added. Existing worker can continue its normal preparation jobs; this helper never uploads or applies one. API/frontend/worker recreation replaces processes/images, not volumes/data. Stop on any failure; do not delete a volume to fix readiness. These are instructions for the owner, not a claim they were executed on Windows.

## Expected preflight and safe recovery

1. Enter existing owner username and hidden password **in your local terminal**. No credentials in chat. Normal login/logout session audits occur; there are no dataset/workflow writes.
2. The helper reads and hashes the **actual currently published** MUJ artifact; obtains its frozen review packet; reconstructs original/clone ancestry from complete review diffs and unique normal creation audits; verifies each full checksum, unchanged source metadata and exact public projection. Frozen graph editor endpoints are deliberately not used. It rereads the publication descriptor (including restriction generation), every ancestry packet and campus draft listing before saving evidence.
3. Expected unchanged source graph:295nodes/700directed edges/22anchors/55places; original correction `already_applied`; both E22 fields `TMA Pai Auditorium entrance`; zero unexpected differences/blockers, `proposed_changes: []`, `graph_writes: 0`, `drafts_created: 0`. Existing editable/review drafts are listed with current versions; **none is selected or altered**. E05 and all other names/stable IDs/geometry/costs/accessibility remain unchanged. The actual publication UUID/checksums/version are printed without assuming Draft2version5or the former draftversion6.
4. The report is durably saved with a new UUID filename under `/app/storage/private/muj-path-audit/preflight-<UUID>.json` on your existing private volume. It includes actual source approvals/validation history, private frozen graph fingerprint and ancestry checksums. It is a **current-state verification report**, not an invented historical application/audit receipt. Existing import/update/naming journals and receipts stay untouched. Only a compact summary is printed; sources/validation details remain in the private report.
5. If the API response/report save is interrupted, simply rerun the same `preflight` command inside the block/origin configuration. It performs no graph writes or draft creation, so there is no uncertain APPLY outcome or duplicate draft to reconcile. New reports retain old ones; a failed report save does not mean data was changed. On an owner edit, missing permission, changed release/restriction/version, incomplete/truncated draft list, unexpected source/diff/checksum or missing/bounded ancestry audit, stop and preserve current data. Inspect **Admin → Audit records → Next audit page** and the release's review history. Do not repair/reimport/choose a draft automatically or relax a checksum guard.

Ancestry search is bounded to16frozen generations and10,050audit entries per needed parent; current dashboard listing supports100draft/review rows. Exceeding those bounds or a missing approved artifact stops safely and needs explicit inspection. No inferred old-parent UUID. A nonpublished MUJ campus returns the normal404and stops without fabricating a release. The cloud cannot inspect your Windows database or supply its new release UUID.

To copy the latest private report without credentials (after startup, same repository):

```powershell
$ScnsReport = docker compose -f compose.yaml exec -T api python -c "from pathlib import Path; print(max(Path('/app/storage/private/muj-path-audit').glob('preflight-*.json'),key=lambda p:p.stat().st_mtime_ns))"
if ($LASTEXITCODE -ne 0) { throw 'Cannot locate report.' }
$ScnsApiContainer = docker compose -f compose.yaml ps -q api
if ($LASTEXITCODE -ne 0 -or -not $ScnsApiContainer) { throw 'API container unavailable.' }
$ScnsReportCopy = Join-Path $env:TEMP ('scns-muj-path-preflight-' + [guid]::NewGuid().ToString() + '.json')
docker cp "${ScnsApiContainer}:$($ScnsReport.Trim())" $ScnsReportCopy
if ($LASTEXITCODE -ne 0) { throw 'Cannot copy private report.' }
Write-Host "Private report copied to $ScnsReportCopy; inspect locally, never commit credentials or private data."
```

## Inspect existing state, without making another draft

Open **Admin**, sign in normally, select the MUJ campus under **Assigned campus**, and inspect existing **Selected draft** choices; do not click **Create draft** for an empty correction. **Outdoor graph** shows that selected draft, not an editable public release. Use **Review and releases → Release history and rollback** for frozen publication evidence and rollback availability; this audit does not change any approval or publication. Do not click publish or acknowledge warnings as part of these checks.

In public **Explore campus**, choose MUJ, then original planner **Route preference → Shortest walking route**, **Distance policy → Metric · stored path distances**. Test:

- Hostel Entrance → GHS Entrance: approximately23.62m,3edges.
- Hostel Entrance → Faculty Block Entrance: approximately163.28m,6edges.
- University Entrance → Mapped entrance10828149259: approximately513.10m,13edges. Directions only switches to **Fewest eligible traversals**, approximately799.32m/9edges, not shortest distance/fastest.
- Hostel Entrance → Central Library: unsupported arrival; University Entrance → Hostel Entrance: no eligible cross-campus route; verified step-free remains unavailable. Unknown accessibility is unchanged.
- Search **TMA Pai Auditorium entrance**: E22 visible, unresolved E05 name unchanged. Demo Campus Main Gate → Library remains approximately257m/4min,3edges. Original homepage, full directory/actions, contextual planner errors and dark map styling remain from8798fa3.

Compare with prior owner-reported Windows checks; no newly verified Windows, live GPS, physical/accessibility or institutional evidence is claimed. [Numbered questions](../data/muj-path-audit/questions.md) specify what additional source/campus evidence could justify a later reviewed draft-only correction. This task does not open unsupported Library, subway or through-building connections merely to improve route counts.
