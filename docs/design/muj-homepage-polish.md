# MUJ homepage polish — unfinished baseline checkpoint

18 October 2026 (owner timezone). Verified clean parent/local remote `feat/muj-path-connectivity` at4fbc61663add1a31df0cda66e065e73a542f6fed, including restored map8798fa3 and subsequent completed data-audit work. Created `polish/muj-homepage`; no reset/worktree/discard. Read `docs/testing/map-preservation-audit.md`, current progress, public styles/components and original observational browser assertions before editing.

## Current blocker

Owner supplied inline previews and subsequently named `muj-campus.png` and `muj-logo.png`. No original image file, local path or downloadable Sediment file reference has arrived. Actual searches of `/workspace/attachments`, `/workspace`, `/tmp` and `/mnt` found neither named file; attachment directory contains specification/request text and the earlier OSM export only. The text-only clarification reply does not supply image bytes. Do not substitute a downloaded/generated/redrawn image or assume the logo preview's black background is embedded. Alpha, pixel dimensions, cropping, compression and image-failure/contrast checks require the actual originals.

No application code/assets/styles changed at this checkpoint. Resume after original files arrive; download and decode both, record hashes/dimensions/formats, inspect logo alpha, retain natural proportions and owner-supplied provenance without inventing rights/endorsement. Asset use is not map-data approval.

## Affected UI inventory and preservation contract

| Surface | Existing behavior/content to keep | Intended visual-only work / evidence still required |
|---|---|---|
| Intro / CampusOpening | Existing SCNS identity/headline, Explore campus selector/locking, About the data, Explore action, service status, synthetic Demo disclosure, intro target | MUJ-only photo/emblem at natural proportions; precise campus metadata identification, no Demo branding leakage; restrained dark overlay, deliberate dome-preserving crops, concise student-project/not-official attribution. No changes to selector/state/events/defaults/anchors. |
| Main navigation / PublicMotion / App | Same sections/order/targets, skip link, focus and hash/reload/reveal behavior; about/footer | Preserve source logic; no new modes/sidebar/feature relocation or animation. |
| Directory | Full6cards, matching/category/pagination/reset, descriptions/aliases/codes, room/floor qualifications, both direct actions and focus | Modest type/spacing/palette/control refinements only; retain all DOM actions and content. |
| Planner / directions | Main Gate/manual, shortest/metric defaults, traversal/fastest/step-free copy and qualifications, swap/clear, native route controls, map-independent results | Existing control order/actions and result content; contextual pending/error/no-route/retry remains beside corresponding controls, no new scroll/focus call. |
| Outdoor / indoor maps | Dark outdoor vectors/mint routes/category symbols, direct pin destination selection, original bounds/Fit/resize; approved floor images/controls | No map interaction, selection, layer or floor-image redesign. |
| QR/GPS/restrictions/releases | Existing explicit confirmation/expiry/revocation, restricted/stale/offline safety gates and reload/recovery | No state/API/algorithm/message/default changes. Browser GPS remains simulated, no live tracking. |
| Admin/backend/data | Byte-preserved independent admin, contracts/schema/permissions/published releases/source data | No redesign, migration/new data workflow/helper replay/publication or dependencies. |
| Responsive/accessibility | All controls visible at320/360/390/768/1440, keyboard/focus/44px targets/reduced motion | Actual photo contrast/crops, long names, responsive reduced-height keyboard-space simulation, no overflow, allocated image space/no lazy hero, no image-loading jump, both asset-failure fallbacks. Physical phone keyboard/AT/Windows explicitly unverified unless owner reports. |

## Baseline evidence saved

Current source app ran with normal stored-graph API and disposable `scns_homepage_20261018_e2e_test` plus temporary private fixture storage. Existing unchanged `preservation-observation.spec.ts` journey passed **2/2desktop/mobile**,12.4s. Initial structure/navigation/places/search/defaults/actions/focus, computed Library route/directions, map-independent directions, no-route and contextual search error captured. No application changes, no rewritten assertions. Existing baseline runner initializes only its disposable test schema; no migration/reseed on retained developer data.

[Before captures and runtime observations](../previews/muj-homepage/README.md):12non-empty decoded PNGs and2observation JSON files, checksummed. Desktop/mobile intro rendered and inspected; captures include directory/planner/route/no-route/search error for later matching. These are synthetic source-fixture evidence, not actual Windows, real MUJ release or physical phone verification. No after screenshots/asset integration/completion claim. Final frontend lint/type/unit/build, affected original journeys and final rendered/retained-data checks remain pending after implementation.

## Resume without restarting

1. Verify original PNG delivery; inspect/decode/hash both and logo alpha; create optimized photo derivatives using standard tools only (user expressly requested standard-tool derivatives), avoid upscaling, preserve dome/composition and unmodified logo lettering/transparency. Keep originals/provenance in an appropriate public-asset location, no external substitute.
2. Preserve this parent/baseline and existing behavior. Scope implementation to CampusOpening/new small branding component and public-only styles; retain PublicNavigation/PublicMotion/CampusExplorer/maps/App state/handlers. Use restrained warm cream/ink/amber accents; Demo keeps synthetic identity. No source data or publication changes.
3. Add focused branding/asset-failure/content-preservation tests; do not weaken original behavior assertions. Save/push implementation checkpoint before longer verification. Reuse this saved before evidence and do not restart baseline audit.
4. Run lint/type/unit/build and affected desktop/mobile original navigation/QR/GPS/closure/floor/recovery journeys with disposable resources; inspect5widths/long names/reduced height/failures/admin, save matching after captures and accurate verification. Preserve22table/.env baseline and all retained volumes/storage.
5. Finish operations/checklist/progress/evidence and full frontend-only loopback Windows commands. Preserve but exclude stale phone override, start/check retained DB before API readiness. Push completion/verify remote/clean tree; attempt PR against `feat/muj-path-connectivity`, save prepared body/compare if blocked. No deployment or environment publication.
