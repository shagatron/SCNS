# MUJ preparation v2 — covered source segments, unpublished

© OpenStreetMap contributors; derivative database under ODbL1.0, https://www.openstreetmap.org/copyright . Source SHA256d4b902b01fe944acb3161026679dabbab4898d6952bee22d7019f15fd15748de, unchanged from v1. No contributor identity attributes. No official MUJ/accessibility/physical route approval.

**Do not upload these full bundles over an existing v1 draft or rerun the old setup helper.** v1 under`data/muj/` and its receipts remain unchanged. Use the secure versioned update helper and review its exact before/after/CAS preview: docs/operations/muj-connectivity-review.md. It applies22graph changes atomically through the normal protected editor, including explicit removal of two replaced edges. There is no automatic source approval or publication.

Policy: retain maximal runs of original consecutive node pairs only when each full pair is covered by the exact two campus polygons. No clipped/interpolated boundary nodes, proximity merges or outside/gap access. All v1 indoor/grade/access/direction/accessibility guards remain. Existing source shared nodes establish junctions, including the newly retained Hostel Road junction10783309690, which requires splitting its incident GHS Hostel Main Road1154145951 segment.

After on an otherwise unchanged v1:51buildings/55places/295nodes/700directed edges/22anchors/29weak components/33unanchored. Delta:5nodes,14edges,1anchor added;2old edges deleted/replaced; no common record updates. ExistingC2/C17 join; a separate source-supported inside run is also retained, so the weak component total remains29. Explicit entrance10828149259 can now anchor its already catalogued place; no building/library centroid becomes a door. Accessibility unknown; distances estimated from stored geometry.

Regenerate separately, never into v1:

```bash
cd backend
UV_CACHE_DIR=/tmp/scns-uv-cache uv run --frozen python -m app.cli.osm ../data/raw/muj/source.osm --covered-segments-v2 --output ../data/muj-v2
```

Original/private source remains ignored; manifest pins every generated bundle, campus/options/report/coverage file. README is human guidance outside that pin. Versioned diagnostics/maps under docs/data/muj-connectivity-v2 supplement preserved v1 diagrams; full findings and evidence collection: docs/data/muj-connectivity-review.md.
