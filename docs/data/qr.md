# QR inventory and routing contract — M4A

Authoritative master-spec sections6,11,13.2 and20. This operational table is separate from map revisions and binds only current published public graph nodes. No import, marker creation or activation publishes a draft. Public maps/search/artifacts continue to use the immutable active release; private source plans and installation notes never enter public marker resolution. All examples and fixtures remain synthetic.

## Identity, permissions and versioning

`qr_markers` (migration0015_qr) stores random UUID public ID, campus, creator, creation key, marker version, label, outdoor/indoor stored-node reference, current release binding, physical-target checksum, private intended position, installation/evidence and lifecycle state. URLs are never deleted: DELETE has no API and a SQL history guard. Creator/campus/key is unique; the same content/key retry returns one marker. Changed content under a reused key conflicts. Inventory cap2,000/campus; target selector cap5,000 with an explicit truncation notice.

Campus `operations` and `system_admin` can manage; `editor` and `reviewer_publisher` can inspect and download signs. Assignment is rechecked on every operation, with existing live session/CSRF/origin protections. All writes use campus transaction lock, row lock and marker-specific `If-Match: "version"`. This operational version does not claim/change a draft's edit version. Stale writes return409 without applying any fields or audit. Audit includes actor/campus/marker, request correlation, before/after and actions `qr.create`, `qr.reassign`, `qr.activate`, `qr.revoke`, `qr.release_revalidate` in the same transaction.

## Lifecycle and canonical signs

Create/edit→planned, install verification→active, revoke→revoked. Only planned/needs_verification may activate. Moving/relabeling/reassigning a sign clears installation verification and requires explicit replanning and verification. The same opaque public ID is retained. Installer name, actual/intended position, ordered installation/verification dates (campus timezone) and evidence are recorded; verifying accessibility remains a separate surveyed claim. Synthetic records say simulated.

Publication/rollback revalidate markers in their existing atomic campus transaction. Active missing/restricted/disabled-floor target→retired; physical node coordinates, local frame/scale or selected plan checksum change→needs_verification. Label-only node changes retain physical verification. Every release rebinding increments marker version/audits. Rollback never automatically activates revoked/retired/needs_verification signs. Explicitly replan/reverify if the restored target is suitable. Legacy trusted releases are projected without rewriting checksums; public resolution additionally checks live target eligibility.

`PUBLIC_APP_URL` is a configured canonical origin, never Request Host or forwarded headers. Nonlocal origins requireHTTPS; localHTTPlocalhost/127.0.0.1/::1 is the Docker demo exception. Credentials, paths, queries, fragments, whitespace and invalid ports are rejected; max180characters. Stable URL `/q/<random-id>`. SVG/PNG/PDF generated locally with readable origin/label/full URL, white quiet zone, native camera instructions and explicit location confirmation/no continuous positioning. No external QR service/tracker. Signs downloaded while planned are stamped NOT ACTIVE; download again after activation. Check readable domain and physical label before scanning. PNG/PDF built-in font suits Latin demo labels; use SVG with appropriate viewer/font for scripts not supported by that font. Physical printing/camera/device scanning remain owner/field verification.

## Endpoints and public route source

- `GET /api/v1/admin/campuses/{campus}/qr-markers`: private scoped inventory/current published targets/canonical origin.
- `POST` same: MarkerCreate; retry key, returns planned marker.
- `PUT /{marker}`: MarkerInput/If-Match; explicit reassign/replan.
- `POST /{marker}/activate`: Installation/If-Match; record actual placement/verification.
- `POST /{marker}/revoke`: substantive reason/If-Match.
- `GET /{marker}/sign.svg`, `.png`, `.pdf`: authenticated attachment/private no-store.
- `GET /api/v1/qr/{marker}`: no account; public no-store label/campus/building/floor/node/date/state/version/release. Non-active target details are hidden, unknown marker404, malformed ID422; manual fallback always available.

`POST /api/v1/routes` accepts a discriminated source:

```json
{"campus_id":"CURRENT_CAMPUS_UUID","source":{"kind":"qr","marker_id":"PUBLIC_MARKER_UUID","expected_marker_version":2,"confirmed":true},"destination":{"kind":"place","place_id":"PUBLIC_DESTINATION_UUID"},"profile":"shortest","cost_mode":"metric","expected_release_id":"CURRENT_RELEASE_UUID"}
```

Required `confirmed:true` is the user's explicit current-location assertion, not sensor/physical proof or an authentication token. Server rechecks campus, active eligibility, marker version and release. Inactive410, stale marker/release409, cross-campus/unknown404. Routing starts exactly at stored node through existing mixed Dijkstra and hard access/cost eligibility; no fabricated start place/anchor or proximity connection. Response adds nullable `source_marker_id`/`source_node_id`; for QR `source_place_id`/`source_anchor_id` are null. Destination anchor/cost/directions/floor metadata keep the existing contract. Existing place-source requests (including omitted default place kind) remain compatible.

A new source is never calculated offline. Landing polls15seconds/checks on focus, clears confirmation on changed version/release, reload, failed live check or connection loss, and rechecks on server stale/unavailable errors. Once confirmed, the existing planner/maps/text directions/floor switching are reused. Public release polling remains30seconds. Native phone-camera link opening is supported; no embedded camera/geolocation/indoor position inference added. Other M4 sources/overlays/PWA are later slices. Generated OpenAPI/TypeScript and `data/templates/qr-v1` schemas are the precise request contracts.
