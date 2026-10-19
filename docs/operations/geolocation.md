# Optional outdoor location — M4C

Only4C is delivered. The polished planner and existing manual/QR/indoor/outdoor navigation are preserved. This pilot requires physical landmark confirmation after a location suggestion; no GPS-to-path approach, indoor inference, continuous tracking or real-campus certification. The synthetic campus is near0°,0°; real device fixes in India should fail coverage and retain manual/QR starts. No LAN/phone access or deployment.

## Complete Windows PowerShell update

Run in the existing SCNS directory with Docker Desktop Linux containers running. Preserve local changes if the guard stops. No environment file, account, data, QR/restriction, draft/release, upload or volume is deleted/reseeded. No new migration: inherited0016_closures/head remains.

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
$scnsLocalBranch = git branch --list feat/milestone-4c-geolocation
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect local branches.' }
if ($scnsLocalBranch) {
    Invoke-ScnsStep { git switch feat/milestone-4c-geolocation }
} else {
    Invoke-ScnsStep { git switch --track origin/feat/milestone-4c-geolocation }
}
Invoke-ScnsStep { git pull --ff-only origin feat/milestone-4c-geolocation }
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

Expect readiness success and a Use my location button on http://localhost:5173/. On9October2026 the owner reported Windows Chrome **simulated-browser** checks passed at604ace8:±5m Gate confirmation→Library257m/4min;100m/outside-campus/disconnected Garden/one-way East Exit rejection; override cleared and manual Main Gate→Library257m/4min. This limited report is separate from automated tests and does not verify real-device GPS or a broad Windows polish pass. Other Windows location cases remain unreported; parser/mocked command checks on Linux do not constitute Windows execution. See [evidence](../testing/verification.md).

## Beginner Chrome simulation: precise coordinates and accuracy

These steps simulate a position, not real-device/permission/field evidence. Use the existing synthetic campus and published release. Keep actual incidents/data unchanged; baseline totals assume no overlapping active restrictions.

1. Open http://localhost:5173/ in desktop Chrome. The page must not request location on load. PressF12 to open DevTools. PressF1 (Settings), choose Experiments, enable **Protocol Monitor**, then close/reopen DevTools if required. Open the DevTools three-dot menu→More tools→Protocol monitor. This built-in tool needs no app/plugin installation.
2. Chrome Sensors custom locations may omit an accuracy control or use an accuracy too large for this pilot. For reproducible5m accuracy, enter this exact JSON in the Protocol Monitor command input and send it (the command editor/pencil button also accepts command Emulation.setGeolocationOverride and these parameters):

```json
{"cmd":"Emulation.setGeolocationOverride","args":{"latitude":0.0002,"longitude":0.00015,"accuracy":5}}
```

3. Back in the app click **Use my location**. When Chrome prompts, choose **Allow**. Expected: reported accuracy radius±5m, suggested **Gate**, approach approximately0m, no computed route until confirmation. For this synthetic software test click **I am at this landmark now**. It is not a claim that an invented physical gate exists.
4. Destination **Library**, preference **Shortest walking route**, distance policy **Metric · stored path distances** (formerly **Verified metric paths**)→Find walking route. Original synthetic graph:256.88m/three stored edges, UI257metres/4min estimated. Route begins at confirmed Gate; approach excluded. Selecting a suggestion alone must never establish the start.
5. Optional approach demonstration: send override latitude0.00023, longitude0.00016, accuracy5, request location again. Expect nearbyGate suggestion with a nonzero approximate straight-line approach; confirm only in synthetic simulation. Route distance still begins atGate, not the simulated dot.
6. Send the following overrides one at a time, then press Use my location. No automatic retry/acquisition.

| Latitude | Longitude | Accuracy metres | Expected |
|---|---|---|---|
|0.0002|0.00015|100|Too inaccurate: exceeds20m; no observation transmitted to matching endpoint; manual/QR controls retained|
|1|1|5|Outside this published campus; no location start|
|0.00275|0.0035|5|No suitable published path/landmark (disconnectedGarden)|
|0.0008|0.0035|5|No suitable outgoing start at one-wayEast Exit; no backward shortcut|
|0.0002|0.00015|5|Recover normal Gate proposal, requiring fresh explicit confirmation|

To change the override, use the same command JSON with the table's latitude/longitude/accuracy values. Send `{"cmd":"Emulation.setGeolocationOverride","args":{}}` to simulate unavailable position; **Emulation.clearGeolocationOverride** with empty args removes the override.

7. Denial: Chrome address-bar site controls→Site settings→Location→Block, reload, click Use my location. Expect permission-denied fallback. Restore **Ask/Allow**, reload and reapply the synthetic override to continue.
8. Deterministic stale and timeout failures (optional): DevTools Console accepts these **temporary test-only overrides**, then click Use my location. Reload restores the real browser method; do not paste real coordinates. These bypass sensor behavior and are simulated failures, not device testing.

```javascript
// Stale fix: two minutes old, accuracy5m.
Object.defineProperty(navigator.geolocation, 'getCurrentPosition', { configurable: true, value: success => success({ coords: { latitude: 0.0002, longitude: 0.00015, accuracy: 5 }, timestamp: Date.now() - 120000 }) });
```

Expect stale-location message, no matching request, manual/QR selection usable. Reload, then optionally test timeout:

```javascript
Object.defineProperty(navigator.geolocation, 'getCurrentPosition', { configurable: true, value: (success, failure) => failure({ code: 3 }) });
```

Expect timed-out fallback. Reload after either temporary console simulation to restore browser geolocation.

## Revalidation and regressions

- A confirmed fix expires after60seconds (default). Request again and physically confirm or choose manual/QR. No coordinates/confirmation survive reload. Clear route/Discard location/manual selection removes GPS memory. Changing the proposed landmark also removes its previous confirmation.
- Confirm and calculate, then DevTools Network→Offline: GPS confirmation/routes are discarded, new routing disabled; reconnect/check restrictions requires new request/confirmation. Do not infer a floor even when viewing an indoor plan.
- A normal release/restriction change invalidates old GPS starts; permission revocation and failed live checks also discard them. Automated tests simulate those responses and normally publish disposable indoor data. Do not change retained releases or create outages just for this manual test. Existing incident verification/cleanup procedures remain in [closures guide](closures.md).
- Choose Starting point **Main Gate** manually→Library: same baseline256.88m. Existing active QR link still requires its usual explicit marker confirmation. Retain the prior owner3C18m/36m/57m/no-route evidence separately.
- If your3C indoor demo is already published, a confirmed outdoorGate can route to its room/office through mapped entrances. Step-free excludes unavailable lifts and never falls back to stairs; exact outdoor-to-room total depends on your published graph. Do not publish/reseed retained ACA drafts to expose floors.

Optional policy defaults and request/privacy contracts: [location contract](../data/location.md). Required contributor checks: make check/build/test-unit/generate-api/test-integration; affected desktop/mobile location/navigation/QR/closures/indoor/publication journeys; frozen image build and built worker/browser smoke. No new schema means prior0016 migration evidence is reused, not a new migration pass claim. Real-device accuracy, physical approach/wall knowledge, accessibility, GPS availability and actual Chrome UI versions/Windows execution remain unverified; real university data comes later.
