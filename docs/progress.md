## M2C unfinished implementation checkpoint — 7 October 2026

Backend lifecycle/migration, private source/derivative registration/approval, whole-draft validation and expected-route evidence, exact-content independent review, immutable checksummed artifacts, guarded transactional publish/rollback with retry keys and audited history are implemented. Review submissions lock entity writes at API and database level; withdrawal/rejection returns to a fresh draft version. Responsive source/review/history screens and release-pinned public refresh are present but browser verification is unfinished.

Focused result: 15 new backend unit/PostGIS tests passed (9 integration and 6 contract cases), plus 23 affected graph integration regressions passed. Type check and frontend lint passed with one Fast Refresh warning; helper extraction removes that warning and requires rerun. Full core suites and committed-transaction race tests are running; results are not yet claimed. New browser journeys, full migration rehearsal, built workflow smoke, Windows operations instructions and final evidence remain next. No developer release/draft was published or rolled back. This is explicitly unfinished.

## M2C unfinished scope checkpoint — 7 October 2026

Authorized by the owner’s pasted request; existing checkout clean at verified `21c65fb`. Branch `feat/milestone-2-publication` starts there; no worktree/reset/discard. Prior 2B2 implementation and verification retained.

Acceptance: authoritative whole-draft validation (catalog/import/geometry/graph/anchors/accessibility), blocking errors versus individually acknowledged warnings, computed standard/step-free expected-route evidence; explicit submit/reject/return/approve states bound to exact version/content; independent campus reviewer; source rights/provenance and reviewed outdoor public derivatives with private originals; reproducible immutable public artifacts; atomic publish and guarded rollback/history; stale-client recovery; transactional CAS/idempotency/audit. Preserve all existing workflows. Floorplan image/PDF processing is M3; live closures/QR/PWA/deployment remain excluded.

Implementation slices: backend lifecycle/migration/permission/transaction tests; responsive review/source/asset/history screens plus public recovery; full regression, migrations and container smoke against disposable databases only. No developer draft/release/account will be published/rolled back for testing. Windows Docker Desktop update instructions will retain volumes and .env.

Unfinished: application implementation and all new verification. Existing 2B2 results remain historical evidence, not 2C verification. Next: implement review records, exact-content validation/projection, lifecycle and transaction guards; then UI and isolated browser journeys; run all checks, document actual results, push and attempt PR targeting `feat/milestone-2-graph-editor` without merging.

## M2B2 delivery receipt and PR blocker — 7 October 2026

Completion commit **`93b525708f8cc59e537af0d402e54b7b611cd9e4`** is pushed to **`feat/milestone-2-graph-editor`**, which starts at completed imports `4444c68`. Working tree was clean after delivery; no user changes/secrets/dependencies/databases/uploads/build artifacts were included. Source startup and shutdown were verified and the built local Compose stack restored; API, DB, frontend and import worker are running locally. No public deployment/environment publication or merge occurred.

