# Data dictionary and coordinate contract

| Table / fields | Meaning and integrity |
|---|---|
| `campuses` | Stable UUID, unique code, name, IANA timezone, explicit `is_demo`, WGS84 centre and boundary |
| `dataset_revisions` | UUID, campus, integer version, parent, draft/review/frozen status, nullable draft/SHA-256 frozen input checksum, edit_version for optimistic writes, UTC creation time |
| `coordinate_frames` | Revision-scoped UUID; outdoor WGS84 or indoor local image; width/height pixels, optional metres/pixel and JSON calibration evidence |
| `buildings` | Revision-scoped logical UUID, campus, code/name, polygon footprint, visibility |
| `places` | Searchable destination UUID/code/name/kind, aliases, normalized search text, description, building association, display point and visibility |
| `navigation_nodes` | Topological vertex UUID/frame/landmark; exactly one of geographic point or local x/y pixels |
| `navigation_edges` | Directed from/to UUIDs, physical-pair UUID, frame, walkway/ramp/stairs kind, full WGS84 line, metres, measured/calibrated/estimated status, accessibility, visibility, static open flag and private evidence text |
| `place_anchors` | Place-to-node entry association; multiple allowed, open state and accessibility independent of the display marker; private verification evidence notes |
| `releases` | Immutable UUID pointing to frozen revision, input checksum and UTC publication timestamp |
| `active_releases` | One `(campus, public audience)` pointer, transactionally switched |

Stable logical IDs recur across revisions. Foreign keys include the revision; composite revision/campus constraints prevent cross-campus identity mixing. Published rows cannot be edited, deleted or unfrozen. These navigation tables contain no login credentials, source plan contents or personal location history. M2A identity tables are listed below.

Visibility values are `public` or `restricted`. Accessibility values are `verified_step_free`, `not_step_free`, `unknown`. The synthetic fixture's affirmative state is evidence about a test scenario only. Real accessibility still needs a survey. Static `is_open=false` excludes an edge; no dynamic closure administration exists yet.

JSON API fields use snake_case; frontend types come from OpenAPI. UUIDs in the demo are deterministic UUIDv5 values with a reserved `scns.invalid/demo` namespace; revisions/releases use fresh UUIDs. Alias normalization case-folds Unicode, collapses punctuation/whitespace, and search performs literal containment with exact/prefix ranking. Fuzzy/department/room ranking is not implemented in M1.

GeoJSON arrays use longitude first. The map adapter is the sole place to swap to Leaflet's latitude-first tuples. Degrees are never subtracted as metres. Baseline time is distance / speed, with explicit uncertainty and no personalized promise. An image point `(20,30)` on a 600px-tall floor maps to Leaflet simple coordinates `[570,20]`. A 200px calibration line measured as 10m gives `0.05 m/px`; a 200px local path then measures 10m. Cross-floor subtraction is prohibited.

The full master-spec entities not yet needed—floors/rooms, connectors, source assets, import jobs, reviews, operational overlays, QR and reports—will be introduced through dedicated migrations in their milestones, not empty speculative tables.

## M2A additions

| Table | Meaning and integrity |
|---|---|
| `admin_users` | Canonical username, display name, Argon2id password hash, active flag and creation time |
| `role_assignments` | Composite user/campus/role grant; editor, reviewer_publisher, operations, system_admin |
| `admin_sessions` | Hash of opaque token, user, absolute expiry, creation and revocation; no raw token |
| `login_throttles` | Hashed account/IP bucket key, attempt count and fixed-window expiry |
| `admin_bootstrap` | Single consumed-bootstrap row, protected from update/delete |
| `departments` / `department_places` | Revision-scoped department catalog and explicit same-revision place associations |
| `place_aliases` | Revision-scoped place, human alias, Unicode-normalized alias and language; unique normalized value per place/language |
| `audit_events` | Append-only actor, campus/revision/resource, action, before/after JSON, request reference and UTC timestamp; no passwords or session/CSRF tokens |

Migration `9fde71668c52` backfills canonical aliases from existing immutable place JSON without changing public release fields/checksums. Migration `0005_anchor_evidence` adds an empty-default private notes field; it invents no field evidence for old releases. New explicit demo seeds label their synthetic notes. Draft HTTP writes require nonblank notes for affirmative step-free edits; surveyed accuracy remains a human responsibility and later validation/publication gate.
