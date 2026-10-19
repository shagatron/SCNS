# Public redesign visual evidence

Actual source Chromium screenshots,13October2026, with an isolated synthetic public dataset. CSS viewport widths: desktop1440px, tablet768px, mobile360px and small mobile320px. Mobile emulation uses device-pixel ratio2.625, so PNG pixel dimensions exceed CSS viewport dimensions. These are not official university mapping, physical-phone/Windows/real-GPS testing or downloadable chat attachments. All12PNG files were checked nonempty, decoded and loaded with Pillow before committing. Overview/process/directory component captures hide floating navigation/skip-link overlays only during screenshot capture; normal navigation is shown on the homepage and remains tested. No administrative credentials/private upload content are pictured; QR screenshots use a separate anonymous browser context.

The homepage, overview, numbered process and directory are compared compositionally with the four supplied references; SCNS identity/copy and real published API records are original. Open controls show the real planner; closed controls demonstrate map/directions independence. The baseline computed route is256.88m/three edges, displayed257metres/4min estimated. Public counts exclude restricted records.

- [Desktop homepage](desktop-homepage.png)
- [360px homepage](mobile-homepage.png), [320px](small-mobile-homepage.png), [768px](tablet-homepage.png)
- [Published overview](desktop-overview.png), [process](desktop-how.png), [directory](desktop-directory.png)
- [Desktop explorer controls](desktop-explorer-controls.png), [360px controls](mobile-explorer-controls.png), [map/directions with controls collapsed](desktop-explorer-map.png)
- [Desktop QR confirmation](desktop-qr.png), [mobile QR](mobile-qr.png)

These static captures do not demonstrate animation. Native scrolling, active navigation, reduced motion, no-animation initialization, keyboard/reload/error recovery and browser accessibility checks are documented in docs/testing/verification.md.
