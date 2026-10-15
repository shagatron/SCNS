# Add unpublished MUJ OSM preparation and authenticated staged setup/import

The supplied OpenStreetMap export can now be converted and staged into a distinct real Manipal University Jaipur campus without renaming Demo Campus, copying synthetic indoor/accessibility data or publishing anything. The deterministic converter, checksummed licensed derivatives and secure Windows Compose helper use normal session/CSRF/campus authorization, audit, draft versions and import worker services. Original XML stays private; no contributor usernames/UIDs or credentials enter Git.

The academic and hostel polygons are distinct and disjoint. Exact coverage controls inclusion; the supported Polygon hull is explicitly an operational display extent, not ownership. Full shared-node polylines and foot direction/access are preserved; unsupported grade-separated/indoor/multi-level and malformed data are reported/quarantined. Source wheelchair tags never imply physical verification. This is OSM preparation, not official MUJ data/a field survey.

Provisioning creates/reuses one provenance-pinned campus, owner grant, draft and unapproved source transactionally. Three create-only batches400/400/306 have normal previews/errors and explicit APPLY confirmations. Interrupted/replayed jobs cannot duplicate records; stale edits reject rather than overwrite; original-copy writes are atomic. Independent source/release review and publication remain explicit. LF attributes preserve pinned derivative checksums on Windows autocrlf checkouts.

Prepared scope:51building footprints,55destinations,290nodes,688directed edges,21anchors/one frame.29weak components; only11destinations have another anchored destination in their component,10anchored places are alone and34destinations lack an entrance anchor. Hostel Entrance→GHS Entrance computes23.62m/three stored edges; Hostel→Faculty Block Entrance163.28m/six stored edges; academic→hostel and unknown step-free cases return no route. Graph0errors/111warnings remain for review. Public runtime/redesign, existing routes, permissions and schema are unchanged apart from the bounded protected provisioning endpoint; no new migration,4D–4F, merge/deployment or public release.

Validation:

- Final136affected backend tests passed (129units+7MUJ PostGIS); retained full211PostGIS passing run covers existing208cases plus initial3MUJ tests.
- Frontend61tests; lint/type/format/build; migration rehearsal/model alignment; repeated contracts/no drift.
-40distinct source browser cases covered through38initial regression passes+two corrected final MUJ cases; initial84built nginx/API/actual-worker cases passed in one run;82unaffected cases retained and both affected MUJ cases reran/passed on final mapped-loop topology. No single final84-case invocation claimed.
- Final frozen image converts the actual original offline and reproduces all pinned files; actual-worker helper verifies concurrent provisioning, interrupted preview/resume, committed replay, audit/version/public isolation. Git Windows-EOL simulation preserves checksums.
- Read-only existing developer-table content/count/schema/release receipts identical;`.env` absence and both retained volumes preserved. No developer seed/reset/bootstrap/migration/import/publication.

Earlier selector, missing-test-URL and disk-full verification attempts are recorded accurately, corrected and rerun. Actual Windows/Docker Desktop, real-device/physical campus/accessibility, institutional approval, full mapping and remote CI remain unverified. Windows helper/manual checks and independent-publication prerequisites: docs/operations/muj-osm.md; source/counts/ODbL: docs/data/muj-osm.md; complete evidence: docs/testing/verification.md.

Base: `redesign/public-experience` at487db02e04a991674862621f09932230255dbef6. Head: `feat/muj-osm-import`. Do not merge or publish automatically.
