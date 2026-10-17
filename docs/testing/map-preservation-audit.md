# Map presentation preservation audit

Functional authority: `a30810d5b73ffd2d757f2c05de1ed2a59f2e39aa`. Audited redesign: `6baeaadb95b92f52ce09bdcadeab42e1ee182151`. Correction continues on `redesign/map-explorer`; no reset/worktree or retained data changes. This audit supersedes the earlier claim that passing redesign tests demonstrated preservation. Those results describe the former implementation, not feature parity.

## Method and evidence boundaries

Full tracked diff reviewed, including all application files, changed/added tests, harness, documentation and screenshots. A clean archived baseline under `/tmp` shares only installed frozen dependencies; it is not a worktree and contains no developer `.env`/uploads. Baseline and original redesign run sequentially against separately named disposable fixture databases/storage, with the identical `preservation-observation.spec.ts` desktop/mobile journey. Baseline and original-redesign results were recorded before corrections. Final corrected runtime records match each viewport’s actual baseline, including map focus order; only requested route-error placement differs. Intro/directory/planner captures are pixel-identical in both layouts. Full built regression outcome is recorded in verification.

## Findings and correction criteria

| Area | Baseline behavior | Original redesign difference | Correction / acceptance |
|---|---|---|---|
| Homepage | Original hero/campus selector/status, counts, process, about/footer and section order | Directory body removed; extra link substituted. Apparent unchanged component files did not preserve their page context. | Restore baseline surrounding components and section structure. |
| Navigation | Places reaches the actual searchable directory; Explore and skip link reach baseline planner | Places reached an almost empty heading; skip added a sidebar-specific event | Restore App/focus helper and directory targets. |
| Directory | Six full cards, graphics/headings/building, details/description/aliases/code, floor/room and availability copy | Compact rows moved into planner sidebar; details required a new selected card; default Plan hid rows | Restore complete baseline directory, including inline catalog-only/unknown-access messages. |
| Search | Label/placeholder/max length, shared query, category, reset offset, contextual pending/error/retry/empty state | Moved away from Places; parent layout/state changed; errors no longer beside original directory | Restore baseline controls, query state and placement. |
| Pagination | Total/range plus visible Previous/Next with endpoint disabling | Moved; buttons hidden in default Plan mode | Restore baseline location and actions. |
| Place actions | Route here/Start here directly update fields, clear old route, open controls and focus field | Extra selection/card step and new action tree; new dedup/state behavior | Restore exact baseline handlers and focus helper. |
| Map actions | One click sets destination and focuses it, without calculating automatically | Click selected a floating card instead; destination stayed unchanged | Restore direct destination action. Category icon is visual only; original map tab order and directory keyboard actions remain. |
| Map place coverage | All initial public geographic places and permanent names | Decluttering hid pins; only hovered/selected names shown; different records fed into map | Restore original record input, all pins and permanent labels. |
| Planner | Original grid/card, headings, field order, defaults and native open route details | New sidebar/brand/campus selector, browse/plan/collapse states and different form dimensions | Restore baseline, remove replacement states/controls. |
| Policies | Main Gate/manual default, shortest/metric; directions-only traversal wording/fastest disabled, step-free qualifications | Values mostly retained but control context/styles changed | Preserve exact state, copy, values and eligibility. |
| Restrictions | Baseline operational aside/retry/items/estimated-end qualifications, stale safety gates | Moved to workspace header; duplicate notices/status copy introduced | Restore original aside/state/copy and unsafe-result notice. |
| QR | Explicit confirmation, locked campus, source/swap rules, stale/revocation/reload recovery | Extra campus selector and new surrounding controls | Restore baseline shell/notice/control behavior; rerun original journeys. |
| GPS | Explicit opt-in/confirmation, manual/QR fallback, expiry/context invalidation/privacy | Location notices relocated, extra workspace copy | Restore baseline component/context and status location; simulated tests only. |
| Result/directions | Full-width results after original grid, independent of controls/map visibility | Moved into collapsible sidebar; smaller metrics/directions and new condensed summary | Restore full original result tree, original copy/metrics/assumptions/view buttons. |
| Route errors | Same API/validation/no-route messages and retry state | Moved to workspace header, away from form | Place route API pending/error feedback beside planner controls without scroll/focus calls. Preserve original copy; this is an explicit contextual-error correction. |
| Linked-place errors | Recover shared route fields through existing retry | Baseline error already in map column; redesign retained it there | Put field-recovery errors beside planner; preserve existing retry and state. |
| Release recovery | Original availability boundary, stale route hiding/query invalidation and epoch/remount/retry | New planner states/selection tree remounted within this lifecycle | Restore exact lifecycle/state and original notices; rerun release/reload cases. |
| Outdoor bounds | Original28px fit padding, route/campus bounds and resize refit |48px padding and resize no longer refitted | Restore baseline bounds/resize behavior. |
| Floor view | Original floor/frame filtering, unfiltered approved image, retry, permanent labels and transition/start/end markers | New selectable place markers, hidden labels and different resize behavior | Restore entire baseline FloorRouteMap. |
| Mobile/scroll | Original planner/map document flow, normal document flow, original anchors/offsets and responsive breakpoints | New controls above map and collapsible results below; widespread typography/spacing | Restore baseline stylesheet/layout outside outdoor map. |
| Errors/loading | Original search/planner/floor/map statuses in their relevant sections | Workspace header gathered unrelated errors; CSS altered surrounding boxes | Restore contextual states; no error-triggered scrolling or focus transfer. |
| Failure boundary | API/image failures already retained text; lazy chunk exception could blank root | New map-only exception fallback | Keep additive map-only exception boundary, document this intentional recovery improvement; no normal-path action change. |
| Retained styling | Existing editorial shell and approved floor image colours | Dark tokens/buttons/form/result styling applied to whole explorer | Retain only dark outdoor map/vector/route/category styles scoped to `.outdoor-panel`; surrounding styles equal baseline. |
| Data/API/admin | Existing contracts, source data, backend, permissions and admin | No tracked changes in these areas | Keep byte-identical; verify retained DB count/content digests and `.env` presence. |

