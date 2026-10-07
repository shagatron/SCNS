# Indoor visual editor — local update and manual verification

Milestone 3B traces existing independently approved plans into canonical indoor destinations, same-floor paths and explicit door access. Public indoor navigation remains unavailable until 3C. Draft edits never publish automatically. Sources/dates/accessibility remain assertions requiring rights and field verification. Official institutional plans and surveyed topology remain external inputs.

## Data-preserving Windows PowerShell update

Run in the **existing SCNS repository folder** with Docker Desktop in Linux-container mode and Compose v2. Preserve/commit local changes before switching; do not reset/discard. Existing owner/reviewer accounts, unpublished ACA draft, .env, database/private-import volumes and plan history stay in place. Stop at any failing command, investigate and retain volumes; these commands do not create a fresh demo or publish anything.

```powershell
git status --short
git fetch origin
git switch feat/milestone-3b-indoor-editor
git pull --ff-only origin feat/milestone-3b-indoor-editor
docker compose build api frontend
docker compose stop api frontend import-worker
docker compose up -d --wait db
docker compose run --rm --no-deps api alembic upgrade head
docker compose up -d --wait --no-build api frontend import-worker
docker compose ps
Invoke-RestMethod http://localhost:5173/api/v1/health/ready
Start-Process http://localhost:5173/admin
```

Forward migration `0013_indoor` adds local tables, guards and nullable indoor canonical geography. It retains existing rows/accounts/releases and active pointers. Never run reset/reseed, bootstrap, database downgrade or `docker compose down -v` as an update. Downgrade with indoor canonical places refuses non-test databases rather than losing indoor data. The existing worker remains responsible for staged imports and PDF/image processing; 3B does not require another service. Private original/PNG BYTEA is part of database backups, and staged text originals retain their existing private volume. No production backup/restore certification or actual Windows execution is claimed. The owner's reported 3A Windows test is separate evidence; our cloud DB is separate.

Linux source development in the existing checkout (after preserving local changes/switching/updating and with dependencies already installed):

```bash
make db migrate
# Stop Compose application services before using host ports 8000/5173.
docker compose stop api frontend import-worker
make dev
# scripts/dev.sh starts API, frontend and import/floorplan worker; Ctrl+C stops them.
```

For dependency updates on an existing checkout use `make setup` (retains an existing .env), then the migration command. Use README demo/bootstrap instructions only for an explicitly new empty installation.

## Complete manual test walkthrough

Use clearly labelled synthetic Demo Campus and an editable private draft; keep it unpublished for the editing steps. Your existing Windows ACA Ground Floor plan at 0.05m/reference-pixel, independently approved derivative/calibration, can be used **if its reference dimensions are 600×400**. This prerequisite is owner-reported, not cloud verification. Open owner/editor in the normal browser and a different assigned reviewer in a separate browser profile/private window. Use your existing credentials; no password is supplied by this feature.

