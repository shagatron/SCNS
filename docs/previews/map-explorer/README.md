# Public map explorer: rendered previews

Captured 17 October 2026 from the final **built nginx frontend**, image SHA256 `3f041fa78566f3e08de415059eb09ef2f999233263cfdf665de5d7f76b59d5a4`, with an isolated API/worker, disposable database and temporary storage. All 16 non-empty PNGs were decoded/loaded and copied byte-for-byte; dimensions, sizes and SHA256 are in [manifest.json](manifest.json).

## Synthetic Demo Campus

These are invented campus data, not real-world navigation. Routes use the real backend/Dijkstra against stored test graph edges: Main Gate → Library 256.88m / 3 edges, displayed approximately 257m / 4min. Viewport captures are 960px high; ordinary page scrolling exposes the map legend, attribution and the panel below on phones. Existing floating navigation/skip-link are hidden **only by the screenshot capture style** in these viewport images; application navigation remains unchanged. Whole-workspace direction captures below retain the normal rendered component.

| Width | Browse | Computed route |
|---|---|---|
|320px|[Browse](320-browse.png)|[Route](320-route.png)|
|360px|[Browse](360-browse.png)|[Route](360-route.png)|
|390px|[Browse](390-browse.png)|[Route](390-route.png)|
|768px|[Browse](768-browse.png)|[Route](768-route.png)|
|1440px|[Browse](1440-browse.png)|[Route](1440-route.png)|

Selected-place details/focus: [390px](390-selected.png), [1440px](1440-selected.png). Desktop card is right-aligned to leave zoom controls clear; mobile card/panel stay in ordinary document flow. Full workspace with independent text directions and collapsed route fields: [360px](360-full-route-directions.png), [1440px](1440-full-route-directions.png).

## MUJ source-response simulation

[Desktop context](desktop-chromium-source-context.png) · [Mobile context](mobile-chromium-source-context.png).

These two complete map-panel captures include geometry, legend and attribution (rather than a mobile viewport cropped to controls). They use **read-only intercepted public responses** populated from committed original `data/muj/` source preparation, with the application name and attribution explicitly labelled simulated release/source visual fixture. They exercise source footprint/path context and unresolved E05 (`Mapped entrance10828149259`) without inventing geometry or identities. They are **not** the owner's corrected/E22-renamed Windows publication, an actual MUJ cloud database/release, a MUJ route calculation, field evidence or accessibility verification. No cloud dataset was published for these images.

The full built regression passed 99 cases with one deliberate duplicate viewport-sweep skip. After the final desktop card-position correction, affected built checks passed 23 cases with the same skip, including the explicit non-overlap assertion and five-width axe/overflow checks. The viewport-space test simulates keyboard pressure; actual Windows/phone/on-screen keyboard, real GPS and human assistive-technology verification remain outstanding. See [verification](../../testing/verification.md) and [Windows update/manual checks](../../operations/map-explorer.md).
