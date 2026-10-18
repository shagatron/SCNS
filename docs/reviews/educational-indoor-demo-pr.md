Add a separate original two-floor educational indoor demonstration linked from the existing MUJ introduction. The page prominently states “Demonstration layout — not an actual MUJ floorplan.” It offers room selection, computed same-floor/cross-floor/reverse directions, floor-section controls and stair instructions, map-independent text, reload recovery and deliberate disconnected-room handling.

The read-only educational API reuses the production pure Dijkstra engine over an authored graph with unit traversal costs. It makes no database writes, uses no campus draft/release or fake source/accessibility approvals, and returns unknown distance/ETA/scale. Original SVGs are not copied from the reference drawings. Existing public/admin data, algorithms, policies and workflows remain; native-Windows work is excluded.

Validation:276backend units;75frontend tests plus lint/type/build;33PostGIS/API cases with source-OSM MUJ metric/traversal baselines unchanged;72source desktop/mobile journeys plus14finalaffected;44built nginx/API/worker journeys and readiness/private boundaries. Retained22-table/.env/private-storage digests match. Ten decoded/checksummed PNGs and Windows Docker/presentation instructions are committed.

Actual Windows/physical device/real MUJ database checks remain owner-run. MUJ-entry browser metadata is explicitly simulated over isolated synthetic release data. The original public route-button150ms transition contrast gap remains disclosed; its full axe assertion now waits for an enabled, settled control. No merge, public deployment, schema change, reseeding, real-campus edit or publication.

Base: polish/muj-homepage at ee683e1a61a6584147c3e39b121a8765db5e46ba.
Head: feat/muj-indoor-demo.
