# Review MUJ source connectivity and correct dataset disclosures

Base: `feat/muj-osm-import` at `1cd6533413e09069b0596b4c309458edccc49886`.
Head: `feat/muj-connectivity-review`. Open without merging.

MUJ draft routes incorrectly described real OSM-derived data as synthetic. The draft API now uses an unpublished/source-and-field-review notice with a synthetic supplement only for `campus.is_demo`; public step-free wording follows the same metadata. QR empty-state wording no longer assumes every sign is synthetic. Demo disclosures and the public redesign remain intact.

The attached exact original was checksum-verified and inspected against the completed v1 preparation. New offline diagnostics trace every stored edge to its canonical original node references, enumerate all29weak components/34unanchored destinations, and include excluded-way IDs/tags/shared-node memberships plus labelled standalone overview/subway figures. The practical report distinguishes converter defects, explicit policy/representation limitations and missing field/access evidence.

The raw subway chain exists, but private entrance10778271605, nonzero-layer/tunnel handling and a tunnel crossing the exact campus-polygon gap prevent safe public connectivity. Library12585506492 is a point within Administrative Block1158522861 with no entrance/path reference. Ground-floor-named corridors and multi-floor paths require evidence rather than flattening. A final source-pair coverage audit proved an overly broad whole-way exclusion. Separate v2 retains fully covered original runs from1159542817/926460863/1164290299; it never clips/invents boundary nodes. Original v1 bundles/IDs/manifests/receipts remain byte-identical. The guarded helper previews20additions(5nodes/14edges/1anchor) and2explicit replaced-edge deletions, then applies one normal GraphPatch/CAS/validation/audit transaction. It preserves unrelated edits, stops on affected edits/collisions/manual partial changes, safely reconciles lost-response retries, and blocks old v1 helper replay via immutable audit evidence. Every new audit record carries the v2 manifest marker; receipts bind server request ID. No full-bundle upsert or original-helper rerun. V2 has295nodes/700edges/22anchors/29components/33unanchored. New University Entrance→Mapped entrance10828149259 computes513.0969783921546m/13edges, previously unanchored; five established cases are unchanged. No new schema/routing/publication/authorization semantics.

Verification so far: final lint/type/format/build,150Python units,61frontend units,50earlier affected PostGIS tests plus first3new update tests passed; final53-case rerun and the2affected final MUJ source/built cases are in progress.28earlier desktop/mobile source journeys passed. Generated contracts/templates have no drift. Prior network-disabled API image reproduced v1 diagnostics; final v1/v2 reproduction is pending. Full86built journeys and original worker/helper passed before v2;84unaffected cases retained,2MUJ cases and the actual correction helper must rerun on final image. Final results and data receipts will be recorded before delivery.

Owner-reported Windows three-batch import/validation/route checks are recorded separately; their Windows campus/draft were not inspected in the cloud and no physical route/accessibility or new Windows update test is claimed. Full data-preserving PowerShell update, exact manual inputs, optional offline preview-only Docker command, and a prioritized exact-ID evidence collection list are documented.

Preserves retained accounts, `.env` status, data, private originals/uploads, volumes, drafts, releases, markers and restrictions. No warning acknowledgements, source approval, review submission, MUJ publication, merge, deployment, reset/reseed/volume removal or4D–4F work.

- Findings/maps: `docs/data/muj-connectivity-review.md`, `docs/data/muj-connectivity/README.md`.
- Windows update/manual/offline preview: `docs/operations/muj-connectivity-review.md`.
- Evidence/progress/checklist: `docs/testing/verification.md`, `docs/progress.md`, `docs/product/requirements-checklist.md`.

Compare/open PR: https://github.com/shagatron/SCNS/compare/feat%2Fmuj-osm-import...feat%2Fmuj-connectivity-review?expand=1
