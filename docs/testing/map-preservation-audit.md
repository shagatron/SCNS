# Map presentation preservation audit

Functional authority: `a30810d5b73ffd2d757f2c05de1ed2a59f2e39aa`. Audited redesign: `6baeaadb95b92f52ce09bdcadeab42e1ee182151`. Correction continues on `redesign/map-explorer`; no reset/worktree or retained data changes. This audit supersedes the earlier claim that passing redesign tests demonstrated preservation. Those results describe the former implementation, not feature parity.

## Method and current checkpoint

Full tracked diff reviewed, including all application files, changed/added tests, harness, documentation and screenshots. A clean archived baseline under `/tmp` shares only installed frozen dependencies; it is not a worktree and contains no developer `.env`/uploads. Baseline and original redesign run sequentially against separately named disposable fixture databases/storage, with the identical `preservation-observation.spec.ts` desktop/mobile journey. Baseline results and matched screenshots are recorded before corrections; final corrected comparison and regression verification are pending in this checkpoint.

## Findings and required corrections

| Area | Baseline behavior | Original redesign difference | Correction / acceptance |
|---|---|---|---|
| Homepage | Original hero/campus selector/status, counts, process, about/footer and section order | Directory body removed; extra link substituted. Apparent unchanged component files did not preserve their page context. | Restore baseline surrounding components and section structure. |
| Navigation | Places reaches the actual searchable directory; Explore and skip link reach baseline planner | Places reached an almost empty heading; skip added a sidebar-specific event | Restore App/focus helper and directory targets. |
| Directory | Six full cards, graphics/headings/building, details/description/aliases/code, floor/room and availability copy | Compact rows moved into planner sidebar; details required a new selected card; default Plan hid rows | Restore complete baseline directory, including inline catalog-only/unknown-access messages. |
| Search | Label/placeholder/max length, shared query, category, reset offset, contextual pending/error/retry/empty state | Moved away from Places; parent layout/state changed; errors no longer beside original directory | Restore baseline controls, query state and placement. |
| Pagination | Total/range plus visible Previous/Next with endpoint disabling | Moved; buttons hidden in default Plan mode | Restore baseline location and actions. |
| Place actions | Route here/Start here directly update fields, clear old route, open controls and focus field | Extra selection/card step and new action tree; new dedup/state behavior | Restore exact baseline handlers and focus helper. |
| Map actions | One click sets destination and focuses it, without calculating automatically | Click selected a floating card instead; destination stayed unchanged | Restore direct destination action. Category icon is visual only; keyboard activation may invoke that same action. |
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
| Mobile/scroll | Baseline map-first grid, normal document flow, original anchors/offsets and responsive breakpoints | New controls above map and collapsible results below; widespread typography/spacing | Restore baseline stylesheet/layout outside outdoor map. |
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

Only outdoor dark surfaces/vectors, mint route/halo and corresponding legend colour, original SVG category markers (with the original direct destination action), and frame-safe entrance dots are intended map presentation differences. Marker keyboard Enter/Space invokes the same baseline click action. Floor plans and surrounding controls remain original. The map-only exception boundary is additive resilience; contextual planner/linked-place errors deliberately improve placement without changing messages, requests, focus or navigation. Final observed evidence and any unresolved limits must be recorded before declaring completion.
