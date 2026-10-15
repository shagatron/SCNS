# MUJ OpenStreetMap preparation

This is a real **OpenStreetMap-derived preparation**, not official Manipal University Jaipur data, a complete map, or a field survey. It is separate from Demo Campus. The supplied screenshots provide context only; no paths, rooms or entrances were traced from them. No MUJ release is published by this workflow.

## Source and reproducibility

Owner-supplied `map (1).osm`: **819,138 bytes**, SHA-256 `d4b902b01fe944acb3161026679dabbab4898d6952bee22d7019f15fd15748de`. Original retained in ignored `data/raw/muj/source.osm` in the cloud checkout. It is deliberately excluded from Git/images because it contains unnecessary contributor account metadata. Keep the downloaded original for first Windows setup; that helper verifies the checksum and retains an exact mode0600 copy under the existing private storage volume, `private/muj/<sha256>.osm`. It never serves that directory. No cloud copy changes the Windows database.

Repository attributes pin JSON/GeoJSON line endings to LF, including Windows automatic-CRLF checkouts. Committed `data/muj/` contains only reproducible derivative import-v1 JSON, geographic coverage, a detailed preparation report, options and checksummed manifest. Contributor usernames/UIDs/changesets are omitted from derivatives; useful feature IDs/tags remain in the preparation report and import evidence. JSON values are data, never code. No OSM URLs are fetched during conversion/import.

From the repository root, with the downloaded original copied to the ignored source path:

```bash
cd backend
UV_CACHE_DIR=/tmp/scns-uv-cache uv sync --frozen
UV_CACHE_DIR=/tmp/scns-uv-cache uv run --frozen python -m app.cli.osm ../data/raw/muj/source.osm --output ../data/muj
cd ..
git diff --exit-code -- data/muj
```

`app.cli.osm` is offline and never opens a database. Input is bounded to5MiB/100,000elements, XML DTD/entities refused; current source is well below those bounds. Robust Shapely validity/coverage/holes are used without make-valid, buffering, simplification, snapping or invented geography. Bad features are reported/quarantined; invalid/missing required university polygons stop conversion. Use a separate output directory when investigating a different export. Setup pins both source and preparation checksums and refuses silently replacing an existing MUJ campus with changed preparation.

External identities: `osm-node-ID`, `osm-way-ID`, `osm-relation-ID-part-N`; directed segments include their source way and original endpoint node IDs plus forward/reverse. Relation parts are sorted deterministically by geometry; existing v1 is pinned, so a changed source/conversion requires explicit new preparation review, not blind in-place upsert. Logical UUIDs use the existing import-v1 campus/entity/external-ID convention. Separate entities can reference the same OSM element without confusing buildings, places and nodes. Create-only policy is deliberate: identical content is unchanged; different existing content conflicts rather than overwriting an editor/survey. Job identity binds exact draft+batch checksum and existing uploader; committed replay does not increment versions/audits. Original actor must resume; changing uploader is a separately audited attempt, not permission to replace data.

## Coverage and counts

Raw export: **3,193 nodes,517 ways,9 relations;167 building-tagged ways,243 highway-tagged ways,20 indoor=room ways** (22ways have any indoor tag). These are raw counts, not eligible campus records.

