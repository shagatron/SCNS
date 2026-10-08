# QR signs — M4A update, installation and manual checks

M4A adds only the QR workflow from [the authoritative Milestone4 slice plan](../product/milestone-4-plan.md). Location, closures/outages, issue triage, PWA/saved-route caching and facility/load work remain later slices. Marker operations use current published nodes; draft edits/imports still cannot change public navigation. No real signs, real MUJ data or deployment are authorized here.

## Complete Windows PowerShell update

Run in your **existing SCNS checkout** with Docker Desktop Linux containers running. This block stops on command errors and stops if tracked/untracked changes need preservation. Commit your changes safely first if it reports them; do not reset/discard. Existing ignored `.env`/uploads/volumes remain intact. No accounts need bootstrap. No seed or demo setup command is part of this update.

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
$scnsLocalBranch = git branch --list feat/milestone-4a-qr-markers
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect local branches.' }
if ($scnsLocalBranch) {
    Invoke-ScnsStep { git switch feat/milestone-4a-qr-markers }
} else {
    Invoke-ScnsStep { git switch --track origin/feat/milestone-4a-qr-markers }
}
Invoke-ScnsStep { git pull --ff-only origin feat/milestone-4a-qr-markers }
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

Expected: migration `0015_qr (head)`, API/database ready, frontend and combined worker running; existing accounts/drafts/ACA tracing/plan processing/uploads/.env/public release unchanged. New inventory starts empty. Never use down -v, prune volumes, seed-demo, bootstrap, downgrade or reset existing data to update. To return to older application images with this schema, keep the database forward migration and seek a compatible update; do not downgrade a nonempty inventory (guard refuses loss). Build/migration failure leaves data intact; inspect errors before starting new app images.

Default `PUBLIC_APP_URL=http://localhost:5173` is correct for this computer's local demo. An existing `.env` is not edited automatically. Signs carry that canonical origin. A phone's localhost refers to the phone, so opening the local link on a physical phone requires a separately authorized reachable HTTPS origin; this slice does not publish/expose the environment. Native camera opening of links is sufficient; embedded camera scanning is not supplied.

## Exact outdoor QR test inputs/results

Use the existing owner/system administrator or campus operations account; passwords stay in the login form. Do not enter credentials in shell arguments. Do not change draft selections or publication as part of this check.

1. Open public homepage; select the existing synthetic Demo Campus. Manual Main Gate→Library, shortest, metric must still yield about **256.88m/three stored edges**, text directions and stored outdoor path. Your reported3C routes remain a separate baseline.
2. `/admin`, assigned synthetic campus→**QR markers**→**New marker**. Sign label `Synthetic Main Gate QR`; Published target node **outdoor · Gate** (stored node for Main Gate); intended position `Simulated sign at invented Main Gate node. Not a physical installation.` Click **Create planned marker**. Expect planned/v1, random stable link and NOT ACTIVE sign. Open the link in a separate/incognito browser: expect not-installed/verified state, manual fallback, no confirmation/start route button.
3. Installation fields: Installer `Synthetic demo operator`; Actual installed position `Simulated sign at invented Main Gate node. Not physically installed.`; Installation date **today's date in the campus timezone**; Verification date same; Evidence `Synthetic software verification only. No real campus or accessibility evidence.` Click **Record verification and activate**. Expect active/v2 and saved installation/audit. Download **SVG**, **PNG**, **PDF**: readable `http://localhost:5173`, sign label and full opaque `/q/...` link with confirmation instructions. They contain no password/session/evidence/private plan. This simulated verification does not approve real signage or accessibility.
4. Open that same link without admin credentials. Expect correct campus, label, published Gate node and verification date; nothing routes automatically. Click **I am at this marker now**. Starting point now `Confirmed QR · Synthetic Main Gate QR · Gate`. Destination **Library**; shortest/metric→**Find walking route**. Expect **256.88m (UI rounded257m), three stored outdoor edges**, directions and no continuous positioning claim. Swap is disabled while QR start is selected; choose a manual source to use place swap.
5. Reload: expect the normal QR location-confirmation screen, **no automatically recalculated route**. Confirm again if physically at the sign; navigating from an old saved link alone does not establish a current position.
6. In admin, Revocation reason `Synthetic sign removed for verification exercise.`→**Revoke marker**. On public link→**Check marker again**: expect revoked, no route start, manual fallback. Already-open pages check within15seconds/focus and every route request rechecks on the server. Unknown link such as `/q/00000000-0000-4000-8000-000000000000` gives unknown-marker/manual fallback. Disconnect/recheck gives a connection error; no new QR route is claimed offline.
7. Reassign/replan the same sign: choose **outdoor · Courtyard**, label `Synthetic Courtyard QR`, intended position `Simulated sign at invented Courtyard node.`→**Save changes and replan**. Expect stable ID/link, planned/new version, cleared installation. Re-enter actual Courtyard position and today's dates/evidence→verify/activate. Old link now displays the new label/node and requires fresh confirmation. Library distance is computed from Courtyard, **not hardcoded256.88m**. Do not install a moved physical sign until its new location is verified.
8. Two admin browser profiles: select the same marker in both. A enters label `My retained QR label` without saving; B saves `Other operator QR label`. A save returns stale conflict, keeps its input and shows latest version/label/state/target/intended position. Select **Use latest version and keep my inputs**, inspect them, then save deliberately; or **Discard my inputs and load latest**. No automatic overwrite. Editor/reviewer can inspect/download but fields are disabled; operations can manage only its assigned campus and does not gain draft graph permissions.

