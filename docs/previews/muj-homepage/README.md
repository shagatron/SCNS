# MUJ homepage polish — matched renders

Baseline `4fbc61663add1a31df0cda66e065e73a542f6fed` includes the completed map-preservation correction. Its 12 before PNGs and two runtime records from checkpoint `a030089` remain byte-for-byte intact: [original manifest](manifest-before.json). All PNGs in the [complete size/hash/dimensions manifest](manifest.json) decode. Captures are unedited browser renders.

## MUJ branding comparison

These use **simulated MUJ metadata over isolated synthetic published releases**. Before runs the exact archived parent frontend; after runs the compiled nginx frontend against the same API fixture. They do not represent the owner's Windows database, actual MUJ route data, institutional approval or a physical phone. Full parent/current workflow records match in [desktop](matched-muj/desktop-chromium/matched-muj.json) and [mobile](matched-muj/mobile-chromium/matched-muj.json).

| Surface | Desktop before → after | Mobile before → after |
|---|---|---|
| Hero | [Before](matched-muj/desktop-chromium/muj-before-intro.png) → [After](matched-muj/desktop-chromium/muj-after-intro.png) | [Before](matched-muj/mobile-chromium/muj-before-intro.png) → [After](matched-muj/mobile-chromium/muj-after-intro.png) |
| Full directory | [Before](matched-muj/desktop-chromium/muj-before-directory.png) → [After](matched-muj/desktop-chromium/muj-after-directory.png) | [Before](matched-muj/mobile-chromium/muj-before-directory.png) → [After](matched-muj/mobile-chromium/muj-after-directory.png) |
| Planner | [Before](matched-muj/desktop-chromium/muj-before-planner.png) → [After](matched-muj/desktop-chromium/muj-after-planner.png) | [Before](matched-muj/mobile-chromium/muj-before-planner.png) → [After](matched-muj/mobile-chromium/muj-after-planner.png) |
| No route | [Before](matched-muj/desktop-chromium/muj-before-no-route.png) → [After](matched-muj/desktop-chromium/muj-after-no-route.png) | [Before](matched-muj/mobile-chromium/muj-before-no-route.png) → [After](matched-muj/mobile-chromium/muj-after-no-route.png) |
| Contextual search error | [Before](matched-muj/desktop-chromium/muj-before-search-error.png) → [After](matched-muj/desktop-chromium/muj-after-search-error.png) | [Before](matched-muj/mobile-chromium/muj-before-search-error.png) → [After](matched-muj/mobile-chromium/muj-after-search-error.png) |

The original directory, descriptions, pagination, actions, planner policies and dark outdoor map remain. Only MUJ receives the original photograph/emblem/student-project attribution; public sections use warm cream/amber accents. No replacement sidebar or modes.

## Demo Campus baseline comparison

Demo retains its synthetic disclosure and requests no MUJ assets. Before/after runtime records are equal in [desktop](after/desktop-chromium/observations.json) and [mobile](after/mobile-chromium/observations.json), including all recorded focus/scroll/default/copy/direction/error observations. Screenshots differ intentionally in the public palette.

| Surface | Desktop before → after | Mobile before → after |
|---|---|---|
| Intro | [Before](before/desktop-chromium/intro.png) → [After](after/desktop-chromium/intro.png) | [Before](before/mobile-chromium/intro.png) → [After](after/mobile-chromium/intro.png) |
| Directory | [Before](before/desktop-chromium/directory.png) → [After](after/desktop-chromium/directory.png) | [Before](before/mobile-chromium/directory.png) → [After](after/mobile-chromium/directory.png) |
| Planner | [Before](before/desktop-chromium/planner.png) → [After](after/desktop-chromium/planner.png) | [Before](before/mobile-chromium/planner.png) → [After](after/mobile-chromium/planner.png) |
| Computed route | [Before](before/desktop-chromium/route.png) → [After](after/desktop-chromium/route.png) | [Before](before/mobile-chromium/route.png) → [After](after/mobile-chromium/route.png) |
| No route | [Before](before/desktop-chromium/no-route.png) → [After](after/desktop-chromium/no-route.png) | [Before](before/mobile-chromium/no-route.png) → [After](after/mobile-chromium/no-route.png) |
| Search error | [Before](before/desktop-chromium/search-error.png) → [After](after/desktop-chromium/search-error.png) | [Before](before/mobile-chromium/search-error.png) → [After](after/mobile-chromium/search-error.png) |

## Crop and failure inspection

Actual compiled hero captures with long names: [320](inspection/desktop-chromium/muj-320.png), [360](inspection/desktop-chromium/muj-360.png), [390](inspection/desktop-chromium/muj-390.png), [768](inspection/desktop-chromium/muj-768.png), [1440](inspection/desktop-chromium/muj-1440.png), [mobile project](inspection/mobile-chromium/muj-390.png). The original logo's alpha and proportions are preserved. All crops retain the central dome/finial; the 736px original limits large-display sharpness.

[Delayed/failed assets with visible focus](inspection/desktop-chromium/asset-failure-360.png) preserve all controls and hero size at a simulated 360×500 viewport; this is **not** a physical keyboard test. Unchanged anonymous admin: [desktop](inspection/desktop-chromium/admin-login.png), [mobile](inspection/mobile-chromium/admin-login.png). High-DPI mobile PNG dimensions reflect configured browser scale and full section height.

Navigation is hidden only during section screenshot capture using the unchanged baseline helper; application navigation remains present. No image editing, physical-device/GPS or actual Windows/MUJ database verification. [Preservation checklist](../../testing/muj-homepage-preservation.md), [verification](../../testing/verification.md), [Windows update/manual checks](../../operations/muj-homepage-polish.md).