## Complete application/test diff disposition

| Files | Disposition |
|---|---|
| `App.tsx`, `focusPlanner.ts`, `FloorRouteMap.tsx` | Restore byte-for-byte baseline. |
| `CampusExplorer.tsx` | Restore baseline state/handlers/structure/copy. Only map CSS import, map exception boundary and contextual route/linked-place feedback remain as bounded differences. |
| `OutdoorMap.tsx`, `explorer.css` | Start from baseline; apply dark map vectors/route/category icons only. Restore all baseline actions, messages, fit/resize and pin coverage. |
| `routePresentation.ts`, `placeSymbols.ts` | Retain pure frame-safe entrance decoration and original fixed SVG category paths; no state/data changes. |
| `ExplorerPlaces.tsx`, `PlaceIcon.tsx` | Retire replacement directory/card components; Git history preserves prior work. |
| `MapFailureBoundary.tsx` | Keep isolated exception fallback, covered separately. |
| `indoor.spec.ts` | Restore baseline assertion path: heading and full catalog-only qualification visible immediately after search, without extra Select step. Previous adaptation concealed a real loss of direct visibility. |
| `public-experience.spec.ts` | Restore baseline2px planner button assertion. Previous10px adaptation accepted an out-of-scope surrounding control change. |
| `navigation.spec.ts`, `publication.spec.ts` | Retain only allowed outdoor stroke/overlay colour selector changes; all original behavior/privacy/review/rollback assertions stay. |
| `indoor-routing.spec.ts` | Retain original assertions plus additive exact entrance-indicator check. |
| Added explorer tests | Replace assertions for removed unrequested sidebar states with strict baseline directory/actions/defaults/errors/focus/resize checks. Retain renderer failure, width/axe and map-independent route coverage. |
| Added place-card units | Retire units for removed replacement components, retain map error-boundary coverage. Frame-safe projection units remain. |
| Source-response visual test | Keep explicitly simulated source context, adapt only to restored search/category/map action; never claim Windows/MUJ DB evidence. |
| Browser harness | Keep default regression suite; include new preservation checks. No assertion suppression or retained DB targeting. |
| Design/operations/checklist/evidence/previews | Supersede former structural-redesign guidance; retain old results/screenshots as historical, clearly marked. Add matched baseline/corrected evidence and current limitations. |

## Intentional differences remaining after correction

Only outdoor dark surfaces/vectors, mint route/halo and corresponding legend colour, original SVG category markers (with the original direct destination action), and frame-safe entrance dots are intended map presentation differences. Pins add no tab stops, preserving baseline map/directory keyboard order; directory actions remain keyboard accessible. Floor plans and surrounding controls remain original. The map-only exception boundary is additive resilience; contextual planner/linked-place errors deliberately improve placement without changing messages, requests, focus or navigation. Final observed evidence and any unresolved limits must be recorded before declaring completion.

