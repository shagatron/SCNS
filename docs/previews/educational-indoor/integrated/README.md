# MUJ explorer: integrated educational floor viewer

**Demonstration layout — not an actual MUJ floorplan.** MUJ metadata is simulated over an isolated synthetic release in these Linux/Chromium checks. These are not screenshots of the owner's Windows database, a real MUJ building or field verification.

| Explorer view | Desktop | Emulated mobile |
|---|---|---|
| Ground-floor section, computed Classroom A → Classroom C | [Ground](desktop-chromium/integrated-ground.png) | [Ground](mobile-chromium/integrated-ground.png) |
| First-floor section of the same computed route | [First](desktop-chromium/integrated-first.png) | [First](mobile-chromium/integrated-first.png) |
| Entire explorer, mode tabs, room controls and computed stair/text directions | [Cross-floor route](desktop-chromium/integrated-cross-route.png) | [Cross-floor route](mobile-chromium/integrated-cross-route.png) |

The floating navigation/skip link is hidden only during screenshot capture so it does not cover the selected section; actual navigation/focus behavior is tested separately. No image compositing or blueprint substitution. Small schematic text at whole-floor phone fit needs zoom; full-size room selectors and text directions remain independent of the map. All6PNGs were captured against the final built nginx/API/worker runtime and inspected; [manifest.json](manifest.json) records non-empty file sizes, decoded dimensions and SHA256; final capture/runtime and inspection evidence is in [verification](../../../testing/educational-indoor-demo.md).

The [original standalone images](../README.md) and accepted homepage screenshots remain historical evidence, unchanged. The old extra homepage demo link is removed; the primary entry is **MUJ → Explore ↗ → Indoor demo**. `/indoor-demo` remains a compatibility view using the same component/API.

[Windows Docker update and manual presentation](../../../operations/educational-indoor-demo.md).
