## Problem and result

Campus editors previously had to create draft records individually. This adds private staged CSV, versioned JSON and GeoJSON imports with mapping, validation, before/after previews and explicit transactional application to a campus draft. Public search, maps and stored-graph Dijkstra routes continue reading the existing frozen release; importing never publishes.

## Implementation

- Private generated-name upload storage, UTF-8/format/byte/row/storage bounds, source rights/provenance/checksums and campus-scoped permissions/history. Metadata is outside access-log URLs. Formula-safe downloadable row diagnostics identify exact source records.
- Deterministic campus/entity external IDs and draft-scoped bindings; explicit legacy-record adoption and create-only/upsert policy. Duplicate codes never silently choose an update target. Submission keys bind exact content/options/target; repeated application cannot duplicate writes or audits.
- Savepoint dry-run validation of related catalog/outdoor frames/nodes/full directed polylines/references and existing graph dependents. Locked jobs plus whole-draft optimistic versions prevent stale overwrite; application, stable bindings, version, status and per-record/batch audits are one transaction.
- Durable DB worker with bounded child processing, stale-lease recovery, three attempts, cancellation and safe original/orphan retention. API/worker share a private Compose volume and API image; host development starts/stops all three services.
- Responsive complete admin upload/mapping/preview/diagnostics/validate/apply/history workflow, confirmation and stale-preview refresh. Successful imports invalidate affected catalog/dashboard caches. Synthetic templates/branding and setup/operations/checklist/progress/verification documentation are included.

Supported now: outdoor frames, buildings, places, nodes, edges, departments/place links, aliases and anchors. The JSON bundle provides atomic related-record application; dependent CSV/GeoJSON references must exist in the draft or the same supported bundle. Indoor images/PDFs/floors/connectors, graph editor 2B2, review/publication and deployment remain out of scope.

## Verification

- `make check build test-unit test-integration test-migrations validate-dataset`: lint/type/build, **35 Python unit, 50 PostGIS integration and 14 frontend tests**, migrations/schema alignment and original dataset validation passed. The final integration run includes real concurrent apply/replay and committed worker-lease/retention tests.
- `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e`: **28 desktop/mobile journeys passed**, including six import journeys and all ten public-navigation regressions. Admin traces/screenshots/video are disabled; accounts/storage are ephemeral and isolated.
- Contract/schema regeneration reproduces byte-for-byte. Both container images built; built readiness/worker/private-path/anonymous-login/public-route smoke and host three-service startup/shutdown passed. Main Gate → Library remains 256.88m over three stored edges on the original development release.

Full authenticated browser journeys ran on isolated source API/Vite/worker; built nginx received smoke checks. Official campus/field evidence, owner manual testing, non-Chromium/physical-device/assistive-tech verification, process-kill chaos/large-campus load, production security/backup recovery and remote Actions were not verified. No developer administrator/password was provisioned. No public deployment, merge or 2B2 work is included.

See `docs/operations/imports.md` for exact startup/templates/upsert/retention commands and `docs/testing/verification.md` for evidence and limitations. Base: `feat/milestone-2-admin` at `9f0e489`; checkpoints: `790bc4a`, explicitly unfinished `6e54e5f`.
