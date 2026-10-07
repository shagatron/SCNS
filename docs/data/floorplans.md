# Floorplan v1 data and coordinate contract

3A adds floors and display/calibration layers, not indoor navigation topology. The master specification remains the source of truth. These contracts implement its first indoor slice; 3B now adds [same-floor room/corridor tracing](indoor-editor.md); connectors and indoor routes remain 3C.

## Identity, ownership and storage

`floors` and `floorplan_layers` use `(dataset_revision_id, logical UUID)` keys and the same campus/revision composite integrity and draft/review/frozen mutation guards as the catalog/graph. Building, frame, floor, layer and source references are same-revision foreign keys. The current-layer triple FK also binds the selected layer to that exact floor. Floor IDs survive cloning; changing an ID/building is refused. Codes are unique per draft building. `ordering` is a finite floor ordering value (negative for basement, zero ground), not height; optional finite `elevation_m=NULL` remains unknown.

A selected layer retains private sanitized PNG bytes/hash, selected 1-based page, original normalized reference width/height, smaller display width/height and private processing/mask metadata. Original bytes/checksum/filename/media/rights/provenance/uploader live in `source_assets` after apply and in the durable `floorplan_jobs` batch. Sanitized PNGs never carry EXIF/GPS/ICC/text metadata. Protected DB BYTEA is deliberately reused rather than creating a static file mount. Database backup is required; legacy text import originals remain in their existing private volume.

Jobs bind campus/revision/target floor/uploader, idempotency key/fingerprint, original bytes/options and history. The target floor ID is historical rather than a cascading FK, so explicit draft floor deletion preserves the original/history. Job originals/options/identity cannot be rewritten or deleted; applied jobs are entirely immutable. Pre-apply state, lease and generated output are worker-controlled. Cloning copies selected and retained layers, source bytes and frames; it does not clone job history. Quotas include copies, preventing unlimited draft amplification.

## Reference pixels versus display pixels

The reference domain is `[0,width_px] × [0,height_px]`, with origin top left, **x right, y down**, units **pixels**. PNG/JPEG reference dimensions are the decoded, EXIF-normalized image. PDF reference dimensions are the selected rendered page at **150 DPI** (ceiling point-size × 150/72), including page rotation; DPI is only a reproducible rasterization convention, never an asserted architectural scale. Oversized pages reject instead of silently changing reference DPI.

A fresh display PNG is resized to at most 2,048 px/side but mapped to the **full reference** bounds. UI clicks/measurements and masks use reference pixels, never CSS/screen/thumbnail pixels. Leaflet uses a separate `CRS.Simple` instance and one adapter:

```
reference (x, y) → Leaflet [height_px - y, x]
Leaflet [lat, lng] → reference (lng, height_px - lat)
```

The inverse rejects non-finite/out-of-bounds points. Example: `(100,100)` on a 600×400 reference maps to `[300,100]`; a fitted/zoomed 2,048px display still uses the original reference domain. Pan/zoom does not change stored coordinates. Outdoor GeoJSON remains `[longitude,latitude]` in EPSG:4326 with its existing outdoor adapter and PostGIS geodesic metres. Pixels are never inserted into WGS84 GeoJSON or subtracted across floors.

## Metric calibration

Only `uniform_scale` on an undistorted/rectified plan is supported. A known measured line establishes:

```
metres_per_pixel = primary.distance_m / hypot(end.x-start.x, end.y-start.y)
local length_m = sum(hypot(dx_px,dy_px)) × metres_per_pixel
```

The second expression is a coordinate foundation, not a delivered indoor route calculation. Scale alone is insufficient to support indoor navigation without later traced topology/connectors. Uncalibrated scale is NULL, never zero or a fabricated default.

Primary and check lines must be inside reference bounds and at least 10 px long. Known distances are 0.1–10,000 m; uncertainty is finite 0–5 m and below 10% of the primary distance. At least one independent check must be nonparallel (`abs(cross)/(lengths) >= 0.2`). Every check's absolute mismatch under the primary scale must be within `max(2% of its known distance, stated uncertainty)`. Contradictory lines are rejected, never averaged. Degenerate/outside/parallel-only/future-dated and declared distorted/perspective/stretched inputs reject. Measurement date uses the campus IANA timezone both at save and authoritative validation. Arbitrary affine/perspective fitting is outside this slice; rectify with authorized source evidence first.

Stored evidence includes endpoints/known metres/checks, method, plan-quality declaration, measurement date, substantive private evidence, uncertainty, scale/tolerance/max error, measured-by identity, independent reviewer/date and selected PNG checksum. Demo results have `synthetic_calibrated` quality, not surveyed status; other accepted evidence is `measured_uniform`, still an administrative claim requiring independent review/field verification. An author cannot approve their own measurements. Selected-page replacement clears calibration and approval; later measurement edits clear calibration approval and invalidate exact-version review. No automatic scale migration across plans. Existing node dependencies require explicit later migration, so replacement/recalibration refuses them.

## Private API and public immutable projection

All private paths share `/api/v1/admin/campuses/{campus}/drafts/{revision}`. CRUD `/floors`, calibration `/floors/{floor}/calibration` and independent `/calibration/approve`; durable `/floorplan-jobs` upload/list/history, `/{job}/{original|preview}`, `/control/{retry|cancel}`, `/pages` and explicit `/apply`; layer preview `/floorplan-layers/{layer}/preview`. Unsafe calls use the existing cookie session, Origin, `X-CSRF-Token`, current `If-Match`; upload sends raw `application/octet-stream` plus URI-encoded strict JSON `X-Floorplan-Metadata` (see templates). Header-only metadata is not a filename/path authorization mechanism. All private responses are `no-store`; anonymous/foreign-campus assets are refused.

Whole-draft checksum includes floor/frame/layer/source references and processing/measurement evidence, with binary content represented by verified checksums. Submission locks those entities and binds exact content/version; frozen historical rows/PNG bytes cannot change. Existing release hashes/artifacts are not rewritten by the schema upgrade. New reviewed artifacts add explicit dictionaries `floors` and `floorplans`, only for visible floors in public buildings with a current independently approved permitted derivative. Retained unselected history is excluded and does not require approval to release the current plan. Restricted original bytes/notes/mask rectangles/uploader/reviewer/measurement evidence are never projected. Private calibration evidence is replaced by dimensions/scale/status/uncertainty; all floors explicitly set `navigation_mode="display_only"` and `metric_navigation=false`, even if calibrated. Public uncalibrated floors require an explicit warning acknowledgement; floors lacking an eligible plan block publication unless restricted. Live selected-source/calibration/overall reviewer grants are rechecked before publication.

From a public release descriptor and its approved layer hash construct:

```
GET /api/v1/campuses/{campus}/releases/{release}/floorplans/{layer}/{sha256}.png
```

This anonymous asset endpoint resolves only the immutable approved release artifact and frozen stored layer, validates campus/layer/hash/bytes, returns PNG with `ETag`, `nosniff` and `public,max-age=31536000,immutable`. Wrong hash/campus/draft/unapproved layer returns 404. Original filenames are never public asset routes. Publication rollback restores the earlier active pointer while historical approved PNGs remain retrievable. No public floor picker or indoor route UI is claimed in 3A; the responsive admin viewer and immutable asset contract establish the later indoor foundations.
