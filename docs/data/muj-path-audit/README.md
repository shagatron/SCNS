# Complete MUJ outdoor source-path audit

17 October 2026. This follow-up starts from the completed map-preservation correction8798fa3. **No additional unambiguous connectivity correction was found under the retained conservative policy. No graph patch, updater apply action or empty draft is created.** The existing v2 correction must not be replayed. The supplied Google screenshots were orientation only: no OCR, names, pixels, highlighted lines or coordinates were copied.

## Evidence and coverage

- [All1,619consecutive source pairs, CSV](segments.csv), [complete JSON](segments.json): original way, occurrence index, endpoint IDs/positions, all sanitized way/endpoint tags, coverage, exact directed stored-edge references, exclusion/assessment reasons, components, component destinations, direct anchors and raw building-interior overlap context. Original OSM IDs are administrative provenance, not guessed identities. A segment is an **original consecutive node pair**, not necessarily a stored edge; full stored polylines span several pairs.
- [Numbered overview](overview.svg), [academic detail](academic.svg), [hostel/boundary detail](hostel-crossing.svg), [cricket/sports detail](cricket.svg), [near-pair detail](near-pairs.svg).
- [Nine deduplicated owner/source questions](questions.md), [machine-readable questions](questions.json). Numbers match maps; C1–C29 are diagnostic components, not new database IDs.
- [Computed route matrix](routes.json):2,024ordered destination/profile/objective cases plus3,248ordered node-representative/profile/objective cases across all29weak components. The latter include components without destination anchors and are diagnostics, not public arrival claims. Actual application mixed/Dijkstra functions use stored PostGIS full-polyline lengths in an isolated fixture. No hardcoded route answers or substitute Windows publication.
- [Windows actual-release read-only preflight and update](../../operations/muj-path-connectivity.md). Fetches the **actual current** published release/artifact, including the E22 clone, without assuming the original publication UUID.

Green is the existing retained graph, red dashed geometry is excluded/review **original source geometry**, gray outlines/names are source context. There are **no proposed additions**. Building/room/sports outlines do not establish doors, paths, floors or identities. North up; approximate geographic display scaling, not survey measurements. Detail SVGs are zoomable and source IDs/reasons are available in line titles and the inventory. Map numbers can be outside a particular detail crop; use the overview/table. No external basemap or Google content is embedded. © OpenStreetMap contributors / ODbL1.0.

Original:819,138bytes, SHA256`d4b902b01fe944acb3161026679dabbab4898d6952bee22d7019f15fd15748de`. The ignored source file was absent at task start; the existing earlier uploaded export was recovered privately, mode0600, and matched exactly. No new upload or source substitution. All seven manifest-listed files in **each** `data/muj/` and `data/muj-v2/` were checksummed, and both conversions reproduced their original bundle bytes before auditing. Originals/contributor metadata stay private; neither pinned preparation nor old receipts are rewritten. Manifest hashes are in segments.json.

## Findings

All243highway ways are accounted for, including outside-coverage segments for context:1,619pairs,765fully covered,775touching coverage.590pairs are represented;1,029excluded/review pairs comprise854not fully covered and175fully covered pairs blocked by way/node access, corridor, grade/level or supported-type policy. Reasons overlap and must not be summed as separate segment totals. Every unrepresented pair has a specific source/coverage reason; no unexplained omission remains. All fully covered unsupported-highway pairs are elevator geometry, not omitted campus walking roads. All178shared references between retained source ways are stored junctions. Full ordered-reference hashes and exact geometry are checked for each of700directed stored edges; curves are never replaced with endpoint chords. The original source has two general vehicle one-way tags and no pedestrian-specific one-way tags: vehicle direction is **not** imposed on walkers. `oneway:foot`, explicit foot permissions/denials, barriers, conditional access and grade cases are covered by deterministic fixture tests.

| Measure | Original v1 (historical) | Already applied v2 + E22 | Proposed after this audit |
|---|---:|---:|---:|
|Represented original pairs|567|590|590|
|Nodes / directed stored edges|290 /688|295 /700|295 /700|
|Entrance anchors / unanchored catalog destinations|21 /34|22 /33|22 /33|
|Weak components|29|29|29|
|Buildings / places|51 /55|51 /55|51 /55|

The v1→v2 difference is prior work:23additional covered pairs,5nodes/14directed additions/1anchor,2superseded edge deletions,22operations total. It already split original geometry at10783309690 and connected the earlier hostel components while retaining a separate covered run. **This audit adds zero records and repeats none of those operations.**25explicit entrance-tagged source nodes fall inside coverage:22already anchored;10733816254depends on the unresolved subway approach/grade policy,10778271605is explicitly private,11594245196has level2. No additional source-supported ground entrance anchor was missed.