The actual `gh pr create` command targeting `feat/milestone-2-imports` exited 1: `Post "https://api.github.com/graphql": Forbidden`, with no PR URL returned. Git HTTPS pushes work. Complete prepared description: **`docs/reviews/milestone-2b2-pr.md`**. [Compare/open the PR](https://github.com/shagatron/SCNS/compare/feat%2Fmilestone-2-imports...feat%2Fmilestone-2-graph-editor?expand=1). This is a GitHub API access blocker, not a test failure. No credential or permission request is needed to preserve the completed work; owner can open the PR through that browser link.

Remaining next steps: owner manual testing when convenient, open the prepared PR and review without merging as part of this task. Milestone 2C review/publication/rollback, indoor navigation, live closures and deployment require a separate authorized task. Actual automated checks/limits and exact update/start commands remain in `docs/testing/verification.md` and `docs/operations/graph-editor.md`.

## Milestone 2B2 implementation and verification complete — 7 October 2026

Delivered the visual outdoor draft graph editor from clean verified `4444c68` on `feat/milestone-2-graph-editor`. Existing files/architecture/admin/import documentation were read; no worktree/reset or discarded changes. Unfinished checkpoints `2fa6e93`, `5cd3c62`, `a8062f1` were pushed.

Works: protected stored graph/map selection; node CRUD/movement with incident endpoint/cost updates; paired/one-way edge CRUD, vertex drawing/editing, split/snap and explicit shared-node intersections; entrance anchors; unknown nullable accessibility measurements, source notes and dated renewed verification; deletion dependency preview; actionable quality/standard/step-free connectivity diagnostics; stored Dijkstra draft tests; responsive controls, local undo/redo, per-account/tab input recovery and explicit stale-edit reconciliation. Atomic revision-CAS batches and persisted before/after audit reuse existing campus/CSRF/session boundaries. Public release remains `4eb587e6-5607-48ed-a8ca-f5c0d8f1c505`; Main Gate → Library remains 256.88m over three stored edges. Imports/catalog/session behavior remains covered by regression tests.

Final executed checks passed: lint/type/build, **35 Python unit / 19 frontend / 74 PostGIS integration / 38 desktop-mobile browser tests**, fresh/M1-down-and-up migrations through `0008_outdoor_accessibility` with schema alignment, synthetic validation, reproducible contracts/schemas, both image builds, healthy Compose app/worker, built private/protected/public endpoints, anonymous Chromium login, authenticated isolated built API graph/CSRF/concurrency/validation/Dijkstra/public-isolation/logout smoke, source/image hash comparison, idempotent host migration/seed and documented host startup/shutdown (Compose restored). See `docs/testing/verification.md` for failures fixed, isolation details and actual limits. No skipped/failed check is claimed passing.

Operations: `docs/operations/graph-editor.md` contains exact update/start commands and recovery/validation limits. Existing `.env`, DB/private-upload volumes preserved. No developer admin/password was provisioned. Official maps/rights/surveys, owner manual/physical-phone/non-Chromium/human AT, load/chaos/production security/backup and remote Actions remain unverified. Full authenticated browser journeys ran on isolated source services; built nginx received smoke checks. Review/publication/rollback, indoor navigation, live closures and deployment remain unfinished future milestones, not started here.

Exact next steps: commit/push this completion and check clean status; attempt `gh pr create --repo shagatron/SCNS --base feat/milestone-2-imports --head feat/milestone-2-graph-editor --title "Milestone 2B2: visual outdoor draft graph editor" --body-file docs/reviews/milestone-2b2-pr.md`; record outcome without merging. If GitHub API is forbidden, preserve the prepared body and provide the imports→graph-editor compare link. Owner can perform manual testing later; start 2C only upon new authorization. Local update: `git switch feat/milestone-2-graph-editor`, `git pull --ff-only`, `make setup`, `make db migrate seed-demo`, stop Compose app services, `make dev`; existing assigned credentials or trusted one-time bootstrap instructions apply.

## M2B2 unfinished visual-workflow checkpoint — 7 October 2026

The responsive visual editor, node/paired-edge/anchor controls, stored polyline editing, pointer drawing/movement, explicit split/intersection connection, deletion preview, local undo/redo, per-account/tab recovery and revision conflict comparison are implemented. Recovery preserves unapplied text and selected draft; failed saves retain input. Dated verification evidence is required for renewed step-free claims. Diagnostics cover weak components, directed standard/step-free destination reachability, crossings/near duplicates and stale source notes. Exact database endpoints are used when writing lines to avoid rounded-GeoJSON precision failures; audit includes persisted length/geometry. Public-pointer writes remain absent.

Executed earlier full checks: lint/type/build, **35 Python units, 19 frontend tests, 67 PostGIS integrations**, fresh/M1-down-and-up migration alignment, synthetic dataset validation passed. Subsequently added precision/anchor/near-duplicate coverage and changed exact-endpoint writes: focused **18 graph integrations passed**. Latest focused browser run: **9/10 passed**; mobile pointer-save failure is still under diagnosis. No failed/unrun check is counted complete.

Next: finish pointer-save diagnosis; run stable-source full desktop/mobile graph/admin/import/public suite; rerun affected final core checks; build/migrate/start containers and smoke private/graph/public endpoints and stored route; finalize operations/checklist/evidence; commit/push completion and attempt PR to imports. This checkpoint is explicitly unfinished. All current frontend/test changes are preserved; no source implementation restart.

## M2B2 unfinished backend checkpoint — 7 October 2026

Atomic campus-authorized outdoor graph batches, coherent reads, draft revision CAS, ordered explicit deletions, node movement with incident geometry/length updates, per-feature audit, graph quality diagnostics and stored-graph Dijkstra draft route tests are implemented. Migration `0007_graph_node_evidence` adds optional provenance notes without changing active releases. Graph attributes reuse import/catalog contracts; unverified moves reset affected paths to unknown accessibility/estimated distance.

Executed: **15 new real PostGIS graph tests passed**, Ruff lint/format passed (49 files), contracts generated. The first test attempt found the database stopped; restarting the existing container fixed setup. Two initial rollback assertions mutated their own nested expected fixtures; deep-copying the fixtures fixed them. No application integrity assertion was relaxed.

Unfinished: visual UI, undo/redo/split/snap/recovery/reconciliation and browser journeys; broader regressions, migration rehearsal and built-container smoke; final operational/evidence/checklist documentation and PR. Frontend graph-state helper is work in progress. No publication, indoor or closure work.

## M2B2 unfinished starting checkpoint — 7 October 2026

Verified clean checkout at completed/pushed M2B1 `4444c68b533b6fa510b931c436f11fcdb461af58`; created `feat/milestone-2-graph-editor` directly from that commit without a worktree or reset. Read the master editor/integrity/quality requirements and existing implementation/documentation. No application changes or new checks yet.

Authorized scope: outdoor draft graph viewing and selection, node/edge/anchor CRUD, stored polylines and paired directions, explicit intersection connection/split/snap, undo/redo, unsaved recovery and conflict reconciliation, source/accessibility disclosure, server validation and audit. Public immutable releases, imports and existing permissions remain intact. Review/publication, indoor tools and live closures remain later milestones.

Next steps: implement atomic revision-CAS graph commands and diagnostics with PostGIS tests; build responsive visual controls and private per-tab recovery; run desktop/mobile graph plus all existing regressions, lint/type/build/schema and container smoke; update operations/checklist/evidence; push completion and attempt PR against `feat/milestone-2-imports`. This checkpoint is explicitly unfinished. Preserve existing `.env`, database volumes and private uploads.

# Project progress

## Milestone 2B1 complete — 7 October 2026 (Asia/Kolkata)

Completed **staged campus-data imports only** on `feat/milestone-2-imports`, from verified `9f0e489`. Backend checkpoint `790bc4a` and the explicitly unfinished UI/verification checkpoint `6e54e5f` are pushed. Resumed from those existing changes without recreating implementation; the import UI and cache-refresh fix were preserved. No 2B2 graph editor, review/publication, merge, paid service or public deployment occurred.

Completed: private bounded CSV/import-v1 JSON/GeoJSON uploads and executable synthetic templates; campus-scoped job history, rights/provenance/checksums; field mapping and safe downloadable row diagnostics; before/after additions/updates/conflicts; stable external IDs and explicit adoption/create-only/upsert rules; submission and apply idempotency; savepoint previews; transactional draft application with whole-draft concurrency; uploader/applier and per-record audits; durable bounded worker leases/retries/cancellation/retention; responsive complete admin workflow. Applying refreshes the affected catalog/dashboard cache. Upload rights/provenance are carried in a private metadata header rather than access-log URLs. Public APIs remain on the existing frozen release.

Final evidence: **35 Python unit, 50 real PostGIS integration, 14 frontend and 28 desktop/mobile browser tests passed**, no skips or unresolved failures. The added committed-worker test passed both alone and in the final 50-test suite. Existing valid build/unit/browser/migration evidence was reused when unaffected; latest Ruff/format/type/ESLint and complete integration suite were rerun. Fresh/downgrade/re-upgrade migrations, model alignment, dataset validation, SHA-256 contract/schema regeneration and both image builds passed. Built nginx/API/worker readiness, queue access, private-path/anonymous-access smoke and clean anonymous login passed. Host `make dev` readiness/routing/worker startup and supervisor cleanup were exercised; all API/web/worker processes stopped and ports closed. Compose was restored afterward. See `docs/testing/verification.md`.

The development route remains Main Gate → Library, **256.88m over three stored edges**, on release `4eb587e6-5607-48ed-a8ca-f5c0d8f1c505`. No developer administrator/password was provisioned. Isolated tests use temporary accounts/storage, never developer data. Secrets, raw sources, database/dependency/build/browser outputs are ignored. Only code, migrations, executable templates/contracts, tests and documentation are committed.

Operations: `make setup demo dev` starts source API/frontend/worker; stop Compose `api frontend import-worker` first when switching. Built startup: `python scripts/cloud-build.py` in this cloud workspace, explicit migration/seed, then `docker compose up -d --wait api frontend import-worker`. API and worker share the same database and private storage. Admin bootstrap, formats, policy, concurrency and retention commands are documented in `docs/operations/admin.md` and `docs/operations/imports.md`. The cloud `start_skill` draft was updated for the worker; installation/network/credentials/repository settings were preserved. This saves instructions only, with no environment publication or deployment; activating a future snapshot requires owner review/save in environment settings and environment publication.

Delivery confirmed: completion commit `485f3758a33d5ac316a5febe6dc4eaa4e1083925` is pushed to `origin/feat/milestone-2-imports`, following pushed checkpoints `790bc4a` and `6e54e5f`. This documentation receipt records the outcome and will also be pushed. Application implementation and automated verification are complete.

**PR creation blocked:** the actual `gh pr create --repo shagatron/SCNS --base feat/milestone-2-admin --head feat/milestone-2-imports --title "Milestone 2B1: staged campus-data imports" --body-file docs/reviews/milestone-2b1-pr.md` returned `Post "https://api.github.com/graphql": Forbidden` (exit 1). No PR URL was returned and no merge occurred. HTTPS Git pushes are confirmed. Ready description: `docs/reviews/milestone-2b1-pr.md`; [compare/open the PR](https://github.com/shagatron/SCNS/compare/feat%2Fmilestone-2-admin...feat%2Fmilestone-2-imports?expand=1). When API access is available, rerun that exact command, or use the compare page to create the PR with the prepared title/body. PR base remains `feat/milestone-2-admin` at `9f0e489`.

Next steps: owner review/manual testing; open the unmerged PR through the compare link or restored API; keep 2B2 and subsequent implementation pending separate authorization. Owner manual testing, official maps/rights/surveys, physical phones/human assistive technology, non-Chromium browsers, production security/load/recovery and remote Actions are not verified. Future milestones require separate authorization.

## Milestone 2B1 unfinished UI/verification checkpoint — 7 October 2026 (Asia/Kolkata)

Resumed in the existing `feat/milestone-2-imports` checkout. Confirmed `790bc4acc0b7ea67a01ec25b69a9f5a4e1651cc9` is both local HEAD and the pushed remote checkpoint. Preserved and checkpointed all remaining local work, including the responsive import UI, raw upload transport, catalog/dashboard cache refresh after apply, isolated browser journeys, metadata-header privacy hardening and shared API/worker image configuration. This checkpoint is **explicitly unfinished**, not milestone completion.

Valid verification already executed on this implementation: Ruff/format, TypeScript/ESLint, Vite/Python build, **35 Python unit, 49 PostGIS integration, 14 frontend and 28 desktop/mobile browser tests**, fresh/downgrade/re-upgrade migrations and schema alignment, synthetic dataset validation. All passed without skips. The 28 browser tests include six import journeys, twelve admin/session journeys and all ten public-navigation regressions. Both container images built; local API/frontend/worker started, worker `once` and empty retention cleanup succeeded. Built nginx/API preserved the original 256.88m three-edge route/release; private paths remained 404, protected imports/session returned 401, and a fresh built admin visit showed normal sign-in with one session check and no alert. API image/source import-service hashes matched.

Not yet verified: newly added `test_import_worker.py`, which exercises committed stale-lease recovery, exhausted retries, cancellation and orphan cleanup. No application code changed after the valid full regression/browser/container checks; this additional test still needs to run. Active setup documentation still needs its old two-process/no-worker wording updated; final verification/checklist/progress and PR description remain unfinished. GitHub PR creation has not been retried for 2B1.

Exact next steps: push this unfinished checkpoint; run the new worker test and affected checks; finish active setup/worker documentation and reusable startup instructions; confirm generated contracts reproduce; record final evidence and remaining limitations; commit/push milestone completion; attempt `gh pr create --base feat/milestone-2-admin --head feat/milestone-2-imports` without merging, saving the PR body/compare link if API access remains blocked. Do not begin 2B2 or deploy.

## Milestone 2B1 backend checkpoint — 7 October 2026 (Asia/Kolkata)

Verified baseline `9f0e489f0fff83d46b67ce3d8a9f95684c15b74c` in a clean checkout and created `feat/milestone-2-imports` from it. Read master-spec sections 8/17, prior progress/checklist and existing admin/session/catalog code before changes. Only staged imports are authorized; no graph editor, review/publication or deployment is included.

Implemented private bounded CSV/import-v1 JSON/GeoJSON uploads, DB jobs/history, external-ID bindings, mapping/reprocessing, savepoint previews with row diagnostics/conflicts, explicit create-only/upsert policy, validation, whole-draft optimistic application, idempotent submission/apply, cancellation/retries and batch/record audits. Added a bounded child worker and private shared Compose volume; draft applications never touch public releases. Added executable synthetic templates and exact setup/worker/retention commands.

Checkpoint evidence: **43 PostGIS integration tests initially**, 21 existing Python unit tests and 14 frontend tests passed; fresh and downgrade/re-upgrade migrations/schema alignment passed; lint/type/build passed before the subsequent concurrency/boundary hardening. **45 integration tests and 35 Python unit tests now pass**, including real concurrent distinct-job application and same-job replay; 14 frontend tests also pass. Browser admin/public baseline journeys pass so far; initial new import journeys failed on select-field test locators. Corrected locators yielded four passing import journeys; the other two caught stale catalog caching after apply, now fixed by invalidating the affected draft/dashboard. Final browser rerun remains pending. Do not treat the new UI/browser workflow or current final build as verified yet.

Unfinished: finish isolated browser journeys and remaining concurrency/recovery/security tests; run final documented checks and built-stack smoke; update checklist/verification/PR description; commit/push remaining UI and evidence. Frontend work is preserved in this checkout. Backend checkpoint will be pushed, then work continues. PR target is `feat/milestone-2-admin`; GitHub API access was previously Forbidden, so test it after completion and save a compare-link fallback if still blocked.

## M2A session inspection fix — 7 October 2026 (Asia/Kolkata)

Completed the follow-up on `feat/milestone-2-admin` from `bdbc2c4`. The screenshot branch `docs/app-preview-screenshots` and its historical PNGs are preserved separately. No Milestone 2B work was started.

The fresh-visit loop came from treating the initial session-check 401 as an expired session and clearing the observed query. The session controller now settles that response as normal anonymous state, keeps the session query intact, and limits focus/reconnect checks to established sessions. Only a previously established session rejected by the server triggers the end notice and private admin-data cleanup. Login and intentional logout reset the notice. Cancelled older checks cannot overwrite a new login, and public cache data is retained. Backend authorization, cookie/session expiry/revocation and CSRF controls are unchanged.

Regression evidence: the fresh-visit test failed against the original UI/API implementation and passes with the fix. Final checks passed: Ruff/format, TypeScript, ESLint, Vite/Python build, **21 Python unit, 28 PostGIS integration, 14 frontend and 22 desktop/mobile browser tests**. The browser suite includes actual server revocation/re-login/quiet logout and all ten public-navigation regressions. Images rebuilt and the running local nginx app reached network idle with a normal login, no alert, exactly one initial session check and no extra focus check. See `docs/testing/verification.md` for commands and test limitations.

Delivery target: commit/push this verified fix on `feat/milestone-2-admin`; branch history records the resulting commit. Only frontend lifecycle logic, regression tests and associated documentation are part of the follow-up. No schema change, credential provisioning, paid service or public deployment occurred.

Next steps: review the fix; manually test the existing app when ready; begin M2B only after separate authorization. Earlier PR creation remains blocked by GitHub API `Forbidden`, while Git push is available. No new PR attempt is required for this follow-up.

## Milestone 2A completion — 7 October 2026 (Asia/Kolkata)

Scope: **Milestone 2A only**, from baseline `86e1591` on `feat/milestone-2-admin`. Milestones 0/1 are preserved. No staged import, graph editor, review/publish/rollback workflow, live closures, paid service or public deployment was implemented.

### Completed work

- Confirmed backend checkpoint `59413e85129de49e6708dbc041eb5343e8e3c490` was already pushed to GitHub. Preserved and completed the unfinished frontend files; did not restart or recreate the branch/implementation.
- Secure local admin login/logout: Argon2id, random opaque server sessions stored as hashes, expiry/revocation/rotation, durable account/IP throttles, Origin/CSRF enforcement, no-store responses and one-time trusted-host bootstrap without a default password.
- Campus-scoped editor, reviewer/publisher, operations and system-administrator grants; dashboard, user provisioning/role changes and last-admin protection. Server authorization and revision/campus isolation remain authoritative.
- Responsive admin interface for buildings, places, departments/place links, aliases and anchors. Read-only node selection, meaningful anchor labels and required evidence notes for affirmative step-free anchor edits.
- Draft cloning without public pointer changes, revision-wide optimistic edits, conflict input preservation/comparison/reconciliation, transactional audits and append-only administrative records. Public search, map and stored-graph Dijkstra routes remain on the published release.
- Isolated browser and migration databases, random ephemeral browser credentials and disabled admin traces. Added real concurrent-transaction, permission, evidence and CLI bootstrap tests. Updated setup/configuration, architecture, data dictionary and checklist.

### Verified results

Ruff/format, TypeScript, ESLint, Vite/Python builds passed. **21 Python unit + 28 PostGIS integration + 7 Vitest + 18 desktop/mobile browser tests passed**, including the original 10 public-navigation browser regressions. No final suite failures or skips. Fresh/downgrade/re-upgrade migrations through `0005_anchor_evidence`, frozen alias backfill/protection, public release preservation, schema alignment and actual one-time CLI replay passed. Contracts reproduce byte-for-byte; dataset validation passed.

Both images rebuilt successfully. The local Compose stack was migrated/restarted and passed readiness, admin bundle/protected endpoint and private-file smoke checks. Public Main Gate → Library remains 256.88m over three stored edges on the original development release. No administrator was bootstrapped in the developer database: the owner supplies that account/password when ready. See `docs/testing/verification.md` for exact commands, test coverage, warnings and limits.

### Delivery and unfinished work

The backend checkpoint and completion commit `8c0ac7fbc8b66c8727cb1e5e37b690cb44f11aa6` are pushed to `origin/feat/milestone-2-admin`; `git ls-remote` confirmed the completion commit. This final documentation receipt records that verified push. Secrets, dependencies, database files and generated build/browser artifacts are excluded; lockfiles and generated API contracts are retained.

**PR creation blocked:** both read-only REST/GraphQL probes and the actual `gh pr create` attempt returned `Forbidden` from `api.github.com`. No PR URL was returned, no merge occurred, and no alternative GitHub connector is available. Git HTTPS push remains supported. The ready description is `docs/reviews/milestone-2a-pr.md`. The PR should target `feat/milestones-0-1`, because GitHub `main` still points at the original initial commit and does not yet contain `86e1591`.

Owner manual app testing is deferred as requested. Physical-phone/assistive-tech verification, official maps/surveys, production security/load/recovery and remote GitHub Actions inspection remain unverified. M2B/2C remain explicitly unimplemented.

### Exact next steps

1. Review the completed/pushed `feat/milestone-2-admin` branch. No source implementation or automated check remains unfinished for 2A.
2. When GitHub API access is restored, open the unmerged PR:

   ```bash
   gh pr create --repo shagatron/SCNS --base feat/milestones-0-1 \
     --head feat/milestone-2-admin \
     --title "Milestone 2A: scoped admin sessions and private draft catalog" \
     --body-file docs/reviews/milestone-2a-pr.md
   ```

3. For later manual testing, use the rebuilt local Compose stack, or stop Compose `api`/`frontend` and run `make setup demo dev`. Follow `docs/operations/admin.md` to bootstrap a chosen admin password and visit `/admin`. No account/default password was silently provisioned.
4. Reproduce checks with `make check build test-unit test-integration test-migrations` and `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e`. Browser and migration databases are disposable; developer data is preserved.
5. Begin M2B only after separate authorization. Prepare official maps, licensing and survey evidence independently using the existing templates.

## Milestones 0/1 history

Checkpoint: 6 October 2026 (Asia/Kolkata). Authorized scope: **Milestones 0 and 1** of `docs/product/master-spec.md`. Later milestones are not part of this delivery.

## Completed work

- Inspected the original repository/history: only README existed. No C prototype was supplied; `legacy/c-prototype/` records this and preserves the intended location.
- Built React/TypeScript/Vite/Tailwind/Leaflet frontend, FastAPI/Pydantic/SQLAlchemy backend, and Alembic/PostgreSQL/PostGIS persistence.
- Added synthetic data: 3 buildings, 10 public destinations plus 1 restricted place, 13 nodes, 27 directed edges and 11 anchors. No official campus geometry was invented.
- Implemented search/directory, details/filters/pagination, manual starts/destinations/swap, map polylines, text directions, mobile layout, error/no-route handling and baseline ETA.
- Implemented multi-source heap Dijkstra over stored graph edges. PostGIS measures complete directed polylines. Changed imported data changes actual routes; closed/restricted/stairs/unknown accessibility constraints are enforced.
- Added revision-scoped relationships, immutable releases, atomic active pointers, coordinate/calibration foundations, private upload spaces and data templates.
- Added dependency locks, generated API/schema contracts, Make commands, local Compose images, CI definition and setup/data/architecture/security documentation.

## Checks completed before this checkpoint

| Check | Observed result |
|---|---|
| Python unit tests | 21 passed |
| Real PostGIS/API integration tests | 13 passed |
| Frontend Vitest tests | 7 passed |
| Desktop + 360px mobile Chromium journeys | 10 passed, including keyboard and axe checks |
| Ruff, TypeScript, ESLint, Vite build, Python compilation | Passed |
| Fresh migrations and isolated test-database downgrade/reapply | Passed |
| Dataset validation and repeated seed | Passed |
| API/frontend container builds | Both built through the configured cloud proxy with verification enabled |

Since the full suite, a nullable indoor-frame dimension constraint/test, map resize refit, development-process cleanup and documentation were added. A subsequent container rebuild completed. Relevant checks for these changes remain next; earlier passes are not represented as a new final run.

## Work that remained at checkpoint

1. Checkpoint source/tests/docs on a working branch and push through existing GitHub access if supported. Exclude secrets, installed dependencies, database files, private input, build outputs and browser artifacts. Retain lockfiles and generated API contracts for reproducibility.
2. Validate the built Compose stack: run migrations, repeated synthetic seed, readiness and a functional route through nginx. Host servers were stopped to free ports 8000/5173; PostGIS remains running.
3. Rerun affected lint/build/unit/integration/browser checks, validate `make setup` and development startup/shutdown, and record final counts in `docs/testing/verification.md`.
4. Finish the requirements checklist and progress report, save reusable cloud startup instructions, and report any remaining limitations. No public deployment/publication is authorized.

From `/workspace/SCNS`:

```bash
docker compose run --rm --no-deps api alembic upgrade head
docker compose run --rm --no-deps api python -m app.cli.dataset seed-demo ../data/demo/campus.json
docker compose up -d --wait api frontend
make check build test-unit test-integration validate-dataset
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e
make generate-api
```

If images need rebuilding in this workspace, use `python scripts/cloud-build.py`. It forwards configured proxy variables by name and mounts existing CA trust as a BuildKit secret; it does not disable verification or write credentials into images. Standard Playwright download was blocked by network policy; installed Chromium ran all browser tests successfully.

## Subsequent milestones and external inputs

M2: scoped admin authentication, catalog editing, real staged CSV/JSON/GeoJSON imports, review/publication, concurrency and audit. M3: indoor floors/rooms/connectors. M4: QR, location, live closures, reports and PWA/saved routes. Official maps, source rights, surveys, owner/license decisions and field verification remain external inputs. They do not block the current synthetic outdoor slice. No paid services or public deployment have been used.

## Git checkpoint outcome

Checkpoint `007d87a` was created on working branch `feat/milestones-0-1` and successfully pushed to `origin/feat/milestones-0-1` on 6 October 2026. Secrets, installed dependencies, database files, raw uploads, caches, build output and browser artifacts were excluded. Lockfiles and generated API contracts were intentionally retained. The completion section below records validation performed after this checkpoint.

## Completion after checkpoint

Milestones **0 and 1 are implemented and verified**. The latest indoor-dimension constraint, map resize behavior and process cleanup were checked. Frozen dependency setup, lint/type/build, 21 Python unit tests, 13 real PostGIS integration tests, 7 frontend tests and 10 desktop/mobile browser tests passed. The browser suite also passed against the actual built nginx/Compose frontend/API stack. Fresh migration and downgrade/reapply through `0003_frame_dimensions` passed on the isolated test database.

Both images built with the cloud helper. The built server returned a real 3-edge route from Main Gate to Library (256.88m, 183.5s baseline ETA), returned 404 for private source paths, and preserved the release across repeated demo seeding. `make dev` startup/readiness and shutdown were exercised; both service process groups stopped and released their ports. The Compose app was restarted afterward and remains the running local stack.

Generated OpenAPI/TypeScript/schema artifacts reproduced without diff. Git ignore and credential-pattern checks confirmed that local `.env`, dependencies, caches, database files, raw uploads, traces and build output were excluded. The deprecated ESLint 9 version was updated to compatible ESLint 10. See `docs/testing/verification.md` for full evidence and unrun checks; all M0/M1 entries in the requirements checklist are accurate.

### Next steps

1. Run the current slice with `make setup demo dev` (stop the existing Compose `api`/`frontend` first if using host development). Or reuse the healthy local Compose services on port 5173.
2. Recheck with `make check build test-unit test-integration` and `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e` in this workspace.
3. Review the working branch. No merge, public deployment, paid service or environment publication was performed.
4. The **next implementation milestone is M2**: campus-scoped admin identity/roles, draft catalog/editor, staged real-data import preview and commit, validation/review/publication, audit and optimistic concurrency. Keep edits invisible to public APIs until review; use new real-campus IDs rather than renaming Demo Campus.
5. Owner can prepare authorized maps/rights/surveys using `data/README.md` and `data/templates/` while M2 is developed. These inputs do not block synthetic development. Indoor routes, QR, geolocation and offline saved routes remain M3/M4 work, as specified.

Reusable cloud configuration: `install_script` and `start_skill` were saved as an environment configuration draft. This saves instructions only; it does not publish the environment or deploy the app. To use a new reusable snapshot, review/save the draft in environment settings and publish the environment there. No runtime secret or network allowlist changes were added.
