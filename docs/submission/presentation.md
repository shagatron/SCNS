# Presentation-day checklist and exact demo inputs

This is the Docker academic application, not an institutional or physically verified navigation service. Prepare locally before assessment; no internet hosting/LAN changes, reseed or imports are required. [Safe main update/start](../operations/academic-submission.md).

## Before the professor arrives

1. Start/check the existing database, then API/worker/frontend. Confirm `http://localhost:5173/api/v1/health/ready` succeeds and the homepage opens. Keep Docker Desktop running. Preserve the phone override on disk but exclude it for laptop-only startup.
2. Check the campus selector contains your existing MUJ preview and Demo Campus. Git cannot recreate the owner's published database/private uploads. On a separate fresh database, use Demo Campus plus `/indoor-demo`; disclose that MUJ is absent rather than inventing/importing/publishing it for the demo.
3. Confirm supplied MUJ photo/logo, full directory/search/pagination/place actions and ordinary route controls are present. Keep known good public pages open as a fallback. Use actual running computation; static screenshots are supplementary, not computed live results.
4. Do not alter active restrictions/data to make an expected number pass. If a legitimate closure changes the route, disclose it and use the unaffected synthetic educational graph instead. No last-minute approval/publication/graph editing needed.

## Reliable live sequence

| Step / exact controls | Expected explanation/result |
|---|---|
| Demo Campus → Starting point **Main Gate**, Destination **Library**, Route preference **Shortest walking route**, Distance policy **Metric · stored path distances**, Find walking route | Approximately257m/4min,256.88m over3stored edges. Show highlighted stored polylines and ordered text. It is computed, not a straight line or hardcoded result. |
| Search directory for Library, open Place details; Route here / Start here; clear/search/filter/page | Full directory and original actions are retained. Destination/start focus moves to the normal planner; route calculation remains explicit. |
| MUJ → **University Entrance → Mapped entrance10828149259**(E05), shortest+metric | Owner-reported Windows / isolated-source fixture baseline513.10m/13edges(~513m), assuming unchanged published data and no new relevant restrictions. E05 remains unidentified; do not call it Library/main entrance. |
| Same MUJ pair, **Directions only · unknown distance allowed** and **Fewest eligible traversals** | About799m/9edges, not minimum metres. One cost unit per eligible traversal means9can beat13despite longer physical length. |
| MUJ → **Hostel Entrance → GHS Entrance**; then **Faculty Block Entrance**, metric |23.62m/3edges and163.28m/6edges respectively, subject to current restrictions. |
| MUJ → Explore ↗ → **Indoor demo** | Read **“Demonstration layout — not an actual MUJ floorplan.”** Same explorer area; independent fictional graph, no outdoor-to-demo connection. |
| Start **Demo Classroom A · Ground floor**, Destination **Demo Library · Ground floor** → Find demo directions |3authored traversals, highlighted ground-floor section; distance unknown/ETA unavailable. |
| A → **Demo Classroom C · First floor** |9traversals; explicit Demo Stairs ascent. Use **Show First floor** next to stair text or View demonstration floor. First-floor highlights continue to C. |
| Reverse **Demo Classroom C → Demo Classroom A** |9traversals; explicit stair descent and first-floor initial view. |
| A → A; A → **Demo Disconnected Room · Ground floor** |0traversals without invented physical distance; then contextual no-route and no remaining highlight. No connection is invented through a wall. |
| Recalculate A→C; hide demonstration map; show it; reload; switch Outdoor/Indoor demo | Text directions remain when hidden. Floor/route reload state recovers; mode choices/results/errors stay separate. Directory actions return to the original planner. |
| Keyboard mode tab focus → Left/Right or Home/End; Tab/Enter; floor selector; focus map and arrows/+/- | Selected-state tabs/focus; labelled controls; pan/zoom and Fit floor plan. Narrow phone fit requires zoom for small schematic labels; text selectors/directions stay full-size. |

## Optional existing features, with prerequisites

- **QR:** use only an existing installed valid marker/sign, explicit confirmation, and an eligible destination. Planned/revoked/stale markers must not route as installed starts; reassignment needs fresh installation evidence. Sign download/physical scanning/printing are **not owner-verified** in recorded evidence. Do not create/install markers for this audit.
- **GPS:** click **Use my location** explicitly; browser permission and a fresh accurate outdoor fix are required, followed by landmark confirmation. It is not tracking and cannot detect a floor/room. Classroom GPS may fail coverage/accuracy; use manual/QR fallback. Owner-reported Windows Chrome simulated±5m Gate→Library gave257m/4min;100m accuracy/outside/disconnected Garden/one-way East Exit were rejected. These were **simulated browser positions**, not real-device GPS evidence. Exact simulation setup: [geolocation guide](../operations/geolocation.md).
- **Closures:** point out restriction freshness/check control and honest unavailable status. Do not modify live retained restrictions for assessment; use existing state. Estimated end does not automatically reopen an edge/lift. Stale context must hide old results and require recalculation.
- **Published indoor floors:** the ordinary explorer's **Building and floor view** remains available for existing reviewed releases. This is separate from the unscaled educational demo; do not present the school's fictional rooms as MUJ records.

## Evidence and limitations to say aloud

“Dijkstra uses Python's heapq and an adjacency list, with relaxation, stale-entry skipping and predecessor reconstruction. Metric routes minimize eligible length, while Directions only minimizes eligible arc count. Floor transitions connect explicit graph nodes; no line is drawn between incompatible pixel frames.” See [verified source explanation](dsa.md).

The three MUJ metric routes and policy comparison are owner-reported Windows checks plus isolated original-source calculations, not physical surveys. Owner-operated separate application accounts performed source/submission/review/publication; no independent human/institutional approval is claimed. E22 **TMA Pai Auditorium entrance** is the owner-reported published label; E05 and other unresolved identities remain unchanged. Unsupported MUJ Library/cross-campus/verified-step-free routes must remain unavailable.

The integrated educational frontend was verified in cloud Linux Chromium/desktop/mobile emulation and built nginx/API/worker fixtures. Latest owner Windows indoor update, physical phone/human AT/live GPS/accessibility are still unverified unless the owner separately reports them. Educational distance/ETA/scale/accessibility remain unknown. The new E22 release UUID/artifact checksum were not supplied; do not invent them. [Detailed evidence](audit.md).
