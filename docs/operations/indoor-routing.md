# Indoor/mixed routing — update and manual verification

Milestone 3C adds explicit connectors and entrances to the existing floor and graph editors. Editing/importing still does not publish. Use existing assigned accounts; no new password or bootstrap is required. All supplied fixture assertions are invented for testing. Do not replace a retained developer plan/tracing or publish its draft for test convenience.

## Complete data-preserving Windows PowerShell update

From the **existing SCNS checkout** with Docker Desktop running Linux containers and Compose v2. Inspect status first. Commit/preserve unexpected local work; do not reset/discard it. Stop if switching/pulling/building/migrating fails. Preserve `.env`, accounts, upload storage, database volumes, published releases and draft history.

```powershell
git status --short
git fetch origin
git switch feat/milestone-3c-indoor-routing
git pull --ff-only origin feat/milestone-3c-indoor-routing
docker compose build api frontend
docker compose stop api frontend import-worker
docker compose up -d --wait db
docker compose run --rm --no-deps api alembic upgrade head
docker compose up -d --wait --no-build api frontend import-worker
docker compose ps
Invoke-RestMethod http://localhost:5173/api/v1/health/ready
Start-Process http://localhost:5173/
Start-Process http://localhost:5173/admin
```

If this branch is not yet local, `git switch --track origin/feat/milestone-3c-indoor-routing` creates the tracking branch; otherwise use the command above. Migration0014 creates connector/policy/transition tables and dependency/integrity guards without seeding or changing an active release. Never run bootstrap, seed-demo, downgrade/reset or `docker compose down -v` to update an existing installation. Non-test downgrade with routing data refuses destructive loss. Private original/image BYTEA stays in the database; private staged import files remain in the existing volume. Actual Windows execution is not claimed by cloud tests.

Existing Linux source checkout:

```bash
make setup                 # frozen dependencies; keeps an existing .env
# Stop application services before migrating/updating the source processes:
docker compose stop api frontend import-worker
make db migrate            # forward-only developer migration
make dev                   # API, frontend and combined import/floorplan worker
```

For container startup use the same build/stop/migrate/start sequence above in a shell. No external service, paid account or public deployment is required.

## Exact synthetic prerequisites and inputs

Use a separate disposable synthetic campus/draft for review/publication experiments. Existing owner-reported Windows ACA Ground Floor tracing remains separate evidence and must be preserved; its reported scale 0.05m/reference-pixel and independent approvals do not establish current cloud data. If reusing an existing test floor, confirm reference dimensions600×400/current approved derivative+calibration and compare tracing before loading a fixture. The 3C ground fixture deliberately updates stable 3B records with **invented dated accessibility assertions**; do not apply it to real or unsurveyed production records.

