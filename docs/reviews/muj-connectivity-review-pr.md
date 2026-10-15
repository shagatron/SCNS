# Preserve MUJ source connectivity with a versioned draft correction

Base: `feat/muj-osm-import` at`1cd6533413e09069b0596b4c309458edccc49886`; head:`feat/muj-connectivity-review`. Open without merging.

V1 discarded entire highway ways when their final vertices left campus coverage, losing valid inside connections. Separately pinned v2 retains only fully covered original consecutive-node runs, without clipping, snapping, fabricated geometry or weaker access/grade rules. The guarded updater previews20additions(5nodes/14edges/1explicit entrance anchor) and2replaced-edge deletions, then applies one normal GraphPatch transaction. Original v1 files/IDs/receipts remain unchanged; do not upload full v2 bundles or replay the original setup helper.

Updater protections: affected baseline records/endpoints/catalog checks, unrelated owner edit preservation, exact preview/version/source/manifest binding, explicit APPLY, normal session/Origin/CSRF/campus permissions, draft-wide CAS/full validation/transaction/audits, explicit dependency-ordered edge replacement, collision/partial-state refusal and safe lost-response/retry reconciliation. Audit evidence carries v2 manifest marker and private receipts bind server request/requesting actor. Original helper refuses corrected history and rechecks before pending-batch applies; CAS handles the remaining concurrent-change window. No new API/schema, routing algorithm, publication or authorization semantics.

Result:51buildings/55places,295nodes/700directed edges/22anchors,29weak components/33unanchored. University Entrance→Mapped entrance10828149259 now computes513.0969783921546m/13edges (previously unanchored); five established cases unchanged;0errors/111warnings, no acknowledgements. The raw subway chain exists but private10778271605 plus grade/coverage policy still prevent an eligible cross-campus route. Central Library12585506492 has no mapped entrance. Corridors/multi-floor geometry require evidence. Complete exact-ID source investigation, component inventory and clearly labelled before/after diagnostic SVGs separate applied source corrections from unresolved proposals.

Draft route wording now uses a neutral unpublished/source/field-review notice plus synthetic supplement only for actual`campus.is_demo`. Public step-free wording follows metadata and QR empty state does not universally assume synthetic signs. Existing public redesign preserved.

Validation:

- Final lint/format/type/build and151Python units passed;61frontend units retained after final frontend change.
- Final53PostGIS tests passed: MUJ setup/import/update plus graph/import/concurrency/rollback/regression.
-28distinct source browser cases:26unaffected retained,2final updated MUJ desktop/mobile passed.86distinct built cases:84unaffected from full86pass retained,2final updated MUJ passed48.2s; no claim of a single final86-case invocation. Last change only adds legacy CLI preflight, separately verified by unit interposition and final real-worker/helper smoke.
- Final frozen API/frontend images; network disabled: exact original reproduces both preparations/manifests and all8diagnostic files byte-for-byte. Maps actually rendered/inspected; no policy bypass for blocked file:// navigation.
- Final built API/actual-worker/helper passes interrupted preview,3v1batch applies/replay, atomic22-operation correction/actor audits/retry, positive route and original-helper/public/source isolation.
- No OpenAPI/TS/template drift or new migration; prior0016migration rehearsal reused, fresh disposable container DBs migrate normally.
- Read-only retained receipts:22non-spatial counts/content hashes match, exact original unchanged, `.env` absent throughout, retained DB/private-upload volumes intact. No developer migration/seed/bootstrap/import/publication.

Owner-reported Windows v1 import/validation/routes are recorded separately. Windows DB was not inspected in the cloud; new PowerShell/correction command, real-device GPS, physical access/doors/accessibility, institutional approval and signs/printing/scanning remain unverified. Full data-preserving Windows update, secure preview/APPLY/manual inputs, offline diagnostics and prioritized exact-ID collection instructions provided. Independent source/content/audience review and publication remain future explicit actions. No warning acknowledgement/source approval/review submission/public MUJ release,4D–4F, merge, deployment, LAN/cloud publication, reset/reseed or volume removal.

- Findings/maps:`docs/data/muj-connectivity-review.md`, `docs/data/muj-connectivity/README.md`, `docs/data/muj-connectivity-v2/README.md`.
- Windows update/preview/APPLY:`docs/operations/muj-connectivity-review.md`.
- Results/failures/limits:`docs/testing/verification.md`; history:`docs/progress.md`; checklist:`docs/product/requirements-checklist.md`.

Compare/open PR: https://github.com/shagatron/SCNS/compare/feat%2Fmuj-osm-import...feat%2Fmuj-connectivity-review?expand=1
