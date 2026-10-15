# MUJ connectivity investigation — pinned preparation v1

Reviewed 15 October 2026. **MUJ stays unpublished.** This is an OSM source/topology investigation, not a campus survey. The newly supplied export and retained original both contain819138bytes, SHA256`d4b902b01fe944acb3161026679dabbab4898d6952bee22d7019f15fd15748de`. No contributor identities are reproduced. Derivatives retain © OpenStreetMap contributors / ODbL1.0 attribution.

The complete export (3193nodes/517ways/9relations), all prepared records, rejected ways, quarantined indoor descriptors and relation decisions were inspected. **No source-proven graph correction is applied.** The confirmed application defect is misleading synthetic wording. Exclusion policy is deliberately conservative; this conclusion does not certify every excluded path inaccessible or every retained path correct.

## Evidence and figures

- [Component inventory, sizes, anchored names, all34unanchored names and excluded references](muj-connectivity/README.md).
- [Standalone component map](muj-connectivity/components.svg), [subway detail](muj-connectivity/subway.svg).
- [Machine-readable diagnostic](muj-connectivity/diagnostic.json): all290stored node IDs,688directed edges, original internal node memberships, source way tags, all exclusions/relation decisions, exact coverage and building containment. Component identifiers C1–C29 are diagnostic labels only, not new database IDs.

Coloured solid lines are existing prepared graph geometry; numbers identify weak components. **Red dashed lines are excluded original OSM geometry selected for review, not applied connections, approved access or newly invented paths.** No basemap, proximity snapping or crossing joins. The coverage polygons are OSM mapping, not surveyed legal boundaries. Overview labels may overlap at this scale; zoom the SVG or use the exact-ID inventory. North is up; longitude is visually corrected by cos(latitude), not a metric survey. No distances are measured from these figures.

The diagnostic CLI first checks the original hash, every manifest file and re-converted bundle bytes. It matches canonical source-reference hashes back to each stored edge, so internal source vertices are accounted for even when not stored junctions. It cannot silently accept a modified converter or substitute a similarly positioned node. It only writes to a separate diagnostic directory, never opens a database or alters v1.

## Findings by category

### 1. Confirmed defects

No eligible source-supported path was found silently lost by repeated-node segmentation, directionality, multipolygon processing or identity collisions in the completed v1. The prior repeated-reference loop correction already retains GHS Hostel Main Road1154145951 and G3 footway1158552748; excluded1164716027 is outside exact coverage. Do not redo that work.

The draft route API universally described results as synthetic. It now returns a neutral unpublished/source-and-field-review notice, adding invented-data disclosure only when the actual campus `is_demo` flag is true. Public step-free wording uses that same metadata. QR empty-state wording now asks for an eligible published node and explicit labelling of simulations. Names are never used to decide provenance. Source rights choices and clearly labelled fixture instructions remain choices/instructions, not assertions that MUJ is synthetic. Existing imported source, per-feature provenance, OSM attribution and unknown accessibility remain visible through normal admin/source controls; no source approval is implied.

### 2. Valid mapped geometry needing explicit representation or policy

**Subway:** contrary to a possible interpretation of the earlier documentation, the export does contain a complete shared-node chain between the campuses. It is not merely a near crossing or a missing tunnel. Reading the raw highway references without treating them as an eligible route gives:

`University Entrance10780185180 → way1159217178 → way1158055389 → node10769840689 → way1154145270 → node10733816254 → way1154145273 → node10733816255 → way1246099090 → node10733816256 → way1154145269 (via11576759949) → node10733816257 → way1159217177 → node10778271605 → way1245274146 → node11576759947 → way1159998433 → way1245274147 → Hostel Entrance10780185181`.

This forensic chain is **not an authorized routing result**. The intervening ways also contain their full original vertices; the diagram above does not assert that non-adjacent displayed IDs are a straight segment.

| Source | Actual tags / topology | Current result and review needed |
|---|---|---|
|1154145270|`highway=pedestrian`, `level=0`, `name=Subway road`, `tunnel:name=Subway`;10733816254↔10769840689|Inside exact coverage; broad `tunnel:name` guard excludes even this approach. A name alone is not a proven tunnel/floor transition. Clarify approach vs tunnel extent before changing the pinned policy.|
|1154145273|`highway=steps`, `layer=-1`, `tunnel=yes`;10733816255↔10733816254|Source-supported stairs/connection, excluded by nonzero-layer policy. No wheelchair ramp inferred.|
|1246099090|`highway=footway`, `layer=-1`, `tunnel=yes`;10733816256↔10733816255|Endpoints inside the two polygons, but the full line crosses the road gap and fails exact polygon-union coverage as well as layer policy. Dropping the layer guard alone is insufficient.|
|1154145269|`highway=steps`, `incline=down`, `layer=-1`, `level=0`, `tunnel=yes`, both luggage/wheelchair ramps `no`|Excluded nonzero layer; source describes stairs, not a verified step-free transition. Mixed level/layer describes relative stacking, not surveyed floor labels/elevation.|
|1159217177 /1245274146|Steps10778271605↔10733816257; path11576759947↔10778271605|Inside exact coverage, but both touch the explicitly private entrance below, so rejected segments are deliberate.|
|Node10778271605|`entrance=yes`, `access=private`, `name=Subway Entrance`, `wheelchair=no`;75.5633072,26.8417877|Decisive access restriction; no `foot=yes` override. Cannot remove it from source interpretation to make a useful public route. Requires current authorized access/audience evidence.|
|Node10733816254|`entrance=yes`, `level=0`, `name=Subway entrance/exit`;75.5636667,26.8420098|Catalogued but unanchored because all its accepted path connections were excluded. Not evidence of a missing OSM door.|