The earlier subway finding is unchanged: a complete raw shared-node chain exists, but private access at10778271605, `tunnel:name=Subway` on1154145270, nonzero-layer stairs/tunnel1154145273/1246099090/1154145269 and the polygon-union road gap remain unresolved. A tunnel name alone does not establish extent; dropping a layer guard alone would not fix access/coverage. The export contains **no new evidence** resolving these limitations. General tertiary road segments1245026708/1245026709 do not justify opening the academic–hostel gap. Geometric crossings, near nodes and screenshot highlights do not establish a permitted join.

C6/C8/C16still have no excluded highway sharing their retained source nodes. C12and other isolated stair/academic components retain their exact-ID inventories. A path may exist physically, but missing source topology is not a converter omission. Library node12585506492is a display destination, not an arrival entrance; screenshot “Knowledge Centre” wording was not equated with it. E22 remains **TMA Pai Auditorium entrance**; E05 / Mapped entrance10828149259, E02 and all unresolved names remain unchanged.

**Additional explicit caution:**49source pairs intersect interiors of raw building-tagged outlines;27of those are already retained, across15ways. These are overlap diagnostics, not newly authorized passages or proof of a converter defect. Some hostel outlines carry layer1; academic room outlines can describe upper floors over ground paths. Others lack sufficient level/access evidence. The inventory exposes the exact outline/path tags and reference membership rather than treating a footprint intersection or proximity as a connection. Questions4/7/9group the relevant ambiguities. No new path through a building, centroid-to-road anchor, inter-floor connection, physical-separation assertion or access fact is added. Existing overlaps need source/campus assessment before any separately justified correction; this audit does not certify existing paths or clear publication warnings.

## Computed comparison, not fresh Windows evidence

| Journey | Objective/profile | Isolated source/PostGIS result | New graph change |
|---|---|---:|---|
|Hostel Entrance → GHS Entrance|Metric shortest|23.62m /3edges|None|
|Hostel Entrance → Faculty Block Entrance|Metric shortest|163.28m /6edges|None|
|University Entrance → Mapped entrance10828149259|Metric shortest|513.10m /13edges|None|
|University Entrance → Mapped entrance10828149259|Fewest eligible traversals, Directions only|799.32m /9edges|None|
|Hostel Entrance → Central Library|Either standard objective|No eligible arrival anchor|None|
|University Entrance → Hostel Entrance|Either standard objective|No eligible route|None|
|Any distinct entrance pair|Verified step-free, either objective|No verified route; accessibility stays unknown|None|
|Demo Main Gate → Library|Metric shortest|Existing API regression approximately256.88m /3edges|None|

Of506ordered distinct pairs among23selected destinations (all22anchored entrances plus Library),30are reachable under each standard objective;476are not. All506step-free cases fail under each objective. All812ordered pairs of different weak-component representatives fail for each of two profiles/two objectives (3,248cases). This evidence separates lack of anchors from disconnected topology; it does not infer physical isolation. Before/after matrices are the **same** because there is no patch; a second fabricated dataset is unnecessary.

The prior owner-reported Windows baselines (23.62m/3,163.28m/6,513.10m/13,approximately799m/9and Demo256.88m/3) remain comparison inputs, not newly inspected Windows results. Public matrix output rounds physical distance to2decimals; original stored unrounded distances remain authoritative. Estimated mapping lengths are not surveyed merely because an existing policy is labelled Verified. No real-device GPS, physical route, accessibility, independent human or institutional approval is claimed.

## Reproduce without changing data

From `backend`, with the exact private original retained at the existing ignored path:

```bash
UV_CACHE_DIR=/tmp/scns-uv-cache uv run --frozen python -m app.cli.muj_paths audit --source ../data/raw/muj/source.osm --output /tmp/muj-path-audit
```

Compare generated segments.json/CSV, questions and five SVGs with this directory; only README/routes/manifest are separate explanatory/verification artifacts. Output may never be the original, either preparation, their ancestors or children. The CLI verifies v1 and v2, refuses unsafe XML/checksum changes and unexplained pairs, and never connects to a database. To regenerate routes using normal API/data safeguards in a **dedicated rollback-only PostGIS test database**, run the affected integration test with `SCNS_PATH_EVIDENCE=/tmp/muj-routes.json`; see verification. Never point tests at your retained Windows or developer database. Actual Windows preflight is separate and read-only.

[Artifact sizes/SHA256 manifest](manifest.json) covers the machine inventories, route matrix, SVGs and five decoded1140×810PNG browser renders. PNG alternatives: [overview](overview.png), [academic](academic.png), [hostel/crossing](hostel-crossing.png), [cricket](cricket.png), [near-pairs](near-pairs.png). These are source-only diagnostic figures, not Google screenshots or actual Windows UI captures. CSV uses explicit LF and machine artifacts have pinned LF Git attributes for Windows autocrlf reproducibility.
