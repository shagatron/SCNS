# Review MUJ source connectivity and correct dataset disclosures

Base: `feat/muj-osm-import` at `1cd6533413e09069b0596b4c309458edccc49886`.
Head: `feat/muj-connectivity-review`. Open without merging.

MUJ draft routes incorrectly described real OSM-derived data as synthetic. The draft API now uses an unpublished/source-and-field-review notice with a synthetic supplement only for `campus.is_demo`; public step-free wording follows the same metadata. QR empty-state wording no longer assumes every sign is synthetic. Demo disclosures and the public redesign remain intact.

The attached exact original was checksum-verified and inspected against the completed v1 preparation. New offline diagnostics trace every stored edge to its canonical original node references, enumerate all29weak components/34unanchored destinations, and include excluded-way IDs/tags/shared-node memberships plus labelled standalone overview/subway figures. The practical report distinguishes converter defects, explicit policy/representation limitations and missing field/access evidence.

The raw subway chain exists, but private entrance10778271605, nonzero-layer/tunnel handling and a tunnel crossing the exact campus-polygon gap prevent safe public connectivity. Library12585506492 is a point within Administrative Block1158522861 with no entrance/path reference. Ground-floor-named corridors and multi-floor paths require evidence rather than flattening. No source-proven graph correction is applied: all v1 bundles/IDs/manifests/receipts remain byte-identical; no new preparation, upsert/deletion/update workflow or original-helper rerun is needed. No new schema/routing/publication/authorization semantics.

Verification so far: final lint/type/format/build,137Python units,61frontend units,50affected PostGIS tests,32focused converter/diagnostic tests and28desktop/mobile source journeys passed. Generated contracts/templates have no drift. Final network-disabled API image reproduced all four diagnostics byte-for-byte. Final built regression/worker results and data receipts will be recorded before this PR is offered as complete.

Owner-reported Windows three-batch import/validation/route checks are recorded separately; their Windows campus/draft were not inspected in the cloud and no physical route/accessibility or new Windows update test is claimed. Full data-preserving PowerShell update, exact manual inputs, optional offline preview-only Docker command, and a prioritized exact-ID evidence collection list are documented.

Preserves retained accounts, `.env` status, data, private originals/uploads, volumes, drafts, releases, markers and restrictions. No warning acknowledgements, source approval, review submission, MUJ publication, merge, deployment, reset/reseed/volume removal or4D–4F work.

- Findings/maps: `docs/data/muj-connectivity-review.md`, `docs/data/muj-connectivity/README.md`.
- Windows update/manual/offline preview: `docs/operations/muj-connectivity-review.md`.
- Evidence/progress/checklist: `docs/testing/verification.md`, `docs/progress.md`, `docs/product/requirements-checklist.md`.

Compare/open PR: https://github.com/shagatron/SCNS/compare/feat%2Fmuj-osm-import...feat%2Fmuj-connectivity-review?expand=1