The existing outdoor graph can store a tunnel's **horizontal** WGS84 polyline, explicit endpoint topology and stairs/non-step-free kind, without joining unrelated surface crossings. Thus blanket exclusion of every nonzero layer/tunnel is a preparation limitation, **not a claim that SCNS requires a new schema for every outdoor underpass**. Existing geometry distances do not measure vertical stair travel. A future reviewed preparation could use a narrowly evidenced corridor/coverage policy and explicit transition checks; this task does not authorize overriding the private entrance, guessing layer compatibility, or silently modifying an already imported pin. No reason to redesign indoor routing just to reduce components.

**Smaller academic components:** excluded926463927 (`AB1 corridor`,path,layer0,level0) shares retained references in C1/C3.1158509500 (`AB2 Corridor`,path,level0,building:levels3,roof:levels1) touches C1/C4/C5/C7/C9/C10/C11/C13/C14. The name-based corridor guard is intentionally broad; neither name nor `level=0` proves these are outdoor public paths. They may be valid ground-floor indoor/covered circulation that needs source ownership, exact entrance transitions and correct representation. Do not assert they are all physically blocked.

Explicit indoor multi-floor ways1158055386 and1247085145 (`indoor=yes`,`level=0;1;2;3`) touch respectively C3/C15/C18/C22–C26 and C1/C3/C18/C19/C21/C27–C29. Flattening them would falsely connect rooms/floors. Steps1245556383 touch C19/C21;1245556384 and1247150898 are also multi-floor. C20 touches upper-floor paths1247150897/1247150902 and1247150898; it must not become ground-level merely to connect. Old Mess corridor1271244213 has only `highway=path` and a name; its indoor/outdoor role needs evidence. Grand Staircase1163582909/1163582910 useslayer1;1568303898 useslayer-1 without a tunnel tag. None is silently normalized to ground.

**Boundary:** v1 rejects whole ways not covered by the exact academic495716022/hostel1158554635 union; it does not clip or retain only inside segments.57highway ways encounter this rule. That loses usable in-bound portions as a consequence of the chosen all-or-nothing policy; it is not evidence that their external portions are permissible. MUJ Hostel Road1159542817 touches C2/C17 but goes outside exact coverage. A revised policy could split at existing source boundary nodes or explicitly review an approach corridor. Cutting arbitrary new nodes, adopting the operational convex hull as access permission, or applying a new source policy via old create-only bundles would be incorrect. Full rejected geometry/tags are in the diagnostic.

### 3. Missing or ambiguous source evidence

**Central Library12585506492:**75.5651891,26.8415259;`amenity=library`,`name=Central Library`. No highway references that node, and it has no entrance tag. It lies within imported Administrative Block1158522861. Containment does not establish the Library's permitted door, floor, vestibule, shared building entrance or walkway. There is no source-supported Library anchor to add. The35-vertex building ring does not share an entrance-tagged node. No centroid or nearest path connection is proposed.

Other important unanchored places include Academic Block-3 (1244851612), LHC(1359652183), B1/B2/B3(1151360714/713/712), B6(1158515143), G1 relation15765627, Laundry/GHS Library relation15777926. Their imported display points/footprints similarly do not imply doors. Named Subway building1159754690 shares an entrance, but that is precisely the private10778271605 node. TMA Pai Auditorium1249393737 is building-tagged **and**room/auditorium/level0 inside AB2; its two mapped entrances10773902923/11664524407 remain separately catalogued. Promoting the room outline to an outdoor building is not a confirmed correction.

C6/C8/C12/C16 have **no excluded highway sharing a retained original node**. Their source-way lists and geometry are in the inventory; adding adjacent lines by visual proximity would invent topology. All other components list their touching rejected references. Some connections may exist physically but are absent in this source; disconnected-room/stair loops are evidence gaps, not automatic merge opportunities.

**Directions/access/relations:** only two generic `oneway=yes` highway tags, no `oneway:foot` tags. Motor directions are not applied to pedestrians; this does not explain the29weak components. Explicit private/no entrances10778271605/10831198789/10831239723 stay excluded. Barrier13078102236 has explicit `foot=yes` and is retained, so it is not an accidentally dropped pedestrian junction. No conditional-access bypass was added. Nine relations: valid footprint15765627/15777926 retained without filling holes;15777927 outside coverage;AB2/AB1 landuse relations15765611/15765621 are not building/floor/connector graphs;19474646 lacks supported multipolygon type;19474647 is a foot-route grouping, not new geometry/access; bus10475844/11783173 have no missing campus walking link to synthesize from absent external members. Rejected member rings do not fall back to filled buildings.

