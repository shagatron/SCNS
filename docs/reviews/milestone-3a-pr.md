# Milestone 3A: private floorplans, draft floors and evidence-bound calibration

Base: `feat/milestone-2-publication` · Head: `feat/milestone-3a-floorplans`

Campus administrators can now manage draft floors, upload private PDF/PNG/JPEG plans, inspect sanitized pages/masks, explicitly apply or replace a selected page, and establish independently reviewed uniform scale. Public outdoor navigation continues to read its immutable release; uploads/apply never publish. Retained unselected plan history stays private and no longer blocks review/publication of the currently selected approved plan. Indoor tracing/connectors/routing remain 3B/3C.

## Delivered

- Additive `0012_floorplans`: stable revision/building-scoped floors with basement/ground ordering, unknown optional elevation/visibility, exact current-layer integrity, draft/review/frozen guards and non-cascading retained private batch history.
- Private originals/SHA-256/rights/provenance and durable jobs with 10MiB actual-content/signature/decode limits; unencrypted PDF ≤30 pages, 150DPI reference, ≤10kpx/side/32MP, bounded pixel-only PNG ≤2048px/side. Explicit page selection and reference-resolution masks before resampling.
- Linux decoder child with minimal environment, non-root drop when needed, fail-closed seccomp file/network/spawn restrictions and memory/CPU/wall/output limits. Existing image worker performs bounded processing outside DB locks, committed leases/three-attempt recovery, cancellation/late-result discard, campus quotas and exact retry keys.
- Campus permissions/live sessions/Origin/CSRF, whole-draft CAS, transactional writes/audits. Explicit replacement clears calibration; graph dependencies block replacement/recalibration/deletion; exact listed layer deletion retains historical job originals/releases.
- Responsive local Leaflet preview/pan/zoom/fit, reference-pixel y inversion, numeric/pointer control points and known line + nonparallel independent check. Dated substantive evidence/uncertainty/quality and campus-day validation; inconsistent/degenerate/distorted/future inputs reject. Independent calibration and sanitized derivative approval, including grant revocation at publication.
- Whole-draft checksums/review locks, only current permitted independently approved public PNG projection, no original/mask/private evidence/uploader metadata, immutable campus/release/layer/hash assets retained after rollback. Uncalibrated display publication requires acknowledged warning; all floors enforce display-only/no metric indoor routing even when calibrated.
- Errors/conflicts retain input with explicit reconciliation; same-tab two-hour metadata recovery/logout clearing and file reselection. Synthetic 600×400 PNG/JPEG/two-page PDF fixtures, executable schemas/examples, coordinate/data contracts, operations and data-retaining Windows update instructions.

## Validation

- Ruff lint/format, TypeScript/ESLint, Vite/Python build passed.
- **69 Python unit + 24 frontend tests, 118 PostGIS integrations**, no skips.
- Fresh/M1 downgrade/re-upgrade through 0012, alias/frozen guard/active pointer preservation, CLI bootstrap/model alignment passed on isolated DBs.
- **44 source desktop/mobile browser journeys**: four expanded floorplan plus all 40 public/admin/import/graph/review regressions.
- **16 built nginx/API/image-worker desktop/mobile journeys**: actual PDF and >6MiB valid image processing, explicit page replacement, retained unselected history approval, reload recovery, permissions/privacy, review/publish/rollback/immutable assets and outdoor navigation. No source worker used in built smoke.
- Both container images built; eight generated contracts reproduced byte-for-byte; three JSON examples validate; original synthetic dataset valid.
- Local built update preserved original developer counters/pointer/release hashes/.env/private-import volumes; new floor tables empty. Main Gate→Library remains 256.88m/three stored edges on the original release. No developer reset/reseed/bootstrap/publish/rollback; tests own/remove only disposable resources.

Exact evidence and limits: `docs/testing/verification.md`. Update/run/workflow: `docs/operations/floorplans.md`. Coordinate/storage/release contract: `docs/data/floorplans.md`.

## Limits and later work

Actual Windows execution, owner/physical-device/non-Chromium/human AT, Linux ARM execution, real institutional plans/rights/surveys/font coverage, production scanning/security/load/process-kill chaos/backup restoration and remote Actions remain unverified. Uniform rectified plans only, no affine/perspective fitting. Original plan bytes require consistent DB backups; existing text-import originals retain their private volume. Public floor picker, room/corridor/door tracing, entrances/cross-floor connectors and indoor routing are later 3B/3C, not delivered. QR/geolocation/live closures/PWA/ML/redesign/deployment are excluded. No public deployment, cloud-environment publication or merge.