## Existing published indoor demo QR checks

These checks require your **already reviewed/published**3C synthetic floors. If the floors remain only in a draft, they will intentionally not appear in the QR target selector; M4A does not publish them. Do not reseed or overwrite ACA tracing to expose them.

Create a second sign `Synthetic Ground Door101 QR`, choose **indoor · Synthetic door101 · [your published ground-floor label]**, intended/actual `Simulated sign at synthetic door101, not a physical installation.`, installer `Synthetic demo operator`, today's installation/verification dates, evidence `Invented software fixture verification, not real navigation.` Activate normally. Open the stable link: expect correct synthetic campus/Academic House/building/floor/node label. Confirm, then choose the published synthetic destinations below (search the directory if not in the initial100):

| Start | Destination | Preference/policy | Expected |
|---|---|---|---|
| Confirmed Door101 QR | synthetic room **102** (public Ground102) | shortest/metric | **18m**, ground map and corridor/door directions |
| Confirmed Door101 QR | synthetic room **201** (public Upper201) | shortest/metric | **36m**, stairs transition and both floor views |
| Confirmed Door101 QR | room201 | step-free/metric | **57m**, lift transition, no stairs; synthetic verification only |
| Confirmed Door101 QR | **ISO** isolated ground room | shortest/metric | **No eligible route**, no fabricated straight-line connection |

These exact totals apply to the unchanged documented3C fixtures. If selecting another node (e.g. west corridor instead of door101) or a different retained map, distances follow those stored edges and should differ. Metric floors must have reviewed capability/calibration; directions-only floors require selecting directions-only policy, with unknown distance/ETA preserved.

Publication/rollback testing that changes data belongs in a separate disposable campus or automated test database, **not** your retained drafts/releases. Software tests verify normal independent release publication rebinds inventory; removed/restricted/disabled/moved targets retire or require verification; restoring a historical release does not reactivate a retired/revoked sign. Use explicit replan/verification afterwards. Raw sources remain private. No extra publication is required merely to create a sign for an already published node.

## Verification commands

On Linux/source tooling: `make check build test-unit test-integration test-migrations generate-api`; `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e`; `python scripts/cloud-build.py` for this cloud proxy/CA environment; `make test-container-publication`. Windows image builds use the Compose commands above. Unit/PostGIS/browser runners require installed uv/Node/Chromium in addition to Docker; cloud results are recorded separately from your Windows manual evidence. All destructive rehearsals refuse database names outside their explicit `_test`/`_e2e_test`/`_migration_test` boundaries. The container harness uses only owned test containers/database/storage, preserves developer volumes and actually processes floorplans through the built worker.

[QR contract/templates](../data/qr.md) · [verification evidence](../testing/verification.md). Physical QR printing/scanning, human accessibility/screen-reader testing, real campus data and load measurements remain unverified; later M4 slices are planned, not delivered.
