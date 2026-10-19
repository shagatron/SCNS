# Academic submission: retained-data main update and Docker startup

`main` is the submission landing branch. The accepted application comes from feat/muj-indoor-demo136667f, retaining the MUJ homepage, complete directory/planner, normal publication/admin flows and integrated Outdoor / Indoor demo. Native-Windows experiment commits are excluded. Existing feature branches remain intact; no submission tag is created without final acceptance.

## Existing Windows checkout: safe main update and start

Use ordinary PowerShell, Docker Desktop running in **Linux containers** mode, and the existing checkout below. This block stops on dirty/divergent Git state without resetting work. It preserves `.env`, Docker data volumes, private files/journals/accounts/drafts/releases/QR/restrictions and the temporary phone-access override. Existing database data is used, not initialized/reseeded/reimported. No native PostgreSQL/Python/Node installation is needed for Docker, and existing native setup is not removed.

The single explicit `-f compose.yaml` deliberately excludes temporary/automatic phone overrides. **Laptop-only:** localhost5173/8000 and loopback database54329. No LAN/firewall change or public deployment. Worker startup resumes normal private queued processing using the retained database/storage; the demo itself queues no job. Do not start a second host API/worker against the same database with different storage.

```powershell
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath 'C:\Users\Aaditya Shah\SCNS'
function Invoke-ScnsSubmissionStep {
    param([Parameter(Mandatory=$true)][scriptblock]$Action)
    & $Action
    if ($LASTEXITCODE -ne 0) { throw "SCNS command failed ($LASTEXITCODE). Stop; preserve existing work/data." }
}
$ScnsDirty = git status --porcelain
if ($LASTEXITCODE -ne 0 -or $ScnsDirty) { throw 'Preserve local Git changes first. No reset/stash/clean was performed.' }
Invoke-ScnsSubmissionStep { git fetch origin refs/heads/main:refs/remotes/origin/main }
$ScnsMainExists = git branch --list main
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect local branches.' }
if ($ScnsMainExists) {
    Invoke-ScnsSubmissionStep { git switch main }
} else {
    Invoke-ScnsSubmissionStep { git switch --no-track -c main origin/main }
}
Invoke-ScnsSubmissionStep { git pull --ff-only origin main }
Invoke-ScnsSubmissionStep { git merge-base --is-ancestor 136667f690398ffdb1073222d8acf2cce2ad2638 HEAD }
$ScnsLocalHead = git rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw 'Cannot read local HEAD.' }
$ScnsRemoteHead = git rev-parse origin/main
if ($LASTEXITCODE -ne 0 -or $ScnsLocalHead -ne $ScnsRemoteHead) { throw 'Local/remote main differ. Preserve local commits; stop without reset.' }
Write-Host "Submission main: $ScnsLocalHead"
$ScnsPhoneOverride = Join-Path $env:TEMP 'scns-phone.override.yaml'
if (Test-Path -LiteralPath $ScnsPhoneOverride) { Write-Host 'Phone override preserved on disk, excluded for laptop-only startup.' }
$ScnsPreviousAppUrl = $env:PUBLIC_APP_URL
try {
    $env:PUBLIC_APP_URL = 'http://localhost:5173'
    # Start/check the EXISTING database BEFORE waiting on API readiness.
    Invoke-ScnsSubmissionStep { docker compose -f compose.yaml up -d --wait --no-deps --no-build db }
    Invoke-ScnsSubmissionStep { docker compose -f compose.yaml exec -T db pg_isready -U scns -d scns }
    Invoke-ScnsSubmissionStep { docker compose -f compose.yaml build api frontend }
    Invoke-ScnsSubmissionStep { docker compose -f compose.yaml up -d --wait --no-deps --no-build --force-recreate api }
    Invoke-ScnsSubmissionStep { docker compose -f compose.yaml up -d --no-deps --no-build import-worker }
    Invoke-ScnsSubmissionStep { docker compose -f compose.yaml up -d --wait --no-deps --no-build --force-recreate frontend }
    Invoke-ScnsSubmissionStep { docker compose -f compose.yaml ps db api import-worker frontend }
    Invoke-RestMethod 'http://localhost:5173/api/v1/health/ready'
    $ScnsEducational = Invoke-RestMethod 'http://localhost:5173/api/v1/educational/indoor-school'
    if ($ScnsEducational.version -ne 'indoor-school-v1' -or $ScnsEducational.floors.Count -ne 2 -or $ScnsEducational.rooms.Count -ne 7) { throw 'Unexpected educational API response. Preserve data and inspect startup.' }
    Start-Process 'http://localhost:5173/'
} finally {
    $env:PUBLIC_APP_URL = $ScnsPreviousAppUrl
}
```

Expected: existing database accepts connections, API/worker/frontend run, proxied readiness succeeds, educational versionindoor-school-v1 has2floors/7rooms. The owner's existing MUJ and Demo releases should appear unchanged. If MUJ is absent, stop and inspect the selected existing Compose project/volumes; **do not import/seed/publish a substitute**. Git does not contain the owner's live database or private uploads.

Do not run migrations, `make demo`, seed/bootstrap/import/naming/review/publication helpers, restore commands, `down -v`, volume deletion or forced Git updates for this cleanup. An unsuccessful build/start is safe to retry after diagnosis; it has no data activation step to duplicate. On later starts without code changes, reuse database-first `up`/readiness/worker/frontend steps with `--no-build`; building is needed only after updating code/assets. To stop data-preservingly: `docker compose -f compose.yaml stop frontend import-worker api db`.

## Database-related readiness failures

Owner previously observed database/frontend stopped while API-only `up --no-deps` waited on readiness and returned database503s. Starting the existing database and app services resolved it. Inspect `docker compose -f compose.yaml ps` and `exec -T db pg_isready -U scns -d scns` first. Then inspect sanitized local API logs if needed. Do not paste credentials/raw private files into chat. A readiness failure is not a reason to recreate volumes, reseed or replay imports.

## Phone access is separate

This update does **not** enable phone/LAN access and does not modify/delete the existing temporary override. A phone cannot use the laptop's `localhost`. Existing phone access, if separately configured and authorized, uses its reviewed override, origin and host binding; preserve it but do not silently combine it with these laptop commands. Real-device GPS also needs browser secure-context/permission conditions and separate verification. Submission remains local, with manual/QR fallback and no continuous tracking.

## Fresh database versus retained data

For genuinely new installations see the root [README fresh-clone section](../../README.md#fresh-clone-with-genuinely-new-empty-data). It uses a distinct Compose project and explicitly documents first-time schema/demo initialization; those commands are never a retained-data update. A fresh installation has synthetic Demo Campus only, no owner's MUJ/E22 release/accounts/private plans. The standalone compatibility `/indoor-demo` remains available; no fake MUJ dataset is required.

[Presentation-day exact inputs](../submission/presentation.md) · [DSA source/bounds](../submission/dsa.md) · [audit/evidence/remaining files](../submission/audit.md).