- University way[495716022](https://www.openstreetmap.org/way/495716022) is the eastern **academic campus**. Extent `[75.5621716,26.8388434,75.5682706,26.8469982]`.
- University way[1158554635](https://www.openstreetmap.org/way/1158554635) is the western **hostel campus**. Extent `[75.5593205,26.8383207,75.5647705,26.8463506]`.
- They are disjoint, with an intervening road corridor. Exact polygon union, including holes, controls feature eligibility. Both original polygons are retained in `coverage.geojson` as an **unapproved** source display derivative.
- SCNS currently supports one Polygon campus extent. Its enclosing convex hull is used only as the operational display/validation extent, **not an ownership boundary**. About17.06% of the hull lies outside the two mapped polygons. Surrounding/gap features do not become eligible through the hull. The rectangular export bounds are unused. GPS operation remains gated by the actual eligible published paths/anchors if a future reviewed release is created; this extent is not a property/access claim.
- Subway/grade-separated and ambiguous multi-level geometry is not flattened into a connection. The prepared graph therefore has no justified academic↔hostel connection. Mapping and review must resolve it; do not draw a straight shortcut across the road.

| Included derivative | Count |
| --- | ---: |
| Outdoor WGS84 frame | 1 |
| Building footprint records | 51 |
| Named destinations and explicitly labelled mapped entrances | 55 |
| Outdoor graph nodes | 283 |
| Directed stored edges | 638 |
| Mapped entrance anchors | 21 |
| Source highway ways represented by at least one accepted segment | 154 |
| Weak graph components | 35 |
| Anchored entrance destinations | 21 |
| Unanchored destinations | 34 |

Three coherent import bundles contain **400,400,249 records**, below the existing2,000row/5MiB defaults. Dependencies precede dependents across bundles; each batch is transactional, the entire three-batch preparation is resumable rather than globally atomic. Do not publish a partial draft. Distances are computed from full polylines by PostGIS geography on application, `estimated`, never claimed surveyed. Accessibility stays unknown except mapped steps explicitly not-step-free. `wheelchair=yes` does not create verified accessibility.

`report.json` enumerates all exclusions with OSM IDs and tags, missing relation members, surrounding features, quarantined indoor features, full included provenance, component examples and named anchored/unanchored destinations. Major decisions:

| Exclusion/diagnostic | Count |
| --- | ---: |
| Room/level-tagged or numeric room-like building ways quarantined | 88 |
| Building ways outside exact coverage | 30 |
| Highway ways outside exact coverage/cross-campus gap | 56 |
| Unsupported level/layer highway ways | 17 |
| Indoor/corridor highway ways | 5 |
| Additional grade-separated path | 1 |
| Unsupported highway types | 5 |
| Invalid/non-simple path geometry | 3 |
| Blocked/level-tagged node segments | 2 |
| Indoor catalog preparation-only ways | 20 |
| Bus relations excluded | 2 |
| Non-building/indoor multipolygon relations | 2 |
| Outside-coverage multipolygon | 1 |
| Other unsupported relations | 2 |

Anchor presence is not a guarantee of reachability from a chosen start. The21anchors span15components: only10destinations have another anchored destination in the same component;11anchored destinations have no other anchored destination in their component. The other34places have no anchor at all. `report.json` distinguishes these counts rather than calling all21globally routable. The inspected Hostel Entrance component contains GHS Entrance, but not University Entrance or Faculty Block Entrance. No proximity connection is added to improve these counts.

These are decisions at different pipeline stages, not additive percentages of all517ways. Rejected relation members never fall back to filled independent building polygons. Complete multipolygon rings are assembled without snapping; holes remain holes; multiple valid outer components become separate identified footprint records. Unsupported/missing rings and duplicate identities are diagnosed, not repaired. Incomplete external bus relations have no walking/topology role. Indoor catalog preparation retains **106 node/way source descriptors** with room/level/indoor tags; no floors, floorplans, calibration, lifts, room completeness or cross-floor links are invented.

Named included examples: Central Library (OSM node12585506492), Academic Block -3, Lecture Hall Complex (LHC), Administrative Block, B1/B2/B3/B6 and G1–G4 hostel buildings, University Entrance and Hostel Entrance. Library's display point is not an entrance. All building representative points are for catalog display only. Only an entrance-tagged OSM node that is already part of accepted outdoor topology receives an anchor; no centroid/proximity/crossing connection is invented. Buildings remain unanchored until evidence ties a mapped entrance to the destination.

## Attribution and publication prerequisites

**© OpenStreetMap contributors.** Source/derivative database: [Open Database License1.0](https://opendatacommons.org/licenses/odbl/1-0/), [OSM copyright](https://www.openstreetmap.org/copyright). This data licensing is separate from application source-code licensing. Keep notices/provenance when copying the prepared data. Public use of an adapted OSM database requires ODbL compliance, attribution and applicable share-alike/availability obligations; publishing only rendered maps does not eliminate obligations on the adapted database used publicly. Do not relabel this as institutional map ownership or a physical accessibility audit.

Authoritative guidance: [OSMF attribution guidelines](https://osmfoundation.org/wiki/Licence/Attribution_Guidelines), [OSMF produced-work guideline](https://osmfoundation.org/wiki/Licence/Community_Guidelines/Produced_Work_-_Guideline). OSM's official website copyright wording was checked from its [maintained English source](https://github.com/openstreetmap/openstreetmap-website/blob/master/config/locales/en.yml) on15October2026; direct copyright/wiki HTTP requests returned403 in this environment. No claim that the inaccessible pages were freshly read. No standard OSM tile caching/downloading/service was enabled.

Before public release: resolve graph errors and investigate each warning; define a legitimate limited audience/coverage, verify destination entrances/access restrictions and subway topology, retain visible OSM attribution and an appropriate ODbL derivative-data offer, obtain the campus owner's audience/institutional approval as needed, assign an **independent MUJ reviewer** through existing role administration, independently review/approve the exact source and its coverage derivative, validate route expectations, submit exact content, approve independently and explicitly publish through existing2C controls. No helper approves sources, acknowledges warnings, submits a review or publishes. Unknown accessibility is a real limitation, not a warning to waive into verification. Existing public Demo Campus stays unchanged.