1. Owner/editor signs in `/admin`, selects the assigned synthetic campus and editable draft. Reviewer uses a different browser profile/assigned account. Verify current public Main Gate→Library first: shortest gives approximately256.88m, three stored edges and text directions; step-free is also available in the synthetic fixture.
2. In **Floors and floorplans**, choose Academic House (`ACA`). Create G/`Synthetic route Ground`, ordering0, and F1/`Synthetic route Upper`, ordering1, **leave elevations blank**. For **each** floor, upload `data/demo/floorplans/synthetic-ground.png`, page1, rightsSynthetic, title `Synthetic routing G`/`Synthetic routing F1`, provenance `Invented two-floor topology test only, not an institution source`, attribution `Synthetic 3C test plan`. Mask x 480,y 320,width 100,height 60. Wait for actual worker Ready; apply explicitly. Each floor has its own selected layer and frame; the shared image is a test reference, not evidence floors have identical real layouts.
3. Calibrate **each** selected plan: primary start(100,100), end(300,100), distance10m; independent nonparallel check start(100,100), end(100,300), distance10m; uncertainty0.05m, qualityuniform, date 2026-10-01, evidence `Synthetic known10m per200 reference pixels; test assertion only`. Reviewer independently approves each current sanitized derivative and each calibration. Expected scale 0.05m/reference-pixel; no floor height inferred.
4. In **Indoor floor editor**, select G and load `data/demo/indoor-routing/ground.json`; inspect then **Save indoor graph to draft**. Select F1, load `data/demo/indoor-routing/upper.json`, inspect/save. Public101/102 and201/202 have explicit doors and local paths. Restricted R1/R2 must stay private; isolated ISO intentionally has a door with no connected corridor. Source/evidence strings carrying PRIVATE sentinels remain private. All widths/slopes/heights unknown stay blank.
5. In **Outdoor graph**, inspect the Academic House public place's existing explicit entrance anchor and its stored outdoor node; this will be the west fixture anchor. Add a second anchor for that **same place**, selecting the existing public `Central` outdoor node deliberately (an invented alternate entrance for this fixture only), open and `verified_step_free` only for this synthetic test; evidence `Invented alternative entrance synthetic test2026-10-01 only`. Save. Do not create geographic coordinates from floor pixels. Record/select these two anchor UUIDs, not an unrelated Library/place anchor.
6. Open **Connections and entrances**, expand **Load synthetic connection fixture**. Select Ground fixture floor G, Upper fixture floor F1, West entrance anchor fromstep 5, East entrance anchor fromstep 5. Upload `data/demo/indoor-routing/connections.json`. Loader binds current layer/building/floor/anchor references and performs non-mutating server preview. Inspect proposed groups/stops/directions/costs, then **Preview connections** and **Save connections to draft**. No public route changes yet.
7. Groups: stairs, lift, westentrance, eastentrance. Both floors have explicit stored-node stops. Stairs measuredsynthetic 6m/baseline 12s/not_step_free; lift measuredsynthetic 15m/movement 8s/wait 20s/verified_step_free; vertical/horizontalrise remainNULL. West entrance 2m/movement 3s; east 12m/movement 3s, bothdated test assertions. Distances are explicit test traversal costs, not computed from floor order or a fabricated line. Public uncertainty notes must contain no confidential text.

## Manual admin controls and failure checks

