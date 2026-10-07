# Project progress

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
