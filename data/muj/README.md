# MUJ OSM derivative preparation — unpublished

© OpenStreetMap contributors. Database source and these derivative data files:
[Open Database License1.0](https://opendatacommons.org/licenses/odbl/1-0/).
[OSM copyright/attribution](https://www.openstreetmap.org/copyright).

Not official MUJ data, a field survey, a verified accessible map or a published campus release.

- `manifest.json`: pinned source and exact derivative file checksums.
- `campus.json`: additive MUJ setup metadata; extent is the display hull, not ownership.
- `coverage.geojson`: the two exact university polygons, no inferred bridge between them.
- `report.json`: eligible records' source IDs/tags, excluded/surrounding features, missing members, indoor quarantine, components, unanchored destinations and reasons.
- `options.json` and `batch-001..003.json`: current import-v1 create-only batches400/400/249rows. Dependencies precede dependents across batches.

Original XML is private/ignored, not in Git or images. Contributor usernames and UIDs are absent from these derivatives. No floorplans/rooms/QRs/accessibility verification are transplanted from synthetic data. Never use a seed command to apply these files.

Use [Windows staged setup/import](../../docs/operations/muj-osm.md), [complete source/scope/reproduction/licensing](../../docs/data/muj-osm.md), and [actual verification evidence](../../docs/testing/verification.md). Independent source and exact-content review/publication remain explicit. Do not automatically acknowledge warnings or publish a partial import.
