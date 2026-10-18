# Original educational indoor demonstration — rendered evidence

**Demonstration layout — not an actual MUJ floorplan.** These PNGs show original SCNS educational schematics, never the supplied Nalanda blueprints or a surveyed/approved MUJ plan. The MUJ-entry image uses accurately labelled **metadata-response simulation over an isolated synthetic published release**, not the owner's Windows database.

Final captures come from built Linux nginx/API/worker desktop/mobile browser journeys. Routes are computed by the real educational endpoint using the existing production Dijkstra engine. All10PNG files were independently verified non-empty and decoded, with sizes/dimensions/SHA256 in [manifest.json](manifest.json). No screenshot editing/compositing. Offscreen skip links are hidden only during full-page capture to avoid capture artifacts; actual visibility/focus/skip-target behavior has separate browser assertions. Existing accepted homepage54screenshots and supplied photo/logo remain unchanged.

| View | Desktop | Emulated mobile |
|---|---|---|
| Ground floor, A→Library,3traversals | [Ground floor](desktop-chromium/ground-same-floor.png) | [Ground floor](mobile-chromium/ground-same-floor.png) |
| Ground section, A→C cross-floor route | [Ground cross-floor](desktop-chromium/ground-cross-floor.png) | [Ground cross-floor](mobile-chromium/ground-cross-floor.png) |
| First section, A→C cross-floor route | [First floor](desktop-chromium/first-cross-floor.png) | [First floor](mobile-chromium/first-cross-floor.png) |
| Full computed route,9traversals and stair/text instructions | [Computed cross-floor route](desktop-chromium/computed-cross-floor.png) | [Computed cross-floor route](mobile-chromium/computed-cross-floor.png) |
| Additive MUJ entry, simulated metadata only | [Entry](desktop-chromium/muj-entry-simulated.png) | [Entry](mobile-chromium/muj-entry-simulated.png) |

Both floor views and full-route/entry renders were inspected. The paper-background correction makes demo headings readable; fractional fit zoom improves the schematic fit and redundant permanent transition labels no longer cover room labels. Narrow phone fit views need zoom to read small schematic text; selectors and text directions stay full-size. Actual Windows, physical phones, human assistive technology, real buildings/accessibility and field routes remain unverified.

[Complete Windows Docker update and presentation](../../operations/educational-indoor-demo.md) · [Checks and preservation](../../testing/educational-indoor-demo.md).
