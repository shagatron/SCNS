# Executable staged import-v1 templates

**All samples are synthetic Demo Campus data near 0,0, for software testing only.** Replace campus code/timezone, names, coordinates, provenance and rights with authorized data before preparing real imports. Never relabel synthetic geometry as an official campus.

- `catalog-bundle.json`: all supported related entity types, applied together to one draft. Related CSV files contain matching external IDs. The standalone `places.csv` intentionally has no building dependency.
- `options.json`: example API/CLI metadata, rights, provenance and create-only policy. In the browser these values are entered in the upload form. For a CSV/GeoJSON CLI parse, change `format` and `entity` appropriately.
- `places.csv`: independently importable location with a quoted GeoJSON Point cell.
- `places.geojson`: independently importable RFC 7946 FeatureCollection.
- `frames.csv`, `buildings.csv`, `nodes.csv`, `edges.csv`, `departments.csv`, `department_places.csv`, `aliases.csv`, `anchors.csv`: typed per-entity examples. Dependent files require the referenced records already in the target draft, or their records together in a JSON bundle for one atomic application. Edge `geometry` is a quoted full LineString including every bend, not a scalar/chord approximation.

Use `external_id,campus_code` plus the typed fields. CSV headers must be unique; UTF-8, commas and standard double-quote escaping apply. References (`building_id`, `frame_id`, `place_id`, `node_id`, `department_id`, endpoints, `place_ids`) are stable external IDs or existing target-draft UUIDs; cross-campus/revision references fail. `physical_path_id` is a shared stable group for related directed segments. Arrays (`place_ids`) and geometries are JSON cells. Booleans are `true`/`false`.

Supported fields and defaults are in backend typed schemas and [the import guide](../../../docs/operations/imports.md). To adopt an existing admin-created record rather than conflict on its code, add an `existing_id` column/property with that record's draft UUID. Upsert is an explicit complete-field replacement. Repeated external IDs within one batch are invalid. A changed existing stable identity conflicts under create-only; review an explicit upsert preview before applying. No import deletes or publishes data.

Owner preparation checklist:

1. Confirm authorization, source rights, campus code/timezone, boundary and WGS84 coordinate order.
2. Assign stable external IDs once, preserve them in every export, resolve references across files.
3. Supply actual entrance/door nodes, directed full path polylines and evidence; do not claim surveyed accessibility from a drawing.
4. Parse with the offline CLI below. Then upload to a draft, inspect every diagnostic/conflict, and validate before application.
5. Public release review/publication is a later milestone; uploaded and applied draft data stays private.

```bash
cd backend
uv run --frozen python -m app.cli.imports validate \
  --file ../data/templates/import-v1/catalog-bundle.json \
  --options ../data/templates/import-v1/options.json
```

Floors, rooms, connectors, floorplan/calibration/QR and opening-rule root templates are preparation-only future milestones. This import slice accepts CSV/JSON/GeoJSON outdoor/catalog records, not image/PDF uploads or indoor pixels.
