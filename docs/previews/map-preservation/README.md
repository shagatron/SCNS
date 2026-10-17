# Matched baseline and corrected presentation

Functional baseline **a30810d** versus corrected application checkpoint **55a5a61** on `redesign/map-explorer`. These are actual browser renders against separate disposable **synthetic Demo** fixtures, not Windows, actual MUJ/E22 release, real GPS, field/accessibility or human assistive-technology evidence. The original rejected redesign is6baeaad.

Both use the same1440×960desktop and390×960mobile CSS viewports, reduced motion and stored graph. Full component screenshots can exceed viewport height; Pixel7 emulation has a higher pixel ratio. The existing fixed navigation/skip-link are hidden **only during screenshot capture** to frame full components without fixed overlays. Navigation/focus/scroll checks run with those controls present. Images are copied exactly, without post-capture editing. [Manifest](manifest.json) records decoded dimensions, bytes, SHA256 and pixel comparisons.

| Component / state | Baseline desktop | Corrected desktop | Baseline mobile | Corrected mobile |
|---|---|---|---|---|
| Intro | [Before](baseline/desktop-chromium/intro.png) | [After](corrected/desktop-chromium/intro.png) | [Before](baseline/mobile-chromium/intro.png) | [After](corrected/mobile-chromium/intro.png) |
| Complete directory | [Before](baseline/desktop-chromium/directory.png) | [After](corrected/desktop-chromium/directory.png) | [Before](baseline/mobile-chromium/directory.png) | [After](corrected/mobile-chromium/directory.png) |
| Original planner | [Before](baseline/desktop-chromium/planner.png) | [After](corrected/desktop-chromium/planner.png) | [Before](baseline/mobile-chromium/planner.png) | [After](corrected/mobile-chromium/planner.png) |
| Computed route + directions | [Before](baseline/desktop-chromium/route.png) | [After](corrected/desktop-chromium/route.png) | [Before](baseline/mobile-chromium/route.png) | [After](corrected/mobile-chromium/route.png) |
| No route | [Before](baseline/desktop-chromium/no-route.png) | [After](corrected/desktop-chromium/no-route.png) | [Before](baseline/mobile-chromium/no-route.png) | [After](corrected/mobile-chromium/no-route.png) |
| Contextual search error | [Before](baseline/desktop-chromium/search-error.png) | [After](corrected/desktop-chromium/search-error.png) | [Before](baseline/mobile-chromium/search-error.png) | [After](corrected/mobile-chromium/search-error.png) |

All **six paired intro/directory/planner comparisons are pixel-identical**. Route maps intentionally differ in dark vector/route/category presentation; original result metrics/text and full-width directions remain. The no-route message is unchanged and deliberately placed beside planner controls. Search feedback remains beside its original directory controls. Matched runtime records differ only in that requested route-error parent; they also check exact map focus order, original defaults/actions, navigation, search, route and hidden-map directions.

For contrast, the rejected redesign's missing directory is preserved: [desktop](redesign-original/desktop-chromium/directory.png), [mobile](redesign-original/mobile-chromium/directory.png). Historical broader screenshots remain under `../map-explorer/` and are not current-interface evidence.

See [complete feature/test audit](../../testing/map-preservation-audit.md), [runtime observations](../../testing/map-preservation-observations.json), [source boundary checks](../../testing/map-preservation-source-audit.json), [verification sequence](../../testing/verification.md) and [update/manual walkthrough](../../operations/map-explorer.md). Built-container five-width captures are added after final regression; browser emulation does not replace actual phone/keyboard testing.
