# Closures and lift outages — M4B

Only next planned4B is delivered: no location collection/GPS, issue triage, PWA/offline pack, real MUJ import or deployment. Existing public map releases, draft editors/imports and QR workflows are retained. Operators manage a separate versioned live restriction overlay. Synthetic software verification is never field/accessibility evidence.

## Complete Windows PowerShell update

Run from the existing SCNS directory, Docker Desktop Linux containers/Composev2 running. Preserve/commit local changes first if the guard stops. This forward-only update retains existing `.env`, accounts, drafts, released plans/tracing, QR markers, uploads and named volumes. Do not run any seed/bootstrap/demo helper/publication command.

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
$scnsLocalBranch = git branch --list feat/milestone-4b-closures
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect local branches.' }
if ($scnsLocalBranch) {
    Invoke-ScnsStep { git switch feat/milestone-4b-closures }
} else {
    Invoke-ScnsStep { git switch --track origin/feat/milestone-4b-closures }
}
Invoke-ScnsStep { git pull --ff-only origin feat/milestone-4b-closures }
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

Expected `0016_closures (head)`; readiness succeeds; new restrictions empty on first update; existing published release, draft/QR history and accounts retained. Never downgrade/delete a nonempty restriction history, run down -v, remove volumes or reseed to update. Failed migration stops before new application startup. No physical-phone/GPS or public URL setup is part of this slice.

## Exact synthetic outdoor manual cases

Use your existing owner/system-admin or campus operations login in `/admin`; passwords only in the form. Select the **existing synthetic campus**. Read-only editor/reviewer cannot change operational restrictions. These manual steps create labelled test incidents in the synthetic campus and explicitly reopen them afterwards; do not use real campus targets.

1. Public homepage, Main Gate→Library, shortest/metric: baseline **256.88m / three stored edges** (UI257m). Existing confirmed Main Gate QR should produce the same result. Existing Courtyard QR baseline139.29m/two edges remains.
2. Admin→**Closures and outages**→**New restriction**. Published restriction target choose **outdoor_path · Courtyard → West / West → Courtyard** (ordering may show reverse first; both directions share one physical path). Reason `Synthetic Courtyard walkway incident, not a real closure.` Start **now in your device's local timezone**; estimated end leave blank. Click **Record restriction**. Expect a new closed incident and overlay version increment; no draft/publication changes.
3. Public→**Check restrictions**; wait for the check to finish. Expect previous route hidden and source/destination retained. Recalculate Main Gate→Library shortest/metric: **310.20m / three stored edges** (UI310m), a detour without Courtyard→West. Select step-free and recalculate: **405.43m / four stored edges** (UI405m) through the eligible ramp, no stairs fallback. These totals apply to the unchanged documented synthetic graph; edits/other overlapping restrictions can change them.
4. Select that incident in admin. Reopening evidence `Synthetic software incident resolved; not a physical repair.` Check **I explicitly verified reopening or cancellation of this incident**→**Verify and reopen**. Public→Check restrictions→recalculate: baseline256.88m/three edges restored if no other restriction overlaps. History remains reopened; private evidence stays private.
5. Scheduled test: record the same target with start **30 minutes in the future**, estimated end **45 minutes in the future**, reason `Synthetic scheduled restriction; end requires operator verification.` Public status scheduled; current routes conservatively avoid it because it begins inside the one-hour policy window. Neither waiting beyond estimated end nor map rollback reopens it. Resolve explicitly with the same verification procedure; do not wait45minutes to test this rule (automated past-estimated-end coverage verifies it).
6. Failure/freshness: calculate a route, then use browser devtools Network→Offline. Expect previous route hidden and new-route button disabled. Return online→Check restrictions. Old invalidated result stays hidden; calculate again. For an API outage a failed check has the same behavior. Manual and QR start selections remain available; no offline new-route promise.
7. Two independent browser profiles, existing authorized account(s): both load overlay versionN. A fills reason `A retained synthetic restriction reason.` without saving. B records a labelled synthetic restriction and receivesN+1. A saves without reopening:409/conflict, retained reason and explicit latest-overlay comparison. Only deliberately selecting **Use latest overlay and keep my inputs** permits retry. If a response is lost, inputs freeze and **Retry unchanged operation** uses its original key; history must not duplicate the incident. Reopen all test incidents explicitly. Overlapping restrictions remain effective until each is resolved.

## Exact existing published indoor cases

Only use your **already published**3C synthetic floors, not retained ACA drafts. Draft-only target absence is expected; do not publish/reseed just to expose targets. Helper destinations are prefixed `Synthetic 3C demo:`; room codes remain102/201/ISO.

- Baseline: Synthetic support office102 from ground door101 confirmed QR or Synthetic study room101:18m same-floor; Upper Synthetic study room201:36m shortest via stairs/57m step-free via lift; Synthetic disconnected roomISO:no eligible route. Use existing published floor names/IDs, not guessed UUIDs.
- Admin→Closures and outages→New restriction. Select **connector · lift · Synthetic lift** from your current published synthetic group. Reason `Synthetic lift outage for software acceptance only.` Startnow device-local, estimated end blank→Record.
- Public→Check restrictions, same start101→destination201, step-free/metric: **No verified step-free route**, no stairs result. Shortest/metric: **36m via stairs**. Room102:18m unchanged. Ground QR requires the usual explicit physical-label confirmation; the QR itself is not revoked by an outage.
- Select lift incident, verification evidence `Synthetic lift software incident resolved; no real repair or access certification.` Check reopening confirmation→Verify and reopen. Public fresh check/recalculate step-free:57m lift restored. Other overlapping incidents must also be reopened.
- Publication/rollback preservation is automated in disposable campuses. Do **not** change your retained releases to manually rehearse it. Same target retains outage; removed/changed target becomes unresolved and campus routing fails closed until authorized rebind or explicit incident resolution. Restoring a historical map never clears unresolved state. Rebind requires current published target and substantive confirmed evidence; it keeps the restriction closed.

No simulated/real location tests are supplied in4B because location remains4C. Automated browser cases use synthetic data and Chromium desktop/mobile viewports in Linux; actual Windows4B/device/physical repairs/field surveys are separate owner evidence, not assumed. Windows4A owner reports update/planned/outdoor/revoke/reassign/indoor cases passed; Windows concurrency inconclusive, separate built investigation passed with no fix; owner sign downloads/physical scanning/printing remain unverified.

[API/temporal/privacy contract](../data/closures.md) · [actual verification](../testing/verification.md). Required contributor checks: `make check build test-unit test-integration test-migrations generate-api`; `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e`; `python scripts/cloud-build.py`; `make test-container-publication`. Runners restrict destructive rehearsals to owned `_test` databases; no developer data is reset. Existing cloud prerequisites/runtime are reused.
