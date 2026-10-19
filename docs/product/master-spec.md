# Smart Campus Navigation — Master Product Report and Codex Build Specification

Version: 1.0 · Prepared: 6 October 2026 · Intended format: Markdown supplied directly to a coding agent

Contents

- [How to use this document](#how-to-use-this-document)
- [1. Project purpose and starting point](#1-project-purpose-and-starting-point)
- [2. Product scope and release boundaries](#2-product-scope-and-release-boundaries)
- [3. People, permissions, and ownership](#3-people-permissions-and-ownership)
- [4. End-user experience and pages](#4-end-user-experience-and-pages)
- [5. Architecture and technology decisions](#5-architecture-and-technology-decisions)
- [6. Data model and relationships](#6-data-model-and-relationships)
- [7. Coordinate systems and map accuracy](#7-coordinate-systems-and-map-accuracy)
- [8. Campus data acquisition and upload workflow](#8-campus-data-acquisition-and-upload-workflow)
- [9. Admin application and map editor](#9-admin-application-and-map-editor)
- [10. Routing engine and algorithm rules](#10-routing-engine-and-algorithm-rules)
- [11. QR navigation and signage](#11-qr-navigation-and-signage)
- [12. PWA, caching, and offline behavior](#12-pwa-caching-and-offline-behavior)
- [13. API design and typed contracts](#13-api-design-and-typed-contracts)
- [14. Search implementation](#14-search-implementation)
- [15. Authentication, privacy, and security](#15-authentication-privacy-and-security)
- [16. Accessibility and inclusive navigation](#16-accessibility-and-inclusive-navigation)
- [17. Repository structure and data spaces](#17-repository-structure-and-data-spaces)
- [18. Demonstration data and missing-data behavior](#18-demonstration-data-and-missing-data-behavior)
- [19. Testing and release acceptance](#19-testing-and-release-acceptance)
- [20. Delivery milestones and dependencies](#20-delivery-milestones-and-dependencies)
- [21. Optional extensions with concrete integration plans](#21-optional-extensions-with-concrete-integration-plans)
- [22. Operations, maintenance, and cost model](#22-operations-maintenance-and-cost-model)
- [23. Requirements traceability and definition of done](#23-requirements-traceability-and-definition-of-done)
- [24. Final coding-agent execution instructions](#24-final-coding-agent-execution-instructions)
- [25. Technical reference notes](#25-technical-reference-notes)
- [26. Immediate owner checklist](#26-immediate-owner-checklist)
- [27. Configuration, reproducible commands, and deployment gates](#27-configuration-reproducible-commands-and-deployment-gates)
- [28. Concrete acceptance scenario matrix](#28-concrete-acceptance-scenario-matrix)

## How to use this document

This document describes the complete intended product, its data, architecture, implementation stages, repository, acceptance criteria, and future extensions. It is also a build prompt: give Codex this entire file and begin with the instruction below. Keep this document in the repository as `docs/product/master-spec.md` so requirements survive separate coding sessions.

> Build Smart Campus Navigation according to this specification. First inspect the repository and applicable project instructions. Preserve existing work. Start with Milestone 0 and implement Milestone 1 as a complete working vertical slice, then continue through the core milestones in order. Produce working code, database migrations, synthetic demonstration data, meaningful tests, and documentation. Keep a requirements checklist and record implemented, verified, deferred, and blocked items. Do not silently omit requirements or describe placeholders as finished features. When real campus data or institutional approvals are missing, use clearly identified synthetic data and keep the data onboarding workflow ready for the owner. Do not invent actual campus layouts, approvals, survey measurements, API credentials, or deployment results. Finish the current milestone's acceptance criteria before expanding its scope. The target is a maintainable campus service, developed incrementally by a student team.

The numbered milestones specify when features become required. “Core” means required for the complete navigation product; it does not mean everything must be built in the first coding session. “Extension” means a defined future capability that needs its own data or approval before implementation. A folder, mock screen, or empty class alone does not satisfy a feature.

## 1. Project purpose and starting point

Build a mobile-friendly web application that helps students, visitors, teaching staff, and campus personnel find buildings, rooms, departments, services, and facilities, then navigate along actual approved walking routes. The eventual product supports outdoor paths, indoor corridors, movement between floors, QR-based position selection, accessibility preferences, map administration, and continued campus data maintenance.

The existing project is a C console application demonstrating graphs, BFS, DFS, student records, service queues, department trees, hashing, sorting, and navigation history. The new product is a fresh web implementation using those graph concepts. Preserve the original C project in `legacy/`; do not require a C runtime for the website.

The former student-management and generic service-request modules are not automatically part of the public navigation product. They can remain in the legacy demonstration. The relevant production equivalents are location search, campus hierarchy, route calculation, map issue reporting, and operational maintenance. An independent student records system is outside the navigation core.

The owner's college is the intended first deployment. The exact campus name, boundaries, branding, building codes, maps, and publishing permissions must come from the owner or authorized university representatives. Configure these details; do not hardcode an assumed campus layout. Design for one campus initially, while using campus identifiers so another campus can be added without redesigning the database.

### 1.1 Problems addressed

- New students and visitors do not know building names, room locations, shortcuts, or appropriate entrances.
- Outdoor mapping services may show buildings but lack room-level campus details.
- Printed floorplans are difficult to search and do not calculate routes.
- Building labels and informal abbreviations differ from official room and department names.
- Step-free navigation depends on connected ramps, doors, lifts, and corridors, rather than a building-level accessibility flag.
- Campus changes, construction, lift outages, and moved rooms make static maps unreliable.
- Useful campus information is spread across maps, notices, departmental websites, and local knowledge.

### 1.2 Outcomes

1. Search a destination by official name, room code, abbreviation, alias, category, or department.
2. Choose a starting point manually, from a QR marker, or from permission-based outdoor geolocation.
3. Calculate a valid route through a maintained graph.
4. Display the route on outdoor and floor-specific maps, with readable directions.
5. Show measured or calibrated distance, estimated walking time, and data freshness.
6. Offer a verified step-free profile when data supports it.
7. Allow authorized campus maintainers to edit and publish map data without changing application source code.
8. Provide issue reporting, closures, version history, backups, and handover documentation.

### 1.3 Limits that must stay honest

Uploading a floorplan does not create a routing graph. Every walkable connection must be digitized and verified, or proposed by an assisted tool and subsequently reviewed. GPS is primarily an outdoor aid, not a guaranteed indoor position or floor detector. QR codes provide a known starting point when scanned; they do not continuously track movement. ETA is an estimate, not a guarantee. A route is only as trustworthy as its surveyed data and current closure information.

Do not claim emergency evacuation certification, live room occupancy, live crowd density, automatic indoor positioning, or university endorsement without the required evidence and authorization.

## 2. Product scope and release boundaries

| Capability | Initial pilot | Complete core product | Future extension |
|---|---|---|---|
| Campus map and searchable locations | Required | Required | Multiple campuses |
| Weighted outdoor routing | Required | Required | Alternative route choices |
| Distance and baseline ETA | Required | Required | Learned ETA |
| Building/floor/room directory | Small sample | Required for mapped areas | Institution-wide expansion |
| Indoor routing and floor transitions | Demonstration graph | Required | Assisted extraction from drawings |
| Manual start point | Required | Required | Saved contextual defaults |
| QR start markers | First tested marker | Required | Wider signage deployment |
| Browser outdoor location | Later pilot | Required with fallback | Sensor-assisted positioning research |
| Step-free routing | Synthetic test | Verified real routes | Personalized mobility constraints |
| Admin editing and imports | Basic workflow | Required | Advanced bulk GIS tools |
| Draft, review, publication, rollback | Foundation | Required | Department approval delegation |
| Closures and lift outage handling | Routing tests | Required | Authorized live feeds |
| PWA and cached selected routes | Basic shell | Required | Downloadable offline routing packs |
| Map issue reporting | Basic form | Required | Optional service-desk integration |
| Timetables and next-class navigation | No | No | Separate institution-approved module |
| Personal accounts and favorites | No login for public browsing | Local favorites; admin accounts | Optional student SSO |
| AI natural-language search | No | No | Grounded optional interface |
| ML and crowdsensing | No | No | Evidence-driven research modules |
| Dedicated Android/iOS application | No | No | Only after web adoption justifies it |

The core product must work without an AI API, sensors, student accounts, a timetable feed, or continuous location collection. An initial pilot can cover one building and its nearby outdoor connections while the database and editor support expansion.

## 3. People, permissions, and ownership

### 3.1 User roles

| Role | Main actions | Restrictions |
|---|---|---|
| Public visitor | Browse approved locations, search, plan routes, scan QR codes, report a map issue | Cannot see restricted maps or edit data |
| Student/staff viewer | Same public functions; optional approved additional destinations after future login | Login does not automatically grant every staff-only route |
| Map editor | Create and revise assigned campus drafts, trace paths, upload permitted sources | Cannot publish or change user roles |
| Map reviewer/publisher | Review validation results, approve release, publish, roll back | Must operate within assigned campus scope |
| Operations maintainer | Record authorized temporary closures and reopenings | Cannot modify unrelated map geometry or user permissions |
| System administrator | Provision roles, configure system, manage infrastructure and recovery | Actions audited; no public default password |

Use server-side authorization on every protected API and asset request. Hiding a button is not permission enforcement. Roles are campus-scoped. If authenticated staff maps are introduced, use separate authorized projections and route graphs rather than relying on labels hidden in the public UI.

### 3.2 Institutional responsibilities

- University sponsor: approves the pilot, use of drawings, map publication, and signage.
- Facilities/map owner: confirms actual entrances, corridors, access restrictions, closures, and alterations.
- Accessibility representative: reviews surveyed step-free paths and the wording of accessibility claims.
- Student development team: maintains code, surveys permitted spaces, tests routes, and documents work.
- Technical service owner: owns the deployed environment, credentials, backups, domain, and handover.
- Department/timetable owner: confirms optional class and room allocations.

The app should display an appropriate service owner/contact and map correction channel. Do not invent names, phone numbers, or university support commitments.

## 4. End-user experience and pages

### 4.1 Main navigation screen

Desktop: map with a compact side panel. Mobile: map plus an accessible bottom sheet or stacked controls. The map should remain usable on a small phone screen without obscuring the route or attribution.

Include:

- Campus selector, initially containing the pilot campus only.
- Destination search with keyboard-accessible suggestions.
- Start and destination selectors, swap control, and clear route.
- Manual start selection, “Use my location,” and QR guidance.
- Routing profile: shortest walking route, estimated fastest route when implemented, and verified step-free route.
- Map controls: zoom, fit route, select building/floor, recenter.
- Outdoor map, current-floor indoor map, and clear transition controls.
- Route summary, turn instructions, floor changes, warnings, and closure information.
- Map legend and visible source attribution.
- Online/offline indicator and release information available through a details panel.
- Reporting link and accessibility/settings link.

Do not make a full-screen map the only way to navigate. Provide a text route and destination directory.

### 4.2 Search and destination page

Search examples: “Library,” “AB2,” “Academic Block 2,” “AB2-204,” “computer lab,” “washroom,” and a configured department name. These are examples, not real campus assertions.

Each result includes stable place ID, name, type, building, floor label, relevant room code, access status, and whether it is currently routable. Duplicate room numbers across buildings must be disambiguated. A department occupying multiple rooms should present its locations for selection.

Place detail includes description, building/floor, approved photo or icon, entrances, verified facilities, opening hours if maintained, accessibility evidence, verification date, related department, and a route action. Unknown fields must remain unknown rather than receiving optimistic defaults.

### 4.3 Route workflow

1. User chooses or resolves a start.
2. User selects a destination and route preferences.
3. Backend resolves valid entrance/door anchors, active release, access audience, departure time, and current closures.
4. Backend runs the routing algorithm and returns structured route segments.
5. UI shows the complete summary and the appropriate current segment.
6. User can switch between outdoor and indoor segments and follow text steps.
7. If a closure changes while online, the UI checks and offers or calculates a revised route.
8. User can confirm arrival or report an issue without creating an identity-linked movement history.

Keep a planned route distinct from live navigation. Indoor progress is user-confirmed unless a verified positioning system exists. “Next step” is a manual advancement, not proof that the user has moved.

### 4.4 Directory and facilities

Provide building, department, room, and facility listings with category filters. Categories may include library, laboratory, classroom, administration, food, washroom, drinking water, medical centre, sports, parking, entrance, lift, ramp, and help desk. Show only surveyed categories present in the active dataset.

For “nearest facility,” first identify eligible destinations, then compare walkable network cost. Straight-line distance can narrow candidates but does not determine final nearest accessible destination. No known current occupancy means no “available lab” claim; show “mapped lab” and published hours instead.

### 4.5 Favorites, history, sharing, and settings

- Store optional recent searches and favorites on the device for the core product.
- Allow clearing local history and cached routes.
- Share a destination or a route request using stable place IDs and preferences; recalculate on opening.
- Do not include the user's precise GPS start by default in a shared URL.
- Support reduced motion, high contrast, text-size resilience, and accessible route presentation.
- Default language may be English; externalize labels so approved translations can be added later.
- Student account synchronization is an optional extension, not required public access.

### 4.6 Issue reporting

User can report wrong name, wrong room, incorrect path, closed entrance, lift issue, inaccessible route, outdated facility, damaged QR marker, or general feedback. Attach the selected place, edge, or route context when applicable. Ask for optional contact details only when needed for follow-up. Rate-limit submissions and moderate public input. Do not publish raw reports as live closures.

The reporting panel must explain that it is for map maintenance and is not a monitored emergency service. Display official emergency contacts only if verified and approved.

## 5. Architecture and technology decisions

Use a modular monolith with one frontend, one API application, one database, and a separately runnable ingestion worker when necessary. Avoid microservices, Kubernetes, multiple graph databases, and infrastructure unrelated to the pilot.

| Layer | Default choice | Reason and responsibility |
|---|---|---|
| Frontend | React + TypeScript + Vite | Typed mobile-friendly application with a straightforward build |
| UI | Tailwind CSS and a small accessible component set | Consistent controls without maintaining a large custom widget framework |
| Server state | TanStack Query or equivalent | Request lifecycle, caching, invalidation, loading/error state |
| Form validation | Typed schemas such as Zod | Editor forms and generated API contract validation |
| Outdoor maps | Leaflet with a configurable permitted basemap | Matches the established project direction |
| Indoor maps | Separate Leaflet `CRS.Simple` instances and image overlays | Floor-local coordinates without pretending pixels are geographic coordinates |
| API | Python + FastAPI + Pydantic | Typed REST contracts and routing implementation |
| Persistence | PostgreSQL + PostGIS | Relational relationships and outdoor spatial operations |
| Data access | SQLAlchemy + Alembic | Maintainable models, transactions, and migrations |
| Routing | Explicit Python adjacency graph and `heapq` Dijkstra | Explainable weighted graph algorithms with testable correctness |
| Storage | Private filesystem adapter in development; object-storage adapter for deployment | Restricted source plans and approved derived assets |
| Background jobs | Database job table and one worker process | Durable bounded imports without requiring Redis immediately |
| PWA | Service worker tooling compatible with Vite, Cache Storage, IndexedDB | App shell and explicitly managed public cached content |
| Tests | pytest, frontend component tests, Playwright | Routing, permissions, API, and critical user journeys |
| Packaging | Docker Compose for local full stack | Repeatable setup with PostGIS and persistent volumes |
| CI | GitHub Actions or the repository's existing CI | Static checks, tests, migration validation, reproducible builds |

Choose compatible supported package versions during implementation; pin dependencies and commit lockfiles. Check current official documentation instead of guessing version APIs. Database and map provider choices should be configuration-driven.

PostgreSQL is the canonical editable store from the first persisted milestone. JSON/CSV/GeoJSON serve as import, export, fixtures, and immutable releases; they are not a second competing database. A tiny in-memory routing fixture is acceptable in algorithm unit tests.

### 5.1 Logical module boundaries

- Campus catalog: campuses, buildings, floors, places, departments, aliases.
- Map data: source assets, calibration, node and edge editing, connections.
- Routing: graphs, eligibility, weighted search, snapping, steps, profiles.
- Publication: draft datasets, validation, review, releases, public projections.
- Operations: closures, issue triage, verification tasks, QR inventory.
- Identity: admin login, role assignments, sessions, optional later institutional SSO.
- Ingestion: parsing, preview, validation, staging, atomic commit, job progress.
- Optional modules: timetable, grounded AI interface, ML ETA, sensors.

Routing should not depend on HTTP request objects or database ORM objects. Define plain typed graph records and deterministic functions. Route algorithms must run on a frozen eligible graph snapshot.

### 5.2 Deployment arrangement

Prefer a same-origin public frontend and `/api` reverse proxy. Deploy frontend assets, API, worker, PostGIS, and storage with TLS, secret injection, health checks, and persistent state. The development Compose environment is not automatically production hosting.

No specific provider or paid account is assumed. Provide container-based deployment instructions adaptable to a university server or suitable cloud service. If a repository is later hosted by a specific platform, follow that platform's workflow and authorization.

## 6. Data model and relationships

### 6.1 Common conventions

- Stable UUID IDs; human-readable campus/building/room codes are separate fields.
- `campus_id` on campus-owned resources; enforce cross-campus consistency.
- UTC timestamps for storage; campus IANA timezone for schedules and displays.
- Metres and seconds for routing values; explicit coordinate frames.
- Core map entities belong to a `dataset_revision_id` for draft/release isolation.
- Stable logical IDs can recur across revisions; references use both revision and logical identity.
- Source, verifier, verification date, visibility, and evidence where applicable.
- Controlled enumerations with migration strategies; distinguish unknown, false, and true.
- Do not store indoor pixels in an EPSG:4326 geometry.
- Domain relationships validated in services and database constraints where feasible.

### 6.2 Core entities

| Entity | Essential fields and purpose |
|---|---|
| Campus | ID, code, name, timezone, approved boundary, centre, contact, branding config |
| DatasetRevision | Campus, logical version, draft/review/frozen status, parent revision, creator, timestamps |
| Building | Stable ID, revision, campus, code, name, outdoor footprint, aliases, access classification |
| Floor | Building, stable ID, floor label, numeric ordering, local frame ID, optional elevation metres |
| Place | Name, kind, room code, building/floor association, description, public visibility, optional display geometry |
| PlaceAlias | Place ID, alias text, normalized value, language; indexed search values |
| PlaceAnchor | Place, node, entrance/door role, priority, opening/access requirements |
| Department | Name/code, description, contact if authorized; separate links to its actual places |
| FacilityDetails | Place subtype metadata, maintained opening hours, verified attributes |
| NavigationNode | Revision, ID, type, coordinate frame, outdoor geometry OR floor-local x/y, floor, landmark label |
| NavigationEdge | Revision, stable ID, from/to IDs, type, coordinate frame geometry when possible, distance, traversal estimates, direction policy |
| EdgeAccessibility | Width, slope, steps, surface, kerb/ramp details, evidence, verification and unknown states |
| Connector | Stair/lift/ramp/entrance group, participating levels/landing nodes, operational reference |
| SourceAsset | Private storage key, checksum, original name, file type, rights, uploader, campus, restriction |
| MapLayer | Approved derivative asset, floor/revision, image dimensions, coordinate transform, calibration status |
| SurveyEvidence | Referenced entity, measurement method, date, reviewer, private notes/photo references |
| ImportJob | Type, campus, revision, checksum, status, counts, row diagnostics, durable progress |
| Release | Immutable revision reference, manifest checksum, publisher, published time, public snapshot assets |
| ActiveRelease | One current release pointer per campus/audience, changed transactionally |
| ValidationRun | Revision checksum, validator version, errors/warnings, date, pass status |
| ReviewDecision | Revision checksum, reviewer, decision, notes; invalidated by subsequent edits |
| Closure | Target stable IDs, start/end, reason, affected directions, status, operational version, creator |
| IssueReport | Place/edge/route context, category, description, status, optional contact, restricted attachments |
| QRMarker | Public random marker ID, mapped node, label, installation status, verification, revoked/active |
| User | Admin identity, display name, authentication reference or password hash, active status |
| RoleAssignment | User, role, campus scope, optional editing area scope |
| AuditEvent | Actor, action, resource IDs, timestamp, revision, before/after references, request correlation |

Separate conceptual definitions do not require one table per sentence. Use a documented schema that preserves these relationships. Do not flatten departments, rooms, navigation nodes, and buildings into one ambiguous “location” row.

### 6.3 Places versus nodes

A searchable place is not automatically a route vertex. A library can have a display polygon and three entrance anchors; a room may have one or more door nodes; an outdoor junction is a route node with no searchable destination entry. Choose reachable eligible destination anchors based on the routing profile, not by connecting to the building centre.

Room codes must be unique within the configured building/floor naming rule. Names may repeat. Door/entrance anchors cannot reference a node in another dataset revision or campus.

### 6.4 Graph edge representation

Use one explicit stored directed edge per permitted direction. The editor's “two-way” action creates a paired set with a shared physical-path ID. This eliminates ambiguous assumptions when a passage is one-way or a closure affects only one direction.

Core edge fields:

```text
id, physical_path_id, dataset_revision_id, campus_id
from_node_id, to_node_id
kind = walkway | corridor | door | entrance_transition | stairs | lift | ramp
coordinate_frame_id (nullable for cross-frame transitions)
polyline (frame-specific; nullable for abstract vertical transitions)
distance_m, horizontal_distance_m, vertical_rise_m (when measured)
distance_status = measured | calibrated | estimated | unknown
baseline_traversal_s, wait_estimate_s, uncertainty_note
access_class, permitted_audiences
opening_schedule_id
accessibility_status = verified_step_free | not_step_free | unknown
width_m, slope_percent, step_count, surface (nullable)
connector_id, source_evidence_id, last_verified_at
```

Require nonnegative finite cost inputs and valid endpoints. Avoid zero-cost movement edges except documented logical transitions; prevent pathological zero-cost cycles. Unknown distance cannot silently become zero.

### 6.5 Extension tables

Timetable: course, cohort, teaching session, room allocation, schedule revision, cancellation/move override. Personalization: opt-in saved places and profile preferences. ETA research: consented aggregated segment observations, dataset metadata, model registry and evaluation artifacts. Sensor integration: authorized source registry, observation freshness, confidence, and equipment state.

Introduce these with dedicated migrations only when the relevant extension is implemented. Core release must not depend on speculative tables.

## 7. Coordinate systems and map accuracy

### 7.1 Outdoor coordinates

Store longitude/latitude geometry in WGS84, with GeoJSON positions ordered `[longitude, latitude]`. Leaflet APIs usually accept `[latitude, longitude]`; centralize that conversion and test it.

Calculate outdoor metres using PostGIS geography or a suitable local projected coordinate system. Degree differences are not distances in metres. Route length follows the actual path polyline, not just the endpoints.

Use an approved campus boundary to restrict suggested starts and flag imports outside the expected area. An outside-boundary point is not always invalid: an approved approach path can have an explicit exception.

### 7.2 Indoor coordinates

Each floor has a named local coordinate frame. Original image coordinates use origin at top left, x to the right, y downward. Preserve original image dimensions. Rendering translates these through one documented adapter, such as Leaflet simple-map `[map_y, map_x]` with a y inversion when needed.

Do not reuse a geographic map instance for an indoor floor by changing its coordinate assumptions. Use separate instances/components and distinct typed coordinate objects.

If the plan has a verified uniform scale:

```text
metres_per_pixel = surveyed_distance_m / corresponding_image_distance_px
path_distance_m = sum(polyline_segment_lengths_px) * metres_per_pixel
```

Persist calibration line endpoints, measured distance, method, date, and reviewer. A rotated uniform-scale plan remains usable. A stretched, perspective-distorted, or stitched plan needs a more suitable fitted transform and independent check measurements. Record uncertainty and do not publish precise metre values from an uncalibrated image.

If room routing topology is verified but the scale is unknown, publish only an explicitly labelled directions-only mode; do not return a fabricated exact distance or ETA. The main pilot acceptance dataset must contain calibrated distances.

### 7.3 Cross-floor and outdoor/indoor connections

Connect outdoor entrance nodes to indoor entrance/vestibule nodes with a documented transition edge and reviewed traversal estimate. Connect floors through actual stair landings, lift stops, or ramps using a connector ID. Local x/y values from different floors cannot be subtracted to infer walking distance.

For lifts, record served floors, access constraints, movement estimate, and baseline wait estimate. Do not calculate lift vertical distance from horizontally aligned image coordinates. Elevator wait and operational state must remain estimated or unknown unless an authorized feed exists.

Indoor georeferencing is optional. Room routing can work entirely in local floor frames provided transitions are correctly mapped. Never force local pixels into a latitude/longitude column to simplify display.

## 8. Campus data acquisition and upload workflow

### 8.1 Data required from the owner/university

1. Written permission or applicable institutional authorization to use and publish campus navigation information.
2. Campus overview map, boundaries, building names/codes, and permitted approach paths.
3. Building-by-building floorplans, floor labels, image/PDF scale information, and version dates.
4. Room list, official names/codes, public departments, facilities, and approved aliases.
5. Actual door locations, building entrances, corridors, stairs, lift stops, ramps, and access restrictions.
6. Accessibility measurements or a supervised survey: steps, slopes, widths, surfaces, and working lift routes.
7. Opening/closing rules relevant to pedestrian routes.
8. Allowed source plan visibility and any areas that must be redacted or omitted.
9. Permission and physical placement plan for QR signs.
10. Named operational contact for map corrections and closures.
11. Optional approved timetable export/feed and its owner.

Store a provenance register. A publicly visible building on a basemap does not establish that all of its interiors may be published.

### 8.2 Supported input formats

| Input | Initial support | Processing |
|---|---|---|
| CSV | Required | Typed location/node/edge/entity imports with explicit columns |
| JSON | Required | Versioned campus dataset and release interchange |
| GeoJSON | Required for outdoor geometry | Validate CRS assumptions, geometry types, and campus association |
| PNG/JPEG floorplan | Required | Private source upload, reviewed display derivative, calibration and tracing |
| Multi-page PDF | Core ingestion milestone | Select page, bounded raster conversion, orientation/dimensions preservation |
| XLSX room directory | Later convenience | Worksheet and column mapping using the same staged importer |
| SVG | Later controlled input | Sanitize or rasterize; never publish arbitrary active SVG |
| DWG/DXF/CAD | Extension | Approved offline conversion to supported formats or a dedicated tested adapter |
| OpenStreetMap extracts | Extension/convenience | Licensed imported candidate paths, manually checked for campus suitability |

Google Maps or other map screenshots are not automatically reusable datasets. Source rights and terms must be checked before using third-party images or extracted content. Do not scrape external maps as a substitute for authorization.

### 8.3 Floorplan-to-navigation pipeline

1. Create building and floor records in a draft dataset.
2. Upload plan as a private source asset; capture rights and restriction metadata.
3. Validate file type, limits, and decoding; convert selected PDF page if needed.
4. Generate a display derivative; remove prohibited sensitive areas and review it before publication.
5. Record orientation, image size, frame, scale, and calibration evidence.
6. Open floor editor; mark room outlines or label points as needed.
7. Place each destination's door anchor; a room-centre marker is only for display.
8. Trace corridor centre-lines, junctions, doors, stairs, lift stops, ramps, and building entrances.
9. Connect actual traversable segments; apply directions, access, and accessibility evidence.
10. Link floors and outdoor paths through reviewed connector records.
11. Validate graph, search records, calibration, permissions, and assets.
12. Walk representative routes and correct the model.
13. Submit a frozen draft for review and publish its approved public projection.

OCR and computer vision may propose room labels or corridor lines later. Suggestions stay in a draft review layer until a person approves them. A PDF renderer is not a route extractor.

### 8.4 Import lifecycle

Use `uploaded → parsing → preview_ready → validated → committed` or `failed/cancelled`. Each import targets a draft revision. Show column mappings, create/update counts, conflicts, invalid rows, warnings, and exact row-level diagnostics before commit.

Required properties:

- Explicit schema version, units, coordinate frame, and stable external IDs.
- Referential validation across related files before inserting edges.
- Dry-run preview with no changes to published data.
- Deterministic upsert rules; repeating an unchanged import is idempotent.
- Repeated external ID with different content requires explicit update policy.
- Dataset transaction prevents partial commits. Failed imports leave no half-built graph.
- Detect duplicate room codes, invalid geometry, mixed campuses, unknown node references, and incompatible coordinate frames.
- Bound row counts, parse duration, expanded image size, pages, and storage.
- Report asset processing progress and retries without duplicate writes.
- Reject unsupported files with actionable instructions.
- Export diagnostics safely; escape spreadsheet formula-like cell values in CSV diagnostics/exports.

For large imports, parse into staging tables/object files, validate, and commit once. Worker jobs need durable states, bounded retries, cancellation, and cleanup of orphaned temporary objects.

### 8.5 Upload security

Authenticate uploaders and authorize the destination campus/revision. Validate allowlisted extensions, decoded content, signatures, byte size, image pixel count, and PDF page limits. Generate storage names. Prevent path traversal and arbitrary URL fetching. Keep original plans private and outside the public web root.

Perform PDF/image conversion in a bounded isolated worker process using maintained libraries. Reject encrypted/unsupported PDFs unless a separately documented authorized workflow is added. Use malware scanning when required by the deployment environment. Never send confidential plans to public scanning or AI services without permission.

Only approved derived assets are publicly retrievable. Return private assets through authorized endpoints or short-lived scoped URLs; never expose arbitrary object keys.

## 9. Admin application and map editor

### 9.1 Admin pages

- Login and session management.
- Dashboard: current release, pending drafts, errors, issues, verification tasks.
- Campus configuration and map source settings.
- Building, floor, place, department, alias, facility, and anchor editors.
- Outdoor graph editor and indoor floor editor.
- Asset upload and provenance register.
- Import preview/validation/job dashboard.
- Graph quality report and route test console.
- Draft review, publication, release comparison, rollback.
- Closure management and lift/entrance outage controls.
- Issue triage and QR inventory/print management.
- User/role administration for system administrators.
- Audit log with filters and read-only detail views.

### 9.2 Editor tools

Allow add/select/move nodes, draw/edit edge polylines, create paired two-way paths, delete safely, undo/redo draft actions, snap to existing nodes, split a path, connect intersections deliberately, and attach place anchors.

Crossing polylines are not automatically connected; bridges, stairs, and overlaps may cross visually without physical access. Warn about near-duplicate nodes and apparent unmapped intersections, then request editor review. A geometry edit that changes lengths must recalculate the affected draft metrics and require renewed validation.

Indoor tools include floor switcher, plan opacity, calibration tool, room label placement, corridor/door editing, connector assignment, and floor-specific visibility. Outdoor tools include campus boundary, path geometry, entrances, and approved basemap overlays.

Expose accessibility attributes and unknown states clearly. Editing “step-free” requires evidence fields rather than an unchecked default. Show source and last verification beside map features.

### 9.3 Editing integrity

- Draft-only mutations; published revisions immutable.
- Optimistic concurrency via entity/revision version or ETag. Conflicts must not silently overwrite another editor.
- Autosave indicator and recovery for unsaved edits; publication is a separate action.
- Before deleting a node, preview affected edges, anchors, connector references, and QR markers.
- Restrict cascading operations to explicit draft changes with an audit record.
- Review validity bound to dataset checksum; new edits invalidate old approval.
- Reviewer receives change diff, errors/warnings, asset visibility, and route test evidence.

### 9.4 Publication and rollback

Freeze a revision, run validation, approve, generate immutable public artifacts, then atomically update the active-release pointer. If artifact generation fails, keep the previous release active. Route calculations must not mix nodes from one revision with edges or floorplans from another.

Public releases contain only approved fields, nodes, edges, places, and assets. Server-side public routing must use the same approved projection. Do not leak restricted corridors through a computed route or infer their existence through public error details.

Temporary operational closures are a separately versioned live overlay. Rolling back a map release must preserve current safety-relevant closures where target IDs still exist; unresolved closure targets require operator review. Never reopen an outage simply because the map release was rolled back.

### 9.5 Quality validation

Validate missing references, invalid/negative costs, duplicate IDs, inconsistent direction pairs, impossible floor transitions, disconnected searchable destinations, unlinked doors, empty connector groups, out-of-bounds indoor coordinates, unusual path lengths, stale evidence, and forbidden visibility relationships.

Run connectivity and expected-route tests for standard and step-free profiles separately. A disconnected component is not always erroneous: a legitimately isolated or restricted area can be documented. Publication requires no blocking errors and explicit acknowledgement of material warnings.

## 10. Routing engine and algorithm rules

### 10.1 Algorithms

Use adjacency lists. Implement Dijkstra as the authoritative initial weighted shortest-path algorithm with a binary heap priority queue and predecessor reconstruction. BFS/DFS support reachability, connected-component diagnostics, and educational explanation. BFS is not the weighted shortest walking route algorithm.

Dijkstra complexity with adjacency lists and a heap is approximately `O((V + E) log V)` under ordinary assumptions. The graph is sparse; avoid a full adjacency matrix for production routing.

A* is an optional optimization after correctness is established. A heuristic must be admissible for the specific cost/profile and coordinate system. Use zero heuristic when an outdoor/indoor/vertical mix lacks a proven lower bound. A naive Euclidean formula across different floors or mixed pixel/geographic coordinates is invalid. Compare any A* implementation against Dijkstra on representative generated graphs.

### 10.2 Hard eligibility before cost

Exclude edges that are unpublished, closed, outside the user's allowed audience, not open under the route's schedule policy, or forbidden by hard mobility constraints. For verified step-free routing, exclude stairs and edges with unknown step-free status. Confirm connected accessible entrances, doors, ramps, lifts, and landing paths.

If no valid step-free route exists, return a distinct no-route result with useful next actions. Do not silently return a stairs route. A “prefer no stairs” soft preference, if introduced, must be a separately labelled profile.

### 10.3 Cost models

Shortest-distance profile: minimize trusted `distance_m`.

Baseline fastest profile: minimize additive traversal seconds using maintained walking speeds and connector estimates:

```text
edge_time_s = horizontal_walk_time_s + vertical_movement_time_s
              + door_or_transition_delay_s + estimated_wait_s
```

All components must be nonnegative and have clear units. Estimate stairs/ramps with explicit calibrated policies; do not apply a speed intended for horizontal walking to unmeasured vertical movement. Document walking speed defaults and make them configurable. Avoid implying personalized medical advice.

Optional preference profiles may add documented nonnegative costs for outdoor exposure or rough surfaces. Normalize or convert penalties to comparable units. Always report physical distance separately from the optimization score. Do not call a penalty-weighted route the mathematically shortest distance.

### 10.4 Schedule and temporal limitations

Milestone 1 may evaluate static opening/closure state at the requested departure time, and must state that policy. In the core operational milestone, conservatively exclude edges that close during the estimated route window; return schedule limitations and avoid promising a route valid across an unhandled boundary.

True arrival-time-dependent routing, waiting for gates, lift queues, and timetable-dependent passages are extensions requiring a defined FIFO temporal model and additional algorithm tests. Ordinary Dijkstra with arbitrary changing costs is not sufficient for unrestricted time-dependent routing. Store UTC instants and evaluate local recurring hours in the campus timezone.

### 10.5 Source and destination resolution

A place can have multiple start or destination anchors. Route between all eligible candidate anchors efficiently, such as using synthetic super-source/sink edges inside the request-local graph. Choose the least-cost eligible combination. Exclude unknown or inaccessible anchors for a verified step-free profile.

Start equals destination returns a zero-length successful result and an arrival message. A searchable place with no route anchor returns “location mapped, routing unavailable,” not a straight line.

### 10.6 Outdoor location snapping

Given browser coordinates and reported accuracy:

1. Check valid ranges, timestamp, campus proximity, and configured accuracy threshold.
2. Find candidate permitted walkable path segments using a spatial index.
3. Project onto candidate polylines and rank by proximity and eligibility.
4. Preserve path direction and create temporary split nodes/edges in the request graph.
5. Ask for manual start confirmation if results are ambiguous or too far away.

A nearby path across a wall or fence may be physically unreachable. Use approved start zones and entrance knowledge; do not draw an unverified link from the GPS dot through a building. For the initial pilot, suggest the nearest verified landmark and require confirmation instead of claiming continuous precise positioning.

The browser's location permission is user-controlled and requires a secure context in deployment. Show the accuracy radius, stop watches when navigation ends, and provide manual/QR fallbacks for denial, timeout, poor accuracy, or unsupported browsers.

### 10.7 Route representation and directions

Return a typed result containing:

- Route ID/reference, campus, dataset release, closure overlay version, generation/departure time.
- Source/destination resolved IDs and anchors.
- Profile, distance metres, estimated duration seconds, uncertainty/warnings.
- Ordered edge IDs and node IDs for debugging in authorized tooling.
- Outdoor segments with GeoJSON geometry.
- Indoor segments grouped by building, floor, and local coordinate frame.
- Transition segments for entrances, stairs, lift, and ramps.
- Ordered instructions referencing segments, landmarks, and floor labels.
- Validity/freshness information and route-specific limitations.

Steps can say “Enter Academic Block A through the north entrance,” “Continue along the corridor,” or “Take the lift to Floor 2” when those details exist in verified data. Avoid inventing compass direction or left/right from image coordinates without orientation metadata. Simple landmark and connector instructions are preferable to wrong turn instructions.

### 10.8 Graph caching

Build immutable graph snapshots keyed by campus, release, and audience. Apply closures using a versioned overlay included in route cache keys. Include profile and source/destination in cache keys. Avoid unbounded cache cardinality for raw GPS requests.

In multiple API workers, invalidate through a reliable active-release/overlay version check; process-local memory alone cannot provide cross-worker consistency. Every result includes the versions used. A failing cache rebuild keeps a coherent previous snapshot or returns an explicit unavailable state; it must not mix revisions.

## 11. QR navigation and signage

Generate QR codes containing the canonical HTTPS app URL plus an opaque public marker ID, for example `/q/<marker-id>`. On scan, resolve it to a current verified node and show a confirmation label. Marker IDs are public identifiers, not authentication tokens.

Core functionality:

- Create, label, activate, revoke, and reassign markers through authorized admin operations.
- Preview printable SVG/PNG/PDF signs with readable location text, a short link, and scanning instructions.
- Record intended and actual installation positions, installer, date, and verification.
- Use stable canonical URLs so signage survives map release changes.
- Revalidate markers during publication; a removed node requires reassignment or a clear retired-marker screen.
- Include a readable origin/domain on signs so users can notice substituted codes.
- Support the phone's native camera opening the link; embedded scanning is optional and should have camera-permission fallback.

Scanning anchors the user at the marker at that time. Moving a marker physically invalidates that assumption until it is reverified. Do not infer current location from an old saved QR URL without user confirmation.

## 12. PWA, caching, and offline behavior

### 12.1 Core offline scope

Provide manifest, icons, install guidance where supported, service worker updates, and cached app shell. Allow users to save an already calculated public route together with its directions and approved required floorplan assets. Provide limited cached destination browsing when available.

Offline core behavior is viewing a saved route, not guaranteed calculation of a new route. Show “saved route — current closures unavailable,” release timestamp, and last online validation. Unsupported route requests explain that a connection is needed. Returning online revalidates the saved route before treating it as current.

Exclude admin API responses, private plans, login/session data, contact details, personal timetables, and precise movement traces from the public service-worker cache. Use cache versioning, bounded storage, expiry, explicit clear controls, and safe updates that do not erase an in-progress route unexpectedly.

### 12.2 Basemap policy

Map rendering software, map data, and map tile hosting are separate concerns. Maintain required attribution and configure the provider. Do not bulk-download or provide an offline tile pack from the standard OpenStreetMap public tile server. Offline outdoor backgrounds require approved campus imagery, self-hosted data, or a provider explicitly permitting it.

### 12.3 Full offline routing extension

If added, publish a downloadable public-only graph pack and approved assets, validate checksums/schema version, install atomically in IndexedDB, and run a client-side routing engine. Use shared conformance fixtures to prove parity with server-side costs and constraints. Include pack age, overlay version, expiry policy, and conservative handling of unknown current closures.

Do not expose restricted graphs in an offline pack. Public downloadable content cannot later be reliably recalled from all devices. Evaluate this before distributing more sensitive map detail.

## 13. API design and typed contracts

Use `/api/v1`, Pydantic request/response models, generated OpenAPI documentation, and checked-in or reproducibly generated TypeScript client/types. Validate path/query/body IDs, limits, coordinate ranges, and enums. Require pagination for large collections and bounded bounding-box/zoom queries for graph/map views.

### 13.1 Public endpoints

| Method and route | Function |
|---|---|
| `GET /campuses` | Approved public campus list |
| `GET /campuses/{id}/release` | Active release metadata and manifest |
| `GET /campuses/{id}/map` | Bounded public map data by layer/extent |
| `GET /campuses/{id}/search` | Ranked searchable places with filters |
| `GET /places/{id}` | Approved place detail |
| `GET /buildings/{id}/floors` | Published floor list |
| `GET /floors/{id}/map` | Published floor layer metadata and approved asset references |
| `POST /routes` | Compute route using structured source/destination inputs |
| `POST /location/resolve` | Propose verified outdoor start choices or snap result |
| `GET /qr/{marker_id}` | Marker resolution and verification metadata |
| `GET /campuses/{id}/closures` | Approved public operational restrictions |
| `POST /issues` | Rate-limited map issue report |
| `GET /health/live` | Process health without leaking secrets |
| `GET /health/ready` | Bounded dependency readiness status |

### 13.2 Route request shape

```json
{
  "campus_id": "<uuid>",
  "source": {"kind": "place", "place_id": "<uuid>"},
  "destination": {"kind": "place", "place_id": "<uuid>"},
  "profile": "shortest",
  "departure_at": "2026-10-06T09:00:00Z",
  "expected_release_id": "<uuid-or-null>"
}
```

Define discriminated source types for place, public node, QR marker, and permitted outdoor GPS input. Server derives audience from authentication/context; never accept a client-supplied `is_admin` or unrestricted audience. GPS input includes latitude, longitude, accuracy metres, and observation timestamp.

The UUID strings above illustrate a contract; they are not working sample data. Supply valid fixture IDs in generated API examples.

### 13.3 Protected endpoints

Group protected routes under `/admin` for revisions, entities, graph edits, assets, imports, validations, review, release publication, rollback, closure operations, issue triage, QR creation/printing, users/roles, and audit retrieval.

Implement optimistic version guards for mutations, idempotency keys for import commit/publication/job submission, and scoped permissions for every action. Issue report contact details are available only to authorized maintainers.

### 13.4 Error and freshness behavior

Provide stable machine-readable codes: invalid input, location not found, location not routable, no route, no verified step-free route, location too uncertain, access denied, stale release, conflict, import validation failed, and service unavailable. Include request IDs and useful safe messages.

Specify HTTP behavior in OpenAPI. For example, invalid bodies use validation errors; version conflicts use 409; authorization uses 401/403; unknown public IDs use 404; a valid route request with no permissible path returns a documented domain result. Restricted place existence should not leak through a detailed public error.

Routes use `Cache-Control: no-store` by default when precise starts are involved. Selected public route caching happens explicitly on the device. Do not log raw route bodies containing user position by default. Public release artifacts use immutable checksummed URLs and suitable cache headers.

## 14. Search implementation

Normalize case, whitespace, punctuation, common room separators, and configured aliases without losing canonical labels. Index campus, name, room code, type, department links, and aliases. Use PostgreSQL trigram/full-text features if appropriate rather than a new search cluster.

Rank exact code/name matches first, prefix/alias matches next, then fuzzy text. Return explainable labels and avoid silently guessing between duplicate destinations. Limit query lengths and result count. Empty search provides useful categories or popular approved locations without implying personalized tracking.

Ensure unpublished and restricted places never appear in public suggestions, exports, related-place links, or counts that expose sensitive entries. Search must remain functional when an AI provider is unavailable.

## 15. Authentication, privacy, and security

Public routing and directory browsing require no account. Admin authentication is required for editing. Provide secure session cookies using `HttpOnly`, `Secure` in deployment, appropriate `SameSite`, session expiry/revocation, login throttling, and CSRF protection on cookie-authenticated writes. Use maintained password hashing if local admin accounts are used. Never commit a fixed admin password.

Create the first admin through a documented one-time bootstrap command or approved identity provisioning. Prefer institution OIDC/SSO later if available; keep identity adapters separate from graph logic.

Required controls:

- Least-privilege server authorization, object ownership checks, campus scoping, and private asset enforcement.
- Parameterized database access and input validation.
- Safe rendering of imported names/descriptions; no unsanitized HTML from plans or user reports.
- Upload security, bounded parser resources, and rate limits.
- TLS, explicit CORS allowlist when cross-origin development is used, and production security headers.
- Carefully scoped CSP compatible with actual map assets/workers; do not use an untested blanket policy.
- Secret injection, `.env.example`, secret-free logs, dependency review, and no credentials in frontend bundles.
- Audit of edits, permissions, publishing, closures, and role changes.
- Backups encrypted where required by the deployment, plus proven recovery.

Ask for location access only in response to a relevant user action. Keep live coordinates on the client where possible; send only what is needed to resolve a start or route. Do not retain raw movement traces or precise route starts as routine analytics. Analytics must be aggregated, purpose-limited, and retention-controlled.

Before a real deployment, the university must set source-plan publication rules, analytics/issue-contact retention, accessibility approval, and any required privacy review. Treat this as an institutional deployment dependency, not an invented universal legal checklist. Make retention and deletion jobs configurable and document their defaults.

## 16. Accessibility and inclusive navigation

Two separate obligations: the interface must be accessible, and physical step-free routes must be verified. Neither implies the other.

Interface requirements include labelled controls, keyboard operation, clear focus, semantic headings/forms, sufficient contrast, non-colour route distinctions, screen-reader text directions, understandable error messages, reduced motion, and useful map-free directory/route views. Aim for WCAG 2.2 AA; document automated checks and human testing, and do not claim certification based on automated scores alone.

Map editor actions must have alternatives to dragging where practicable: selecting a node and entering coordinates, choosing endpoints through searchable lists, and using explicit move/connect controls. Keep focused controls visible above bottom sheets and fixed headers. Use comfortably sized primary touch targets and validate applicable WCAG target-size/spacing criteria. Automated checks must be supplemented by keyboard, screen-reader, zoom, and touch use.

Physical route eligibility depends on surveyed path continuity, ramp and doorway details, lift availability, allowed entrances, and passage opening times. Unknown accessibility is shown explicitly. A successful synthetic accessibility test proves code behavior, not campus accessibility.

Future detailed mobility profiles require validated dimensions and university/accessibility review. Do not present medical suitability judgments or guarantee every wheelchair configuration fits a route.

## 17. Repository structure and data spaces

Create the following paths as real working modules when their milestone starts. For future modules, record the design in documentation; do not fill the repository with empty files to imply completion.

| Path | Contents |
|---|---|
| `README.md` | What works, quick start, demo warning, setup, test and data onboarding commands |
| `LICENSE` | Owner-approved code license; dataset/plan rights are separate |
| `CONTRIBUTING.md` | Branching, review, tests, data contributions, privacy rules |
| `SECURITY.md` | Reporting procedure and supported deployment practices |
| `.env.example` | Documented nonsecret configuration examples |
| `.gitignore` | Credentials, private/raw campus files, caches, volumes, local uploads |
| `compose.yaml` | Frontend/API/worker/PostGIS local services and persistent volumes |
| `Makefile` or task runner | Setup, dev, test, seed, export, validation, build commands |
| `.github/workflows/ci.yml` | Repository-appropriate CI checks |
| `frontend/package.json` and lockfile | Compatible pinned JavaScript dependencies |
| `frontend/src/app/` | App bootstrap, providers, router, layouts |
| `frontend/src/features/search/` | Search, selection, filters, result detail |
| `frontend/src/features/maps/` | Outdoor map, floor map, coordinate adapters, overlays |
| `frontend/src/features/routing/` | Route form, segments, directions, warnings |
| `frontend/src/features/location/` | Permission-aware outdoor positioning and start confirmation |
| `frontend/src/features/qr/` | Marker landing page and optional scanner |
| `frontend/src/features/directory/` | Buildings, floors, departments, facilities |
| `frontend/src/features/issues/` | Report form and submission states |
| `frontend/src/features/admin/` | Login, editors, imports, review, closures, roles |
| `frontend/src/features/offline/` | Explicit saved route/cache controls |
| `frontend/src/components/` | Shared accessible controls and layout primitives |
| `frontend/src/api/` | Generated types/client and safe request wrapper |
| `frontend/src/lib/` | Units, formatting, geometry, configuration helpers |
| `frontend/src/styles/` | Global styles and theme tokens |
| `frontend/public/` | App icons and intentionally public app assets only |
| `frontend/tests/` | Component and interaction tests |
| `backend/pyproject.toml` and lockfile | Compatible pinned Python dependencies |
| `backend/app/main.py` | FastAPI application and lifecycle |
| `backend/app/core/` | Config, logging, errors, security, permissions |
| `backend/app/db/` | Engine/session/base and database helpers |
| `backend/app/models/` | Persistence models |
| `backend/app/schemas/` | API and ingestion DTOs |
| `backend/app/api/v1/` | Public/protected HTTP routers |
| `backend/app/services/` | Catalog, publication, issues, operations services |
| `backend/app/routing/` | Graph, eligibility, Dijkstra, reachability, snapping, costs, steps |
| `backend/app/ingestion/` | CSV/JSON/GeoJSON/plan parsers and staging validators |
| `backend/app/storage/` | Private storage and approved derivative asset adapters |
| `backend/app/worker/` | Durable ingestion job execution |
| `backend/app/cli/` | Seed, admin bootstrap, import, export, validation and recovery commands |
| `backend/migrations/` | Alembic revisions; schema changes never depend on manual SQL steps |
| `backend/tests/unit/` | Algorithms, validation, coordinate conversions |
| `backend/tests/integration/` | PostGIS/API, imports, releases, permissions |
| `tests/e2e/` | Critical browser journeys |
| `data/README.md` | Upload guide, privacy, conventions, format versions |
| `data/templates/` | Empty CSV/JSON/GeoJSON examples and data dictionary |
| `data/demo/` | Redistributable synthetic campus dataset and floorplans |
| `data/raw/campus-overview/` | Ignored incoming owner-provided overview files |
| `data/raw/floorplans/` | Ignored incoming owner-provided plans organized by building/floor |
| `data/raw/room-directories/` | Ignored incoming official lists |
| `data/raw/surveys/` | Ignored field measurements and evidence |
| `data/staging/` | Ignored temporary parsing and mapping output |
| `data/exports/` | Explicit reviewed exports; ignored by default |
| `storage/uploads/` | Ignored development private assets |
| `storage/derived/` | Ignored generated floorplan derivatives |
| `docs/product/` | Master spec, milestone scope, user stories, requirements checklist |
| `docs/architecture/` | System decisions, schema, coordinate/routing/release design |
| `docs/data/` | Data dictionary, import schemas, survey and calibration guide |
| `docs/admin/` | Editor, review, closures, issues, QR installation guides |
| `docs/operations/` | Deployment, backup/restore, incident handling, ownership |
| `docs/testing/` | Verification evidence, route test matrix, pilot results |
| `docs/research/` | Optional timetable/ML/positioning designs and evaluation |
| `scripts/` | Repeatable setup, migration, synthetic generation, validation tasks |
| `infra/` | Production container/reverse-proxy examples and provider-neutral config |
| `legacy/c-prototype/` | Preserved existing C implementation and its original README |

Use small `.gitkeep` files for intentionally empty incoming-data directories if useful. Real source plans and personal data must not be committed by default. Keep demo data separate from real uploads. Do not make raw files available under the frontend public directory.

### 17.1 Starter data templates

Create versioned templates for campuses, buildings, floors, places, aliases, departments, department-place associations, anchors, nodes, edges, connectors, calibration measurements, opening rules, and QR inventory. Provide a single JSON bundle schema as well as related CSV files with matching stable external IDs.

Examples of required headers:

```csv
# places.csv (actual CSV excludes this explanatory comment)
external_id,campus_code,building_code,floor_code,place_code,name,kind,description,visibility
```

```csv
# nodes.csv
external_id,campus_code,kind,coordinate_frame,floor_code,longitude,latitude,x_px,y_px,label
```

```csv
# edges.csv
external_id,campus_code,from_node,to_node,kind,distance_m,distance_status,baseline_traversal_s,accessibility_status,connector_external_id,physical_path_external_id
```

Exactly one coordinate representation is valid per node. Outdoor geometry belongs in GeoJSON or a clearly documented JSON field; indoor polyline points belong in the declared local frame. CSV fields containing JSON must use standard CSV quoting. A scalar edge CSV alone is insufficient to describe curved path geometry: provide a companion geometry file keyed by edge external ID.

Bundle metadata includes schema version, units, campus timezone, source rights, frame definitions, and calibration. Provide a sample upload checklist and validation CLI so the owner can prepare data before using the web editor.

## 18. Demonstration data and missing-data behavior

Create a wholly synthetic campus called “Demo Campus,” with visible demo branding and coordinate/shape disclosure. Do not portray it as the owner's campus. Real production mode must not automatically seed fictional locations.

Minimum demonstration dataset:

- Three buildings, outdoor gate, library, café, water point, and washroom destinations.
- At least two floors in one building, labelled rooms, corridors, and door anchors.
- Multiple outdoor junctions and shaped walking paths.
- One ordinary stairs route and one longer verified synthetic step-free route using a lift/ramp.
- Multiple building entrances with different costs or access conditions.
- A one-way passage, closed segment, restricted area omitted from public projection, and deliberately isolated destination.
- At least one QR marker tied to a known floor landing.
- Calibrated synthetic floorplan images, transparent provenance, and expected route outputs.
- Test scenarios for lift closure, duplicate room names, rejected imports, no route, and expired/stale cached route.

Separate ordinary showcase data from invalid test fixtures so the normal demo remains understandable. Include no real student records, personal contact details, or confidential drawings.

When real data is absent, show an onboarding checklist to admins and a truthful public demo/empty state. Never generate an actual-campus route using guessed corridors. Real campus migration should be an import into a new campus/draft followed by verification, not renaming Demo Campus.

## 19. Testing and release acceptance

### 19.1 Algorithm tests

Test shortest cost on known graphs, directed paths, multiple anchors, disconnected nodes, same start/end, cycles, unreachable destinations, alternate entrances, stairs exclusion, unknown accessibility exclusion, closure overlays, and release version isolation.

Use generated small graphs and an independent reference method or trusted oracle to compare optimal path costs. Test that all returned edges exist, directions match, total costs equal edge costs, and no forbidden edge appears. Invalid negative, infinite, NaN, or malformed inputs must fail validation.

Test coordinate swaps, image axis inversion, calibrated scale, path polyline length, floor transitions, and distance aggregation. If A* or client offline routing is added, compare against authoritative Dijkstra fixtures.

### 19.2 Integration tests

Use a real test PostGIS database for spatial and migration behavior. Test fresh migration, seed, import preview, transaction rollback, idempotent commit, private upload access, generated asset publication, draft isolation, review invalidation, concurrent edits, publication failure, rollback, and closure preservation.

Verify every role and campus boundary, not just successful admin requests. Tests must demonstrate that public search, route, map, download, and issue-detail APIs do not reveal restricted content.

### 19.3 Browser tests

- Mobile search → destination selection → calculated route → readable directions.
- Outdoor-to-indoor route with floor switching.
- QR landing page resolving the correct confirmed start.
- Denied location permission and manual fallback.
- No valid step-free route after lift closure.
- Admin creates/imports a draft, validates, reviews, publishes, and sees the changed public result.
- Saved-route offline view with stale warning; reconnect validation.
- Keyboard-only core navigation and text-only route access.
- Failed tile/image/API requests produce recoverable states.

### 19.4 Field verification

Before campus pilot, walk a documented route matrix: gate to building, building to building, entrance to room, same-floor room to room, floor transition, step-free route, QR start, and closed-path detour. Confirm actual doors, signs, distances, floor labels, opening constraints, and permitted access. Record failures and map revisions.

Code tests cannot verify a physical corridor exists. The university/map owner must approve the surveyed dataset for its intended audience.

### 19.5 Initial quality targets

Treat these as benchmark targets to measure on declared hardware and networks, not claims already achieved:

| Metric | Initial target and measurement conditions |
|---|---|
| Search API | p95 under 300 ms for 10,000 public searchable places in a warmed local/staging benchmark |
| Route API | p95 under 500 ms on a 10,000-node/30,000-directed-edge warmed graph under a documented pilot load |
| Pilot load | Start with 20 concurrent route/search users; raise only after measurement |
| UI | Usable at 360 px width; core content works under throttled mobile network tests |
| Core assets | Lazy-load admin/map-heavy code; set and report a compressed bundle budget |
| Route correctness | All approved acceptance fixtures satisfy hard constraints and expected optimum cost |
| Pilot map quality | All published pilot destinations have verified anchors or clearly disclosed routing-unavailable status |
| Recovery | Perform and document a successful database + asset restore before pilot launch |

Do not choose performance optimizations before profiling. Spatial indexing, immutable graph caches, map viewport filtering, search indexes, and lazy loading are the initial tools. Re-run affected tests after substantive changes rather than adding tests that merely mirror implementation lines.

## 20. Delivery milestones and dependencies

### Milestone 0 — Specification, repository, and executable foundations

Deliver repository setup, architecture decisions, environment examples, data dictionary, synthetic fixture design, Compose/PostGIS setup, migrations, and running frontend/API health page. Preserve legacy code if supplied.

Acceptance: a new developer can run documented setup without secret credentials; frontend reaches API; database migrations work; demo mode is explicit; requirements checklist exists.

### Milestone 1 — Working outdoor navigation vertical slice

Deliver synthetic campus dataset, public directory/search, outdoor map, manual start/destination, Dijkstra, typed route response, path polyline display, measured synthetic distance/baseline ETA, no-route handling, and basic test suite.

Acceptance: changing imported graph data changes actual computed routes; directions respect edge connectivity; no hardcoded route list; tests cover weighted routing, directed paths, and invalid data. Public routing needs no login.

### Milestone 2 — Real data onboarding and controlled administration

Deliver admin authentication/roles, campus/catalog CRUD, draft revisions, CSV/JSON/GeoJSON preview and imports, outdoor editor, validation, review/publication, approved public projections, audit, and concurrency protection. Owner can upload actual campus outdoor data.

Acceptance: editor changes remain invisible until approved publication; import failure rolls back; a reviewer can compare/approve changes; anonymous users cannot access draft/restricted data; published route uses a coherent release.

### Milestone 3 — Indoor and building-to-room navigation

Deliver floorplan image/PDF upload, derivative review, local frames and calibration, floor editor, room anchors, corridor graph, entrances, stair/lift/ramp connectors, multi-floor route segments, floor selector, and verified step-free profile.

Acceptance: outdoor start reaches a synthetic room through an actual connected entrance and corridor model; floor transitions display correctly; unknown/unavailable lift paths are not treated as verified step-free; no routes cross unconnected walls in surveyed pilot data.

### Milestone 4 — Operational navigation service

Deliver QR creation and printable signs, marker lifecycle, outdoor geolocation/fallback, closures and lift outages, issue triage, cached saved routes/PWA, safe reconnection, search/facility refinements, role coverage, performance measurements, and operational documentation.

Acceptance: lift closure changes the eligible route; cached routes show freshness limitations; QR retirement is handled; raw source plans stay private; outage and rollback do not erase closures; no feature claims continuous indoor position.

### Milestone 5 — University pilot, deployment, and handover

Deliver real campus pilot dataset and evidence, installed/tested QR markers where authorized, institutional map approval, chosen hosting configuration, TLS/domain if authorized, backup/restore evidence, support ownership, accessibility testing, and pilot feedback report.

Acceptance: selected real routes are physically walked and verified; operations owner can publish a closure and restore service from backup; deployment is documented and observable. Missing institutional approval or credentials is reported as a deployment blocker, not as unfinished application code.

### Milestone 6 — Adoption and selected extensions

Expand verified buildings/floors gradually; choose extensions according to actual user demand and available data. Timetable, ML ETA, natural-language interface, full offline routing, crowd-aware routing, and indoor positioning are separate workstreams with independent acceptance criteria.

No milestone date is guaranteed. Indoor mapping and verification often take more effort than shortest-path coding. Plan one building and a manageable outdoor corridor first. Record actual effort and extrapolate from surveyed floor/building complexity rather than promising every building in a fixed number of weeks.

## 21. Optional extensions with concrete integration plans

### 21.1 Timetable and next-class navigation

Use an authorized official export/API or owner-provided CSV. Model course/cohort sessions, room references, timezone, term dates, recurrence, cancellations, holidays, and changed room assignments. Support a cohort selection before assuming individual student data is necessary.

Display next scheduled class and its verified destination; calculate travel from a user-confirmed start. An unresolved room code prompts mapping review rather than creating a fictional location. Schedule conflicts and stale feeds are visible. Do not scrape restricted student portals or fabricate an integration.

Acceptance: import a synthetic timetable, resolve room IDs, handle a moved/cancelled class, show correct next session across day boundaries, and navigate to the new destination. Personal schedules and notifications need consent, approved identity/data access, and appropriate privacy controls.

### 21.2 Grounded natural-language assistance

Support intents such as “Where is the library?”, “Take me to AB2-204,” and “Find the nearest drinking-water point.” The AI may resolve intent and candidate places; deterministic tools execute search and routing against published data. Ambiguous results ask for clarification.

Do not let a model invent rooms, draw routes, approve accessibility, execute arbitrary SQL, edit maps, or override closures. Use a fixed allowlisted tool contract. Keep source plans and user location away from external AI providers unless an approved design permits it. Keep ordinary search and navigation available with AI disabled.

Acceptance: evaluate a labelled set of campus questions, ambiguous room names, nonexistent places, malicious prompts, restricted-location requests, and unavailable provider behavior. Report accuracy and clarification rate. A chatbot alone is not proof of improved navigation.

### 21.3 ML walking-time prediction

First establish a non-ML baseline: measured distance divided by profile speed, plus connector delays. Collect only consented, quality-controlled observations, preferably aggregated by segment with appropriate removal of identifying information. QR start/arrival intervals contain waiting and stoppages; they are noisy observations, not precise walking labels.

Potential features: path distance, connector type, floor change, slope, weather if sourced, time bucket, and permitted aggregate crowd observations. Start with a simple regression/gradient-boosted model before deep learning.

Split train/test by user or session and time to avoid leakage; evaluate MAE, tail error, calibration, improvement over baseline, and poor-data cases. Use bounded nonnegative predictions, uncertainty, model versioning, drift monitoring, and deterministic fallback. If predicted weights change routes, freeze a model/feature snapshot per request and maintain graph algorithm assumptions.

Acceptance: meaningful held-out improvement with documented sample size, consent, data quality, and model limitations. No artificial demo traffic counts as real campus validation.

### 21.4 Crowd-aware and weather-aware navigation

Requires actual authorized sources with timestamps, geographic coverage, and confidence. Manual generic “crowd levels” or fabricated numbers are not a live feed. Expire stale observations and revert to baseline when unavailable.

Weather preferences can favor covered routes only if coverage attributes are surveyed. A less-crowded route remains an estimate. Do not publish individual movement paths or infer sensitive activities. Evaluate route usefulness and privacy before launch.

### 21.5 Indoor positioning research

BLE beacons, Wi-Fi fingerprinting, inertial/PDR methods, and UWB require different hardware, surveys, native/browser capabilities, maintenance, and permissions. Do not assume an ordinary browser can scan arbitrary Wi-Fi fingerprints or continuously access BLE ranging on all phones.

Create a separate feasibility study with hardware inventory, platform support, battery costs, calibration effort, floor-identification accuracy, median/p95 error, failure modes, and comparison with QR/manual positioning. Core navigation must remain usable when this research fails or is unavailable.

### 21.6 Assisted floorplan extraction

Investigate OCR for room codes and vision/vector parsing for candidate corridor/door geometry. Evaluate against manually verified plans, include missed doors/false connections, and keep all output unapproved until review. Sensitive plans may require fully local processing. Never publish an automatically inferred corridor directly.

### 21.7 Service management and integrations

Map reports may be connected to an institution's approved service desk later. Use explicit mapping of report categories and status, deduplication, scoped credentials, and retry-safe delivery. This is distinct from the legacy C request queue and should not evolve into an unrequested ERP/help-desk platform.

Optional university APIs, calendars, notifications, and SSO each require their own access owner and tested adapter. The adapter should fail safely without taking core routing offline.

### 21.8 Multi-campus and native apps

Data is already campus-scoped. True multi-campus support adds campus-specific branding, boundaries, timezones, roles, releases, operations owners, and tenant-isolation tests. Do not create cross-campus walking routes automatically.

A dedicated mobile app may reuse the API after PWA adoption demonstrates a need for native sensors, background operation, or distribution. Native apps do not by themselves solve indoor localization or missing map data.

## 22. Operations, maintenance, and cost model

### 22.1 Routine operations

- Reverify high-use paths, QR signs, accessibility claims, and entrance rules on a defined schedule.
- Reverify immediately after construction, room reallocation, lift changes, or reported map defects.
- Maintain closure start/end and reopen approval; auto-expiry must follow operator policy, not blindly assume a lift is repaired.
- Monitor API errors, route latency, no-route rates, import failures, active-release checksums, storage, and worker backlog.
- Track map coverage and known gaps separately from software uptime.
- Review dependencies and deploy updates with rollback options.
- Keep audit retention, privacy retention, and backup retention documented.

### 22.2 Backup and recovery

Back up database, private/derived assets, release manifests, and configuration references consistently. Do not back up secrets into public exports. Define pilot recovery targets with the service owner; an initial proposal is daily backups with a one-business-day recovery objective, subject to actual requirements and tested capacity.

Provide restore commands and a drill to verify map assets and active release match restored database state. Verify that closure information is restored/reconciled. Protect backups from unauthorized access and confirm deletion/retention policy.

### 22.3 Cost categories

Do not promise free permanent hosting. Document frontend/API hosting, database, storage, backups, traffic, basemap provider, domain, QR printing, survey labor, support, and optional AI/sensor cost. Include a cost worksheet using measured storage/requests and current provider quotes at deployment time; this specification provides no unverified price estimate.

Largest non-cloud effort may be drawing review, corridor tracing, calibration, field verification, and ongoing maintenance. Limit the initial mapped area so those tasks are achievable.

### 22.4 Documentation deliverables

Required documentation: setup guide, architecture decisions, data dictionary, input templates, API reference, routing design, coordinate/calibration guide, map editor guide, publication/rollback guide, accessibility survey checklist, QR installation guide, issue triage guide, deployment runbook, backup/restore runbook, known limitations, pilot verification report, and handover/ownership checklist.

An administrator proposal can later be derived from this specification, but it should focus on the requested university decision: pilot permission, controlled floorplan access, mapping cooperation, signage, and ownership. Do not present future research as a delivered capability.

## 23. Requirements traceability and definition of done

Maintain `docs/product/requirements-checklist.md` with stable IDs and these columns:

```text
requirement_id | requirement | milestone | implementation_paths
verification | status | dependency_or_limitation
```

Use statuses `not_started`, `in_progress`, `implemented`, `verified`, `deferred_extension`, and `blocked_external`. Verification references meaningful automated tests or field evidence. “Implemented” and “verified” are separate claims.

Seed at least these groups: PUB public interface, CAT catalog/search, MAP coordinates/rendering, DAT onboarding, ADM editor/permissions, REL publication, RTE routing, ACC accessibility, LOC geolocation, QR markers, OFF offline, OPS operations, SEC security, TEST verification, and EXT optional modules.

A core feature is done only when:

1. Its intended workflow runs with real backend/data operations.
2. Relevant permissions, invalid states, loading states, empty states, and failures are handled.
3. Data contracts, migrations, and configuration are documented.
4. Meaningful verification passes for the risks it introduces.
5. It works in the supported small-screen/browser scenario.
6. Its truthfulness, privacy, source rights, and restriction handling are enforced.
7. The README/checklist accurately describe the delivered behavior and remaining dependency.

Before declaring a milestone complete, report changed behavior, tests actually run, reproducible commands, known limits, and next milestone. If a check cannot run because an environment is missing, state that clearly; do not call it passed.

## 24. Final coding-agent execution instructions

The following instructions apply when this file is used to build the repository:

1. Read this whole specification and the repository's existing instructions. Determine whether this is a blank repository, a supplied skeleton, or an existing web implementation. Preserve legacy files and user changes.
2. Create/update the requirement checklist and document resolved assumptions. Choose the smallest architecture satisfying the current milestone and keeping the specified data boundaries intact.
3. Do not replace a working project with an unrelated framework without a documented reason. Use the React/TypeScript, Leaflet, FastAPI, PostgreSQL/PostGIS defaults unless the repository or owner supplies a stronger constraint.
4. Implement an end-to-end outdoor routing slice early. Map UI must use actual computed graph routes, not prewritten coordinates selected by a dropdown.
5. Treat all real campus data as external input. Create synthetic fixtures and owner-ready upload spaces, templates, and instructions. Never imply that demonstration paths represent the actual college.
6. Separate raw assets, editable drafts, approved releases, and live closures. Enforce permissions on the server and asset layer.
7. Centralize units and coordinate conversion. Use tests to prevent longitude/latitude swaps, indoor axis mistakes, uncalibrated distance, and invalid floor connections.
8. Use hard constraints for verified accessibility and access restrictions. Preserve honest no-route outcomes. Avoid “best effort” fallback through prohibited paths.
9. Keep core navigation independent of accounts for the public, AI, timetable integrations, sensors, and paid API credentials.
10. Do not create empty extension modules and claim those features exist. Write future designs and create working extension code when its milestone/data gate is reached.
11. Use staged validated imports and atomic publication. Make failed jobs retry-safe and recoverable; do not mutate live graph rows ad hoc.
12. Generate typed API contracts and meaningful tests. Use a real PostGIS integration environment for spatial behavior and browser tests for critical journeys.
13. Record actual checks and evidence. Fix correctness, security, accessibility, and data-integrity failures before adding cosmetic or speculative features.
14. Keep code readable for a student team. Explain algorithm reasoning, domain decisions, and operational workflows in documentation rather than scattering large tutorial comments through components.
15. Make local development reproducible with a short command sequence. Provide isolated test setup, idempotent demo seeding, and a one-time admin bootstrap procedure with no default public credentials.
16. Build production configuration and runbooks before deployment. Request missing hosting/identity decisions only when they block that concrete step; useful local work should continue.
17. Finish each milestone's acceptance criteria and report its exact scope. Continue incrementally when authorized; do not falsely represent the future-state report as a finished campus-wide deployment.

### Suggested first message to Codex after attaching this file

> Use the attached master specification as the product requirements. Build Milestones 0 and 1 completely, including the repository structure, PostGIS migrations, synthetic demo campus, data templates/upload directories, React/Leaflet map, FastAPI search and routing endpoints, real Dijkstra route computation, mobile UI, meaningful tests, and setup documentation. Preserve my existing C prototype under `legacy/` if present. Establish the draft/release and coordinate foundations needed by later milestones, while implementing only the workflow necessary for this first complete slice. Keep a requirements checklist and show me what works, what was tested, and which later milestones remain. Use synthetic data until I provide official campus maps and floorplans.

### Suggested continuation message

> Continue with the next incomplete core milestone in the master specification. Inspect the current requirement checklist and implementation before changing anything. Complete its end-to-end workflow and acceptance tests, update the documentation/checklist, and preserve already-working behavior. Do not substitute a mockup for a backend feature or treat a missing real campus dataset as permission to invent one.

## 25. Technical reference notes

These sources were checked while preparing the specification. They support specific implementation boundaries; they do not certify a deployed system. Consult current official documentation when coding and selecting package versions.

- Leaflet local/non-geographic coordinates and floorplan image rendering: [Non-geographical maps](https://leafletjs.com/examples/crs-simple/crs-simple.html) and [Overlays](https://leafletjs.com/examples/overlays/). The specification uses separate indoor map frames because a plan's pixels/map units are not latitude/longitude.
- Outdoor distance and coordinate transforms: [PostGIS ST_Distance](https://www.postgis.net/docs/manual-dev/en/ST_Distance.html), [ST_Transform](https://www.postgis.net/docs/manual-dev/en/ST_Transform.html), and [ST_SetSRID](https://www.postgis.net/docs/manual-dev/en/ST_SetSRID.html). Changing a spatial-reference label is not transforming coordinates; geographic degree differences are not metre distances.
- Location permissions and deployment context: [MDN Geolocation API](https://developer.mozilla.org/en-US/docs/Web/API/Geolocation_API). Outdoor geolocation needs permission and a secure context; this does not establish accurate indoor positioning.
- PWA foundations: [MDN Service Worker API](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API). Offline functionality must be explicitly implemented and scoped; installing a PWA does not make every route/asset available offline.
- Basemap attribution, usage, and offline boundaries: [OpenStreetMap tile usage policy](https://operations.osmfoundation.org/policies/tiles/). Public standard tiles are not an unrestricted bulk-download/offline backend.
- Upload handling: [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html). Apply bounded validation, safe storage names, authorization, and private storage appropriate to campus plans.
- Interface accessibility: [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/) and [What's new in WCAG 2.2](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/). Check applicable requirements for focus, target size, dragging alternatives, forms, and text alternatives; physical route verification is a separate responsibility.

## 26. Immediate owner checklist

The application can begin with synthetic data now. For a real pilot, prepare:

- Confirmed campus identity and one selected pilot building/outdoor area.
- Authorized overview map and selected building's floorplans.
- Official room/building names and floor codes.
- A supervised walk to identify doors, corridors, stairs, lifts, ramps, and actual path connections.
- Scale/measurement evidence for distances and initial accessibility attributes.
- Approved public/private map boundary and plan restrictions.
- University sponsor, map owner, accessibility reviewer, and eventual technical owner.
- QR placement permission when signs are ready.

The first real success criterion is simple and measurable: a user can choose a verified start, search a mapped room, and follow a correct route there on a phone. Campus-wide coverage, timetables, AI, and indoor positioning can grow from that verified foundation.

## 27. Configuration, reproducible commands, and deployment gates

### 27.1 Configuration contract

Document these settings in `.env.example` and the deployment guide. The exact variable names may be adapted to existing repository conventions, but the responsibilities must remain explicit.

| Setting | Required behavior |
|---|---|
| Application environment | Distinguish development, test, staging, production; production refuses unsafe demo defaults |
| Public application URL | Canonical HTTPS origin used for QR signs and share links |
| Database connection | Secret server-only connection string with appropriate pool settings |
| Session configuration | Server-only secret, cookie security, session TTL and revocation policy |
| Allowed origins/proxy trust | Explicit dev origins and trusted production proxy configuration |
| Storage root/provider | Private source path/bucket and controlled approved-asset delivery |
| Basemap URL/token/attribution | Provider settings, permitted uses, visible attribution; browser tokens restricted appropriately |
| Upload limits | Bytes, pixel count, PDF pages, row counts, parser time and job concurrency |
| Default walking policy | Speed assumptions, connector delays, step-free verification rules |
| Location thresholds | Maximum age, acceptable accuracy, campus proximity and snapping bounds |
| Graph/cache budgets | Bounded graph/query caches with release/overlay version checks |
| Offline policy | Saved route expiry, storage budget, allowed public asset types |
| Retention policy | Issue contacts, audit events, jobs, caches, backups, and deletion jobs |
| Demo controls | Explicit seeded demo campus; never auto-seed production |
| Feature flags | Timetable/AI/offline pack/research features disabled unless implemented and configured |
| Logging/monitoring | Request correlation, safe log level, metrics and health checks |
| Bootstrap identity | One-time admin creation path; no hardcoded password in tracked files |

Invalid or missing production settings should cause a clear startup failure rather than silently enabling insecure fallbacks. Browser-facing variables must be intentionally public. A prefix such as `VITE_` does not protect secrets.

### 27.2 Expected development commands

Provide runnable documented commands or task equivalents for:

```text
setup                  install pinned dependencies and explain prerequisites
dev                    run frontend/API with the documented database
migrate                apply versioned migrations
seed-demo              idempotently create the synthetic campus
bootstrap-admin        create first admin securely
test-unit              run algorithm and component tests
test-integration       run isolated PostGIS/API tests
test-e2e               run browser journeys against the test stack
check                  run formatting/lint/type checks
build                  produce frontend and backend/container artifacts
validate-dataset       validate an import bundle without publishing it
import-dataset         stage/preview/commit an authorized draft import
export-release         export the public approved dataset/manifest
backup                 create a documented consistent backup
restore                restore into a specified recovery environment
```

These are required command responsibilities, not a claim that any command already exists. Provide the actual names/options in the generated README. Destructive development reset commands must be explicitly scoped and must not target production by default. Tests use isolated database names/schemas and storage roots.

### 27.3 Production deployment gate

Before launch, verify compatible runtime versions, dependency lockfiles, migrations, database permissions, private storage, release assets, canonical origin, TLS, secure cookies, reverse proxy headers, worker execution, cleanup jobs, bounded requests, monitoring, backup/restore, and rollback.

Record approved campus map audience, named owner, pilot route evidence, unresolved coverage gaps, QR validation, and accessibility claims. Do not publish guessed campus data to satisfy a software deployment checklist. A working synthetic demo can be deployed and explicitly labelled as such if the owner requests it.

Database migrations must be run as a controlled deployment step. Avoid each API worker attempting concurrent schema changes at startup. For potentially destructive changes, supply backup/rollback or forward-recovery instructions and preserve existing data.

### 27.4 Replacing a floorplan or changing topology

A new image may have different scale, crop, orientation, or dimensions. Create a draft map-layer revision; do not swap its storage URL under existing node coordinates. Recalibrate and transform/retrace affected geometry with review, then rerun route/asset checks. QR marker anchors may need reassignment.

Stable place identity can survive a room relocation while its floor/anchors change in a new revision. Stable edge IDs should represent the same physical feature; materially new paths should receive new IDs and explicit closure/QR reconciliation. Save change reasons so rollback and issue history remain interpretable.

## 28. Concrete acceptance scenario matrix

Use synthetic fixtures first, then repeat applicable scenarios during field verification. The following outcomes are required; they provide a common basis for coding tests and pilot demonstrations.

| ID | Scenario | Expected behavior |
|---|---|---|
| RTE-01 | A–B–D costs 200 m; A–C–D costs 140 m | Shortest profile chooses the 140 m path regardless of hop count |
| RTE-02 | An entrance permits A → B only | Reverse routing cannot traverse B → A unless a separate edge exists |
| RTE-03 | Destination has two doors, one unreachable | Eligible reachable door is selected automatically |
| RTE-04 | Start and destination resolve to the same place/anchor | Successful zero-distance result with arrival message |
| RTE-05 | Searchable room lacks a mapped door | Detail remains searchable; routing reports unavailable |
| RTE-06 | A restricted corridor provides a shorter path | Public routing excludes it and does not expose its geometry |
| ACC-01 | Stairs are shortest; lift route is longer | Verified step-free profile chooses the eligible lift route |
| ACC-02 | Lift closes and stairs are the only alternative | No verified step-free route; no silent stairs fallback |
| ACC-03 | Ramp is marked unknown rather than verified | Verified profile excludes it and displays data limitation |
| MAP-01 | Outdoor GeoJSON point is converted for Leaflet | Longitude/latitude order remains correct through roundtrip |
| MAP-02 | Image has a 200 px calibrated line representing 10 m | Uniform-scale factor is 0.05 m/px; calibrated path distances use it |
| MAP-03 | Nodes are on different local floor frames | Distance never comes from subtracting the two frames' coordinates |
| MAP-04 | Polylines cross without a declared connection | Route cannot turn between them |
| DAT-01 | Edge import references an absent node | Preview lists the row error; commit rejected without partial changes |
| DAT-02 | Same bundle is imported twice | No duplicate entities/edges; idempotent result |
| DAT-03 | Uploaded source contains sensitive plan details | Private original remains inaccessible publicly; only reviewed derivative can publish |
| ADM-01 | Two editors submit conflicting entity versions | Second stale write gets conflict and reconciliation UI |
| REL-01 | Approved draft changes after review | Previous approval invalidated; cannot publish silently |
| REL-02 | Publication asset generation fails | Existing release remains active and coherent |
| REL-03 | Rollback occurs during a live lift outage | Outage stays active or requires explicit unresolved-target review |
| SEC-01 | Anonymous user requests draft/source asset | Access denied without exposing private contents |
| SEC-02 | Editor assigned to Campus A modifies Campus B | Server rejects unauthorized action |
| LOC-01 | Location permission denied or coordinates too inaccurate | Manual/QR start selection stays usable |
| LOC-02 | Nearest geometric path is behind a wall | No unverified shortcut; confirm a surveyed start landmark |
| QR-01 | Scan active verified marker | Show correct campus/building/floor label and confirmed start |
| QR-02 | Scan revoked or unmapped marker | Clear retired-marker state; permit manual start selection |
| OFF-01 | Open previously saved route with no network | Cached route/directions render with closure freshness warning |
| OFF-02 | Request a new route offline without routing pack | Honest connection-required state; no fake computation |
| OPS-01 | Closure overlay changes in a multi-worker service | New route uses current overlay version consistently |
| UI-01 | Navigate with keyboard and text route only | Search, selection, route calculation and instructions are usable |
| UI-02 | Basemap tiles fail but route data exists | Text instructions and available campus layers remain usable |
| EXT-01 | Timetable room allocation changes | Future timetable module resolves and routes to updated room |
| EXT-02 | AI proposes an unknown place | Future AI interface clarifies/fails safely; no invented destination |
| EXT-03 | ML model/data source unavailable | Future ETA module uses documented deterministic fallback |

### Pilot demonstration sequence

1. Search a named building and show an outdoor route calculated from graph data.
2. Search a room with a duplicate number in another building and select the correct result.
3. Route into the building and switch between floor segments.
4. Compare shortest and verified step-free routes.
5. Apply a lift closure as an authorized maintainer and recalculate.
6. Scan a QR marker and confirm the start.
7. Show a saved route offline with the freshness limitation.
8. Demonstrate a draft edit, validation, review, and atomic publication.
9. Report a map issue and show authorized triage.
10. Explain measured pilot coverage and remaining data gaps honestly.

This sequence demonstrates the product's data, algorithms, administration, and practical reliability without depending on speculative research features.
