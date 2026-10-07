# Campus data preparation

`demo/campus.json` is original synthetic data near longitude/latitude zero. Never rename it to pretend it is a real institution. `scripts/generate_demo.py` reproducibly generates 3 buildings, 11 places (10 public), 13 nodes, 27 directed edges and 11 anchors. Distances are measured by PostGIS when imported, not hand-assigned. The normal demo deliberately contains an isolated garden and a help desk with no entrance.

Put authorized owner files in these **ignored, private** directories:

| Directory | Intended input |
|---|---|
| `raw/campus-overview/` | Approved campus overview and boundary |
| `raw/floorplans/<building>/<floor>/` | Original plans with source rights |
| `raw/room-directories/` | Official building/room/department lists |
| `raw/surveys/` | Measured entrances, paths and accessibility evidence |
| `staging/` | Temporary conversion/validation output |
| `exports/` | Reviewed exports; ignored by default |
| `../storage/uploads/` | Future authenticated private upload storage |
| `../storage/derived/` | Future reviewed derivatives, not automatically public |

Do not put source plans, credentials, personal records or unreviewed derivatives in `frontend/public` or commit them. Directory presence is preparation space. M2B1 text imports and M3A private PDF/image floorplan jobs are implemented; use their authenticated workflows rather than a static file directory.

## Executable outdoor JSON v1

`templates/dataset-v1.schema.json` is generated from the actual Pydantic validator. `templates/outdoor-bundle.example.json` is a valid empty synthetic bundle; `demo/campus.json` is the complete runnable example. `id` fields are stable UUIDs, not names; the bundle's single campus scopes all entities. Formats have explicit `schema_version`, units, timezone, source rights, provenance and frames. Unknown properties are rejected. JSON files are limited to 10 MiB.

```bash
make validate-dataset DATASET=/absolute/path/to/bundle.json
# No import or publication occurs during validation.
```

The validator checks IDs/codes, duplicate anchors, references, visibility relationships, frame consistency, positive path topology, endpoint direction, geometry coordinate ranges and closed polygon rings. PostGIS checks and measures persisted geometry during synthetic seeding. This is structural validation, not proof of field correctness or source permission. Unknown outdoor distances are computed along approved input geometry instead of becoming zero. Reversed geometry requires a separate reversed directed edge.

`make seed-demo DATASET=/absolute/path/to/edited-demo.json` is only for explicitly synthetic local data. Each changed bundle creates a frozen revision and release; unchanged bundles are idempotent. Authorized real outdoor/catalog imports use the completed M2 staged preview, independent review and publication workflow; routine updates never reseed existing data.

## CSV / GeoJSON preparation templates

The header-only CSVs cover campuses, buildings, floors, frames, places, aliases, departments, department links, anchors, nodes, edges, connectors, calibration measurements, opening rules, QR inventory and provenance. They are **preparation templates for later import milestones**, not current CSV upload endpoints. Use stable external IDs consistently across related files; the later importer will map them to UUIDs. Use standard CSV quoting for commas or JSON. Empty cells mean unknown, never invented zeros or accessibility approval.

Geometry must accompany scalar edge rows: `edge-geometries.geojson` is an empty FeatureCollection. Each feature will use the matching edge `external_id` as `id`, a `LineString` in `[longitude,latitude]` order, and properties `campus_code` and `coordinate_frame`. Shape points must include bends and directed endpoints. Use a reversed feature for a reversed edge. Indoor polylines belong in `indoor-polylines.json`, keyed by edge external ID and local frame, with pixel coordinates. Do not put pixels into GeoJSON WGS84 coordinates.

## Owner upload checklist

1. Obtain the permitted publication audience and rights to use each source; record provenance/checksum/restrictions in `provenance.csv`.
2. Supply the real campus name/code, IANA timezone, surveyed boundary, official buildings and names.
3. Record actual entrance/door anchors, connected paths, one-way rules and restricted areas. Crossings alone do not establish connections.
4. Measure widths, slopes, steps, surfaces and scale with date/reviewer evidence; leave accessibility unknown until verified.
5. For each floor preserve image dimensions, origin/orientation and calibration line endpoints plus surveyed metres. Never infer metres across distinct floors.
6. Keep source originals private. Select/redact permitted derivative images before publication.
7. Import into a **new real campus draft**, preview diagnostics, validate and obtain review. Do not overwrite Demo Campus.
8. Physically walk the pilot routes before declaring them usable. Official maps and those approvals remain external dependencies.

Executable 2B1 staged CSV/JSON/GeoJSON examples are in [`templates/import-v1/`](templates/import-v1/README.md). Root floor/calibration CSV templates remain preparation-only; executable manual 3A floor/upload/calibration JSON is in [`templates/floorplan-v1/`](templates/floorplan-v1/README.md). Connectors/QR remain future preparation. See [private draft import rules and startup](../docs/operations/imports.md).

M3A fixture PNG/JPEG/two-page PDF: [`demo/floorplans/`](demo/floorplans/README.md), explicitly synthetic 600×400 drawings with independent known 200px/10m lines. Real originals remain ignored/private and require their own rights/measurement evidence. Floorplans use protected database BYTEA rather than the text-import filesystem; no original is a public static asset. [Complete workflow/limits](../docs/operations/floorplans.md) and [coordinate/release contract](../docs/data/floorplans.md).