1. Sign in `/admin`, select assigned Demo Campus and your existing editable draft. Open **Indoor floor editor**, select ACA through **Indoor building**, then Ground Floor through **Indoor floor**. Confirm label, reference dimensions, synthetic warning, scale and absence of prerequisite errors. Pan, zoom and **Fit indoor plan**. Change **Plan opacity** to 0.4; labels/paths remain selectable. There is no public floor picker or indoor route/ETA.
2. If the selected plan/approval is missing, use **Floors and floorplans** (see the [3A workflow](floorplans.md)). In a new synthetic test draft, use `data/demo/floorplans/synthetic-ground.png`, floor G/Ground ordering 0, no guessed elevation, `rights=synthetic`, invented source/attribution, optional mask x480/y320/width100/height60. Apply the worker's ready page explicitly. Primary (100,100)→(300,100) =10m; nonparallel check (100,100)→(100,300) =10m; uncertainty0.05m, date2026-10-01, substantive **synthetic, not surveyed** notes; quality uniform. A different reviewer approves exact derivative and calibration. Return to owner. Do not alter already approved developer plans merely to run this walkthrough.
3. On an empty 600×400 demo floor use **Load tracing JSON into local preview** → repository `data/demo/indoor/synthetic-ground.json`. This proposes **22 records** (3 rooms,6 nodes,10 directed paths,3 access links). Review room101 at(180,170), west corridor(100,100), centre junction(300,100), door101(180,120). R1 and its door/path/access are purple/restricted. Public paths are green, nodes blue, room labels separate; dotted access links are not walkable centre connections. The first paired corridor's full length is10m. All survey/accessibility details are unknown; sentinel evidence is private. Click **Save indoor graph to draft**. No public search/map/route change occurs.
4. Select **101 · Synthetic study room · public** from rooms. Set Room name `Synthetic reviewed study room`. Add alias `Invented teaching space` with **Add room alias**. Optionally create a public department in Draft catalog, reconcile the global version, and select its checkbox. Fill valid private source/verification notes only if warranted; leave date unknown for unsurveyed demo. Room UUID equals canonical searchable place UUID, but room code is101, not its internal I-UUID. Save explicitly.
5. **Add indoor destination**: code103, name `Synthetic extra room`, kindroom, descriptioninvented. Default centre label is only display. **Add indoor node**: label `Extra synthetic door`, kinddoor, x520/y200, **Apply local coordinates**. **Link room to door**: choose103/Synthetic extra room and Extra synthetic door; priority1, accessunknown/open/public. **Add indoor path**: fromSynthetic centre/junction, toExtra synthetic door/door, kinddoor. Choose one-way or paired two-way consciously. Numeric polyline `[[300,100],[450,100],[520,200]]` meets these endpoints; **Apply indoor polyline**. Keep width/slope/steps/surface blank. Save; one-way door return warning is expected, not silently reversed.
6. Pointer tools: select **Add local node**, tap inside the reference plan, inspect x/y, **Undo indoor action**, **Redo indoor action**. Select a node and **Move selected label/node**; moving it updates incident endpoints and clears affected survey assertions. Select a corridor and **Append interior path vertices**, tap a desired bend; choose an interior vertex index and **Move selected interior vertex**. Numeric fields/polyline JSON provide equivalent controls. Snap is2 reference pixels, not metres or connectivity. Room labels never connect through proximity.
7. Select corridorSynthetic west→Synthetic centre. Original zero-based vertex1 is(200,100). **Split indoor path deliberately** creates an unverified junction and converts its two directions into four, retaining shared physical pair consistency. Undo reduces pending changes; redo restores the split. For a crossing, insert a vertex at the intended junction, split the first path, then select that existing junction when splitting the other; no implicit crossing connection. Save and inspect stored geometry/unknown assertions.
8. Deletion: select a door/node/room/path and **Delete indoor feature and dependencies**, read/confirm the consequence. Local pending deletion explicitly includes both affected path directions/door links; room deletion also removes its canonical place on save. Undo/redo preview the changes. Save only intended changes. Backend rejects a direct deletion that omits needed references. In Floors and floorplans, selected-plan replacement/calibration/floor deletion are blocked while rooms/nodes depend on that frame; building deletion retains floor references. Do not delete your developer mapping to test the guard; a disposable synthetic draft suffices.
9. Failed input/reload: select room101, enter `unfinished-pixel-input` forReference x, then **Apply local coordinates**. Error must retain the text. Reload in the same tab; assigned campus/draft/floor/selection/raw text restore while still assigned. Use **Cancel unapplied indoor input** to discard deliberately. Recovery is limited to2MB/two hours/30 actions; a visible storage warning means keep the tab open. Logout/expired/revoked sessions clear recovery. Existing authentication/CSRF/session controls remain enforced.
10. Conflict: two editor tabs load the same saved room. A sets name `My retained local name`; B sets `Concurrent server room name` and saves. A save must refuse stale version and show **Indoor reconciliation**, retaining A's input. **Use reconciled indoor draft** stays disabled until every conflict has a mine/server decision. Choose mine for the room, reconcile, review merged state and save again. Other independent changes merge. A newer selected plan requires explicit comparison/retracing against its displayed latest image; never silently reuse old pixels. Frozen/submitted revisions and reviewers are read-only; operations has no indoor editor.
11. **Validate saved indoor graph** after saving. Bounds/reference/geometry/pairs/duplicate codes/false step-free assertions block writes/review. Unlinked destinations, weak components, unmapped crossings, stale/unknown evidence, one-way unreachable doors, unknown step-free and 3C unavailability are actionable warning diagnostics; select affected records usingInspect buttons. A successful synthetic topology check does not establish field accessibility. Indoor records augment existing exact-content validation, not replace required outdoor route acceptance.
12. Optional **explicit review test on a disposable draft only**: Review and releases → validate outdoor MainGate→Library/step-free acceptance; review every warning with reasons → submit exact current content; independent reviewer inspects and acknowledges → approve → confirm publish. Publication is a separate deliberate action, never import/editor automation. Public searchalias `Invented teaching space` shows room/floor metadata, `point=null`, catalog-only/no indoor routing; restricted R1/private sentinel/source/actors stay absent. Existing outdoor MainGate→Library remainscomputed256.88m/three stored edges. Approved artifacts retain the four permitted indoor dictionaries and all floor `metric_navigation=false`. Explicit rollback restores earlier public pointer while historical artifact/PNG URLs remain readable. Never publish/rollback the retained developer campus solely for test convenience.

## Verification commands and isolation

From the Linux checkout, after setup and disposable test DB provisioning:

```bash
make generate-api check build test-unit validate-dataset
make test-integration test-migrations
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e
python scripts/cloud-build.py  # cloud proxy/CA helper; locally docker compose build api frontend
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-container-publication
```

Integration uses guarded `*_test` sessions/owned committed fixtures; migration resets only `*_migration_test`; browser resets only `*_e2e_test` with ephemeral accounts/private storage. Built smoke owns a unique DB/network/container namespace and uses actual API/nginx/image worker. Never point these runners at developer/production DBs. Standard local Chromium installations may use Playwright's browser instead of the cloud executable override. Source and built smoke share port5174; run sequentially. See [actual verification evidence](../testing/verification.md), not the command list, for pass/fail counts and unverified areas.