## Completed parity checklist

These items are verified by the complete source comparison, actual pinned-baseline/original/corrected runs, matched component captures and final compiled104-case suite. Passing redesigned selectors alone is not the evidence basis. Exact runs/rechecks and limits are in [verification](verification.md).

- [x] Full affected application/test/harness/documentation diff reviewed; eight surrounding source files match baseline bytes, plus state/query/handler and fit/resize equality checks.
- [x] Homepage intro/campus selection/readiness, overview/counts, process, about/footer content and original section order restored.
- [x] Original navigation/Places/Explore/skip targets, normal scrolling and focus helper restored; Places reaches the actual directory.
- [x] Complete six-card directory, graphics/headings/buildings, details/descriptions/aliases/codes/floor/room and direct unknown/unmapped/catalog-only qualifications restored.
- [x] Original search/alias/code matching, placeholder/max length, category list, empty/loading/error/retry, pagination totals/ranges/endpoints and offset reset retained.
- [x] Start here and Route here remain sequentially available without mode switching; original field update/clear/open/focus behavior and no automatic calculation retained.
- [x] Original initial public map place input, all pins/permanent names, direct destination click, zoom/Fit/bounds/resize and map keyboard tab order retained. Icons add no tab stops.
- [x] Original planner grid/controls/order/typography/buttons, Main Gate/shortest/metric defaults, swap/clear and native details retained.
- [x] Metric/traversal/fastest/step-free policy wording, eligibility, estimate/unknown-distance/accessibility qualifications unchanged.
- [x] Stored-edge computation, no-route/same-place/unknown-cost behavior, distance/nullable ETA/assumptions and original full-width independent directions retained.
- [x] Hide map, native control collapse, direction section buttons, shared manual-route URL and reload recovery retained.
- [x] Floor/building controls, reviewed floor/frame filtering, original approved image colours/coordinates, image retry, labels, connectors/stairs/lift/mixed journeys and intentional disconnected routes retained.
- [x] QR confirmation, locked campus, planned/unavailable/revoked fallback, source/swap behavior and reload/revalidation retained.
- [x] GPS explicit opt-in/landmark confirmation, simulated denial/inaccuracy/outside/unmatched/context/release/expiry, manual/QR fallback and coordinate privacy retained. No GPS floor inference or live tracking.
- [x] Closure check/freshness/overlay/context invalidation, unsafe-result hiding, unresolved restriction state, estimated-end/operator-verification messages and reopening behavior retained.
- [x] Release metadata/initial availability, stale data hiding, exact clear/remount/invalidation/query/retry/periodic recovery retained; unchanged baseline publication assertions rechecked serially.
- [x] Search failures stay beside directory controls; unchanged route/shared-place feedback is beside planner; deferred API test verifies no error-driven scroll/focus jump, with selections preserved. Map/floor/metadata retries remain contextual.
- [x] Keyboard form/navigation/skip/actions, five-width overflow/axe/reduced-motion checks and original mobile document flow retained. Native device/AT testing is separately unverified.
- [x] Baseline indoor immediate-visibility and2px surrounding-control assertions restored; only permitted outdoor colour selectors differ in original tests. Tests for withdrawn unrequested components replaced with baseline behavioral checks.
- [x] Exact per-viewport baseline runtime contract, source boundary checks and six pixel-identical intro/directory/planner pairs pass; original rejected-directory evidence retained.
- [x] Frontend lint/type/build/65units pass; final affected source29pass/1intentional skip and full built103pass/1skip, actual worker and private/readiness boundaries pass. Initial failures/rechecks remain disclosed.
- [x]31PNG files non-empty/decoded/checksummed; compiled320/360/390/768/1440px renders and matched desktop/mobile controls/errors/directions inspected.
- [x] Retained22table counts/content digests and `.env` presence exactly unchanged after all checks. Only owned disposable DBs/storage/containers/network and regenerable old build cache cleaned; volumes/accounts/uploads/drafts/releases untouched.

The intentional differences are limited to the outdoor presentation, frame-safe visual entrance dots, specifically requested contextual feedback placement and the additive map-only exception fallback described above. Actual Windows, published MUJ/E22 data, real-device keyboard/GPS, human AT, physical-route and accessibility verification are not claimed. No merge, publication of retained data, deployment or later milestone.
