# Educational indoor demonstration: verification and preservation

Baseline: `polish/muj-homepage` at ee683e1a61a6584147c3e39b121a8765db5e46ba. Feature branch: `feat/muj-indoor-demo`. Explicitly unfinished checkpoints8302130andf0ec199 preserve the original graph/schematics and interrupted UI/verification work. No native-Windows changes are included. This file records cloud/Linux verification; Windows/physical-device acceptance is separate and pending.

## Preservation boundary

Compared complete production changes with the accepted baseline. Existing App, CampusExplorer, routing algorithms/services, route details, admin, QR/GPS/closures, homepage sections/directory/actions/defaults and dependency locks/Compose/migrations remain unchanged. CampusOpening gets one MUJ-only entry and disclosure; public CSS adds only its scoped entry styles. Main selects a separately lazy-loaded /indoor-demo route. Shared FloorRouteMap accepts a deliberately educational mode; the default approved-plan wording/markers/coordinate behavior stays intact. MapFailureBoundary adds optional demo-specific text, preserving its original default message.

No static floor plan is presented as an approved/public campus release. The educational API reads no database/session and performs no writes. Existing unknown accessibility and Directions-only route contracts are retained. The demo reuses pure Dijkstra and indoor geometry/rendering; it does not fabricate approved connector flags in the published mixed-release pipeline. Static synthetic IDs cannot target a real campus record.

| Acceptance / preservation check | Evidence |
|---|---|
| Original floors, generic rooms, prominent qualification; no copied PDF content | Original SVG generator and assets; visual inspection/screenshots; no reference PDF or blueprint added to repository |
| Same/cross/reverse/same-room/disconnected computation | Backend unit tests assert3/9/9/0traversals, stair direction, nullable measurements; desktop/mobile real-API journeys assert matching highlights, explicit transition and no-route clearing |
| Floors/route frames, reload, hidden-map independent text | Shared frame filter and browser assertions for four segments per cross-floor section, arrival buttons/floor selection/reload and map toggle |
| Unknown metrics and conservative accessibility wording | Response types constrain physical totals to null; no guessed scale/ETA; frontend tests and browser metric-text assertions; no step-free option or verification fields |
| Loading/error/retry/empty/image failure, keyboard/mobile | Dedicated component tests and desktop/mobile delay/failure/empty/image retry/keyboard/width/axe checks |
| Existing homepage/photo/logo/full directory/planner/defaults/actions | Original public-experience, navigation and homepage suites retained without weakening/replacing baseline assertions; MUJ entry uses accurately labelled metadata-response simulation over isolated synthetic release |
| Existing published indoor/QR/GPS/closures/admin/release recovery | Original source journeys and built affected regressions; real campus policies/data untouched |
| Actual source-OSM MUJ route baseline (isolated fixtures) |33PostGIS/API integration checks passed: University→E05metric513.10m/13; Directions only799.32m/9; Hostel→GHS23.62m/3; Hostel→Faculty163.28m/6. This uses the original OSM preparation in disposable fixtures, **not the owner's Windows database or a physical route** |
| Retained developer data | Resume captures all22retained table counts/content hashes and root.envpresence read-only before verification; final comparison recorded below. Tests use newly owned databases/storage, never the retained dataset. |

## Verification results

Completion results are recorded after the final affected source and built reruns. Earlier interrupted /tmp logs are unavailable in this resumed environment; do not infer their completion. Reused earlier observed backend success was confirmed by a fresh275-unit run; frontend75tests/type/lint/build now pass after explicit label associations and the typed test-fixture correction. Real renderer inspection additionally caught dark foreground on an inherited dark demo background despite passing functional/axe checks. A demo-only paper background and an explicit rendered-color assertion correct this; final renders/checks must reflect that correction.

No owner Windows result, actual MUJ database verification, live GPS/field survey, independent human/institutional approval, real accessibility verification or public deployment is claimed. The educational graph itself intentionally has no outdoor/GPS/QR/live restriction integration; those existing features remain in the ordinary public explorer.