- Add/edit connector group: buildingACA, codeunique, label, stairs/lift/ramp/entrance, availabilityunknown bydefault. Supply private evidence/date only if warranted. Unknown/unavailable groups are excluded from routing. Select a floor stop's current floor/selected layer and exact stored node; use **Connection inspection floor** to pan/zoom/Fit and select its stored node. Entrance group requires entrance-kind node. No automatic floor/node creation occurs.
- Directed floor path: choose group/fromstop/tostop (different floors), leave unknown costs/dimensions blank, choose accessibility explicitly. **Apply connection fields locally** stages changes. **Pair reverse direction** creates/synchronizes the reverse row; **Make one-way** confirms its removal. Entrance form uses group/stop/buildinganchor/direction/priority. Server rejects foreign campus/floor/reference, positive-step step-free assertions or inconsistent pair costs.
- Delete a group/stop/path: **Delete connection and dependencies** lists every affected UUID and reverse/dependent link before confirmation. Undo/redo before save. Save increments draft version once and records actor/batch audit atomically. A failed write must leave prior data/version/audit unchanged. Do not delete developer topology to test a guard.
- Recovery: select a connection, type `unfinished-cost` in distance m, reload; raw text must remain. Apply rejects nonfinite text without removing it. **Cancel form** discards deliberately. Recovery is same-tab2h/2MB/30 actions, cleared after logout/session expiry/revocation. Private buffers cannot reappear from an ended-session effect.
- Conflict: tabsA/B load same group. A applies local label`My retained staircase`, B applies`saved concurrent staircase` and saves. A save reportsconflict and **Keep my connection**/**Use server connection** choices; compare values explicitly, choose, then review and save again. Independent changes merge. Unresolved choices and raw-field conflicts survive reload. If the same record changed while form text remains unapplied, compare the displayed strings and choose **Retain my unapplied fields** or **Use server fields** explicitly. **Compare latest draft** also compares before saving; selected-plan change requires explicit comparison/rebinding. Frozen/submitted revisions remain read-only; reviewer can inspect; operations has no editor. CSRF/campus/version protections stay server enforced.
- **Validate saved connections** and existing floor graph validation explain unknown/unavailable/unlinked/incomplete costs and capability gaps. Inspect full diagnostics and their stable IDs. Fix blocking errors; a synthetic warning acknowledgement never certifies accessibility. Plan replacement/recalibration/floor or referenced node/anchor deletion must refuse invalidating saved dependencies.

## Review and public route manual test

On a **disposable test draft only**, Review and releases → queue pairs using **Evidence start/destination**, standardfound, step-freefound, metricpolicy, maximumblank, reason `Invented calibrated two-floor route evidence only; no surveyed campus claim`, **Add route evidence pair** for each:

- Ground101→Ground102.
- Upper201→Upper202.
- Ground101→Upper201 and reverse.
- MainGate→Upper201 and reverse.

This queues12 cases. Run authoritative validation, inspect route IDs/costs and every diagnostic. Enabled floors need successful standard evidence and explicit step-free results; include explained negative cases for unavailable/one-way restrictions. Review/acknowledge each warning with substantive reason → submit exact current version → independent reviewer inspects rights/calibration/topology/routes/privateprojection → approve exact content → explicitly confirm publish. No draft edit/import auto-publishes. The retained developer draft must stay unpublished unless its owner deliberately chooses publication.

After fixture publication, publicplanner selects building/floor-disambiguated rooms:

| Input | Preference / policy | Expected |
| --- | --- | --- |
| Ground101↔Ground102 | Shortest or step-free / metric |18m, stored local paths |
| Ground101↔Upper201 | Shortest / metric |36m, stairs and clear floor transition |
| Ground101↔Upper201 | Step-free / metric |57m, lift; no stairs |
| MainGate↔Upper201 | Shortest or step-free / metric |Outdoor/entrance/indoor/connector directions in both directions |
| Ground101→ISO | Any / metric |No eligible route |
| MainGate→Library | Shortest / metric |256.88m/three stored outdoor edges |

Use **Building and floor view** to switch outdoor/G/F1; route instruction **Show…** controls choose correct departure/arrivalfloor. Indoor polylines stay within thatfloor frame; transition markers never draw a cross-frame line. Pan/zoom/Fit plan; original/source/evidence/restrictedrecords remain absent. Hide map and follow text directions. Reload completed shared URL: same public IDs/profile/mode/release recompute the route. A different-release link clears old choices/results and asks for current selections. Failedfloorimage retains text and **Retry floor image**; failedrelease refresh hides stale results untilretry.

In a new **disposable** cloned draft, mark the lift unavailable and explicitly review/publish: the standard cross-floor route uses stairs; step-free has no eligible connector. Set connector distance/status to unknown and leave baseline/wait blank consistently in both directions. A metric route excludes it; explicit directions-only can return eligible traversals with **Distance unknown**, a labelled known subtotal and **ETA unavailable**. A floor with unknown scale must be explicitly directions-only and independently permitted; it makes no metric claim. Fastest excludes unavailable connectors and unknown required times, and optimizes supported seconds. Publication still requires capability evidence. Explicit rollback switches public floors, routes and search coherently while retaining historical permitted PNG/artifact URLs. Developer releases need not change for these tests.


## Reproducible checks

Linux/cloud checkout, disposable test DBs only:

```bash
make generate-api check build test-unit validate-dataset
make test-integration test-migrations
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e
python scripts/cloud-build.py  # cloud proxy/CA helper; local: docker compose build api frontend
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-container-publication
```

Source/built browser runners share5174 and runsequentially. Integration guards `*_test`; migration/browser runner reset only their explicit `*_migration_test`/`*_e2e_test`; built smoke owns uniquely named containers/network/database. Developer volumes/uploads are never deleted. See [verification](../testing/verification.md) for actual results and limitations. These Bash test commands are not claimed as Windows shell commands; on Windows use Docker Desktop/WSL2 for the source check workflow.