## Before / after and safe update decision

All preparation bytes, stable import IDs, source/preparation checksum receipts and existing frozen-draft/release rules are unchanged. There is **no v2 preparation, correction import or draft mutation to preview/apply**. Do not rerun the setup helper for this wording/report update. No deletions, upserts, owner-edit reconciliation or migration is needed. The Windows draftUUID is owner-reported only; this checkout has not inspected it.

| Measure / stored-graph software case | Before | After this review |
|---|---|---|
|Buildings / places / nodes / directed edges / anchors|51/55/290/688/21|Unchanged|
|Weak components / unanchored destinations|29/34|Unchanged|
|Saved graph validation|0errors/111warnings|Unchanged preparation; affected isolated tests rerun, see verification|
|Hostel Entrance→GHS Entrance|23.624997727885383m/3edges|Unchanged stored graph; not a fabricated new distance|
|Hostel Entrance→Faculty Block Entrance|163.28135622236027m/6edges|Unchanged|
|University Entrance→Hostel Entrance|No eligible route|Unchanged, deliberate access/coverage/grade policy|
|Hostel Entrance→Central Library|No eligible route|Unchanged, missing anchor|
|Verified step-free Hostel→GHS|No eligible route|Unchanged; unknown accessibility is not verified|
|Public Demo Main Gate→Library|256.88m/3edges;UI257m/4min|Retained baseline|

If later evidence supports corrections, first archive this v1 pin and receipts, define a new preparation version and exact add/change/remove plan with reference order, diff against the actual owner's draft (not this diagnostic), stop on owner edits/unexpected content, preview with existing imports, delete replaced edges explicitly through normal graph editing, and use normal permissions, If-Match, transactions/audits and independent reviews. Test interruption/replay/conflict/rollback before delivering that separate updater. Import upsert never deletes obsolete edges. Do not substitute a changed manifest and ask the owner to rerun the old helper.

## Prioritized owner evidence collection

Use private uploads/owner review, not public issues for source plans or photos with people. Do not trespass to collect evidence. For every observation record date, observer, OSM ID, actual permitted audience, position method/uncertainty, facing direction, and filename; photograph only where authorized. A GPS fix/photo is not a surveyed accessible path.

1. **Subway access first:** at hostel-side entrance10778271605 (longitude75.5633072,latitude26.8417877), obtain the campus authority's current pedestrian audience/access/opening rules and explain the OSM `private` tag. Label written permission `MUJ-SUBWAY-10778271605-access-YYYYMMDD`; authorised entrance photos `MUJ-SUBWAY-HOSTEL-10778271605-YYYYMMDD-01`. Without this, opening the public cross-campus route is not justified.
2. **Subway topology/grade:** at academic-side10733816254 (75.5636667,26.8420098), and only if permitted along stairs/tunnel1246099090 to hostel-side10733816257, mark the exact landings10733816255/256 and approach10769840689 on an annotated source map. Record actual tunnel start/end, whether each shared node physically joins, surface crossings that do not join, steps/ramps/width/slope and barriers. Label by exact way/node IDs (`MUJ-SUBWAY-1246099090-topology-YYYYMMDD`). Obtain permission for the intervening road corridor; the two OSM polygons do not cover it. No stair vertical distance or wheelchair status may be guessed.
3. **Library arrival:** at Administrative Block1158522861 / Library12585506492 (75.5651891,26.8415259), identify the Library's actual public entrance, floor, building-to-library transition and permitted continuous approach from an existing mapped path. Annotate the actual door (not the point marker), route and matching OSM nodes; include door/access photos and location uncertainty. Label `MUJ-LIBRARY-12585506492-entrance-YYYYMMDD`. Request an authorized plan if arrival is inside; do not publish a raw plan.
4. **Academic corridors:** inspect926463927 and1158509500 and their junctions with C1/C3 and auditorium entrances10773902923/11664524407. Confirm indoor/outdoor/covered status, floor-specific landings, doors and permitted audiences; annotate separately per floor, never combine `0;1;2;3`. Label `MUJ-CORRIDOR-<wayID>-<floor>-YYYYMMDD`. Include1158055386/1247085145 only with authorized floor evidence.
5. **Next useful destination/hostel approaches:** prioritize LHC1359652183, Academic Block-31244851612, Hostel Road1159542817(C2/C17) and your desired hostel entrance. Identify actual public doors and continuous permitted approach connections using annotated source-node IDs/photos. Label `MUJ-<OSM-kind>-<ID>-entrance-YYYYMMDD`. For inaccessible/missing links report “not observed/permission unknown”; never draw a line merely because endpoints look close.

Keep all accessibility unknown until a suitable documented survey verifies the full entrance/path chain. Independent source/audience/content approval and explicit publication remain separate future actions. No warning acknowledgements, review submissions or public MUJ release are performed here.
