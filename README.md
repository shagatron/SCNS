# Smart Campus Navigation (SCNS)

A **DSA academic project** demonstrating computed outdoor and indoor navigation, built with React/TypeScript and FastAPI/PostGIS. The public application includes a campus directory, route planner, dark outdoor maps, published indoor floor views and an original two-floor educational demo. Administration supports authenticated campus-scoped drafts, imports, graph editing, review/publication/rollback, QR markers and live restrictions.

This is a student project, **not an official university service or a field-verified navigation system**. Docker is the supported submission runtime; the abandoned native-Windows experiment remains on its separate branch and is not included in `main`.

## What is in Git, and what is not

Git contains application code, migrations, frozen dependency locks, original/attributed assets, synthetic fixtures, OSM source preparation and verification documentation. **The owner's retained Windows database, accounts, private uploads, drafts and published MUJ/E22 release are separate Docker data. Cloning this repository does not reproduce them.** Never reset/reseed an existing installation or replay imports merely to update code.

| Context | What it demonstrates | Qualification |
|---|---|---|
| Demo Campus | Stored graph, public directory/search, metric routes and synthetic accessibility cases | Entirely invented data, not a real campus |
| MUJ outdoor preview | Limited OpenStreetMap-based routes and published data workflows | Owner reports local publication/acceptance; incomplete, not institutional or physical-survey approval |
| MUJ **Indoor demo** tab | Original fictional two-floor schematics and computed traversal-count routes | **Demonstration layout — not an actual MUJ floorplan.** No real-campus connection, scale, metres, ETA or accessibility evidence |

MUJ's photo/logo remain campus-aware; the complete directory, planner, published-floor controls, QR/GPS confirmation and restrictions are retained. **Outdoor** selects the ordinary published-campus explorer, including its existing published indoor journeys. **Indoor demo** selects a separate educational graph in the same map area. Mode choices/results stay separate; legacy `/indoor-demo` links remain supported. No demo activation, account or campus publication is required for that educational content.

## Actual DSA implementation

[`dijkstra.py`](backend/app/routing/dijkstra.py) constructs a **directed adjacency list** (`defaultdict(list)`) from eligible arcs. Python `heapq` supplies the min-heap; dictionaries store best ranks and predecessor arcs, and sets identify starts/targets and duplicate IDs. Strictly better labels are relaxed and pushed as new heap entries; stale entries are skipped by comparing the popped rank to the current best rank. Predecessors reconstruct ordered nodes/edges. Multi-source/multi-target routing supports entrance choices and deterministic tie-breaking. No custom heap or unimplemented pathfinding algorithm is claimed.

[`mixed.py`](backend/app/routing/mixed.py) filters and weights published outdoor/indoor/entrance/connector arcs before calling the same engine:

- **Metric / shortest:** minimize eligible stored physical length. Outdoor OSM lengths may be **estimated**, not field measured. Unknown lengths are not guessed.
- **Directions only:** minimize **eligible traversals**, one unit per graph arc; not shortest distance or fastest time. It can return a longer physical route with fewer arcs.
- **Fastest:** minimize supported baseline traversal seconds, excluding connections without required time estimates. Walking estimates use configured speed (default1.4m/s); lift movement/wait estimates require the relevant reviewed data. This is not live travel-time prediction; fastest is unavailable with Directions only.
- **Step-free:** retain strict verified-access eligibility, exclude stairs/unknown access, then minimize the selected cost. Direction, permissions/static access, published capabilities and the current closure overlay still apply.

With V represented vertices and E eligible arcs, the **core** uses O((V+E)log(V+E)) time including deterministic sorting/lazy heap entries, and O(V+E) auxiliary space; O((V+E)log V) is a common equivalent shorthand for simple graphs. This is not an end-to-end API/database benchmark. [DSA explanation and bounds](docs/submission/dsa.md) cover adapter overhead, including current entrance-priority preparation. Stack-based DFS-style reachability is used in graph diagnostics; BFS is an equal-weight comparison, not the implemented public route engine. Unit tests compare random weighted graphs against an independent Floyd–Warshall reference.

## Stack and architecture

| Layer | Implementation |
|---|---|
| Public/admin UI | React, TypeScript, Vite, Tailwind/CSS, TanStack Query, Leaflet |
| API and services | Python3.12, FastAPI, Pydantic, SQLAlchemy, Alembic |
| Stored data | PostgreSQL17/PostGIS; directed outdoor paths, indoor frames, immutable published projections, private drafts/audits |
| Local runtime | Docker Compose; nginx frontend, API, private import/floorplan worker and database |

The UI requests the current published release; the API validates context/restrictions and builds eligible graph arcs, computes Dijkstra, then returns geometry and text directions. Draft changes remain private until the normal exact-content review/publication workflow. Original uploads stay private; approved display assets are served through controlled endpoints. The educational API is a separate no-database computation over authored demo data. See [architecture](docs/architecture/design.md), [contracts](docs/architecture/openapi.json) and [requirements/checklist](docs/product/requirements-checklist.md).

## Run with Docker

**Prerequisites:** Git, Docker Engine/Desktop with Compose v2 (Linux containers), a modern browser and sufficient disk space/network for frozen image/dependency builds. Host Python, Node and native PostgreSQL are **not required** for Docker. Default ports are loopback-only5173(frontend),8000(API) and54329(database). Do not run a second stack on those ports. No paid services, map keys or external tiles are required by default.

### Existing checkout / retained owner data

Use the complete copy-paste [Windows PowerShell main update/start block](docs/operations/academic-submission.md#existing-windows-checkout-safe-main-update-and-start) for `C:\Users\Aaditya Shah\SCNS`. It checks clean Git state, fast-forwards `main`, starts/checks the **existing database before API readiness**, builds/starts API, worker and frontend, and opens the app. It preserves `.env`, accounts, private storage, volumes, drafts, releases and the temporary phone override. Laptop startup deliberately excludes that override; no LAN access is enabled.

For an already-updated checkout on Bash/Linux, equivalent retained-data startup is:

```bash
# From repository root, using the existing default Compose project/data.
docker compose -f compose.yaml up -d --wait --no-deps --no-build db
docker compose -f compose.yaml exec -T db pg_isready -U scns -d scns
docker compose -f compose.yaml build api frontend
docker compose -f compose.yaml up -d --wait --no-deps --no-build --force-recreate api
docker compose -f compose.yaml up -d --no-deps --no-build import-worker
docker compose -f compose.yaml up -d --wait --no-deps --no-build --force-recreate frontend
docker compose -f compose.yaml ps db api import-worker frontend
curl --fail http://localhost:5173/api/v1/health/ready
```

Open **http://localhost:5173**. API docs: http://localhost:8000/docs. If the API returns database-related503s, start/check the existing database first; API-only `--no-deps` startup cannot start a stopped database. Repeat startup does not require migration, seed, bootstrap or import commands. To stop without deleting data: `docker compose -f compose.yaml stop frontend import-worker api db`.

### Fresh clone with genuinely new, empty data

A fresh clone starts with **no owner's MUJ database or private files**. The fresh-install instructions below deliberately use a separate project name. Run them only on a new installation with standard ports free. If that project's volumes already exist, stop and use existing-install startup with the same project name; never rerun initialization as an update.

```bash
set -e
git clone https://github.com/shagatron/SCNS.git
cd SCNS
ScnsFreshVolumes=$(docker volume ls --filter label=com.docker.compose.project=scns-academic-fresh --format '{{.Name}}')
if [ -n "$ScnsFreshVolumes" ]; then
  echo 'Existing fresh-project volumes found. Stop; use retained-data startup with that project name.'
  exit 1
fi
# Only for a genuinely NEW project: explicit first-time schema/demo initialization.
docker compose -p scns-academic-fresh -f compose.yaml build api frontend
docker compose -p scns-academic-fresh -f compose.yaml up -d --wait db
docker compose -p scns-academic-fresh -f compose.yaml exec -T db pg_isready -U scns -d scns
docker compose -p scns-academic-fresh -f compose.yaml run --rm --no-deps api alembic upgrade head
docker compose -p scns-academic-fresh -f compose.yaml run --rm --no-deps api python -m app.cli.dataset seed-demo ../data/demo/campus.json
docker compose -p scns-academic-fresh -f compose.yaml up -d --wait api frontend import-worker
```

These first-time commands are documented for an empty install; **they are not part of the retained-data update or this submission audit**. They create only synthetic Demo Campus, not MUJ. Public Demo Campus works without admin provisioning. `/indoor-demo` provides the compatibility educational view when MUJ is absent; do not create a fake MUJ campus to manufacture its integrated entry. Optional admin provisioning requires the separate secure [one-time admin workflow](docs/operations/admin.md), not a hardcoded/default password. Keep this project's name for subsequent startup and stopping; volumes survive `stop`.

## Presentation inputs and evidence

| Context / inputs | Expected result | Evidence status |
|---|---|---|
| Demo Campus, Main Gate → Library, shortest + metric |256.88m/3stored edges, approximately257m/4min | Automated source/API/built evidence; earlier owner Windows baseline also recorded |
| MUJ, University Entrance → Mapped entrance10828149259(E05), shortest + metric |513.10m/13edges, displayed≈513m | Source-OSM fixture calculation and owner-reported Windows acceptance |
| Same MUJ pair, Directions only / Fewest eligible traversals |799.32m/9edges, displayed≈799m; not distance minimization | Fixture calculation and owner-reported Windows acceptance |
| MUJ, Hostel Entrance → GHS Entrance; → Faculty Block Entrance, metric |23.62m/3edges;163.28m/6edges | Fixture calculation and owner-reported Windows acceptance |
| Indoor demo, Classroom A → Demo Library |3authored traversals, Ground floor | Automated real demo API/browser evidence |
| Indoor demo, A → Classroom C; reverse C → A |9traversals each, explicit stair ascent/descent and matching floor sections | Automated source/built evidence |
| Indoor demo, A → A; A → Demo Disconnected Room |0traversals without a physical metric claim; explicit no-route for disconnected room | Automated source/built evidence |

Use the exact **Demo Classroom** option names in the UI. All educational distances/ETA remain unknown. Switch floors with **View demonstration floor** or **Show First floor** in directions; hide the map and follow independent text; reload to recover the route/floor. The MUJ integrated mode is available only when that published campus exists in the local database. [Presentation-day checklist](docs/submission/presentation.md) includes QR/GPS/closure prerequisites, fallback and provenance. Unsupported real MUJ Library/cross-campus/verified-step-free routes must remain unavailable.

Owner-reported results used separate application accounts operated by the owner; **not independent human, institutional, physical-route or accessibility verification**. GPS is explicit opt-in, accuracy/freshness/path checked and landmark-confirmed; it is not continuous tracking and cannot infer an indoor floor/room. QR requires confirmation and valid installation/revocation state. Closure freshness and fail-closed checks remain active; an estimated end never proves reopening.

## Checks, operations and limitations

```bash
npm run check --workspace frontend
npm test --workspace frontend
npm run build --workspace frontend
UV_CACHE_DIR=/tmp/scns-uv-cache uv run --directory backend --frozen pytest -q tests/unit
```

Host checks require the locked developer dependencies (`uv sync --frozen` in backend; root `npm ci`), Python3.12or3.13 and Node22.12+(container uses24). See [contributing](CONTRIBUTING.md) for optional source development, [latest verification](docs/testing/verification.md), [integration evidence](docs/testing/educational-indoor-demo.md#explorer-integration-adjustment--final-evidence) and [submission audit](docs/submission/audit.md). Database/browser fixture runners modify **only their explicitly owned disposable test resources**; never point them at the owner's database. No new deployment or performance certification is claimed.

Useful guides: [admin](docs/operations/admin.md), [imports](docs/operations/imports.md), [graph editor](docs/operations/graph-editor.md), [publication/rollback](docs/operations/publication.md), [indoor routing](docs/operations/indoor-routing.md), [QR](docs/operations/qr-markers.md), [GPS](docs/operations/geolocation.md), [closures](docs/operations/closures.md), [MUJ source/ODbL attribution](docs/data/muj-osm.md), [MUJ publication evidence](docs/operations/muj-publication-preparation.md), [educational viewer](docs/operations/educational-indoor-demo.md), [screenshots](docs/previews/educational-indoor/integrated/README.md).

MUJ outdoor coverage is incomplete; OSM topology is not a field survey. Unidentified entrances remain unresolved; unknown measurements/accessibility are not filled in. The educational schematics are original and unscaled, not MUJ or copied Nalanda blueprints. Physical-device GPS, physical routes, human assistive-technology certification and the latest Windows indoor-demo update remain unverified here. Phone whole-floor labels need zoom; the previously documented brief route-button transition contrast gap remains. Reports4D/offline packs4E and deployment are outside this submission. Supplied C prototype status is recorded under [legacy/c-prototype](legacy/c-prototype/README.md).

Preserve [OpenStreetMap attribution/ODbL](https://www.openstreetmap.org/copyright), bundled Inter's OFL notice and existing asset/source disclosures. No owner-approved code license has been supplied; no license grant or institutional endorsement is invented ([licensing guidance](CONTRIBUTING.md)).

## Final report and slides

The owner-approved final documents are committed unchanged:

| Document | File / status |
|---|---|
| Final academic report, compiled PDF | [SCNS Overleaf report —22pages](docs/submission/files/SCNS_Overleaf_Report.pdf) |
| Editable final presentation | [SCNS DSA presentation —14slides(PPTX)](docs/submission/files/SCNS_DSA_Presentation.pptx) |
| Editable Overleaf/LaTeX source | Not supplied; the report PDF is the compiled output, not the source project. |
| Presentation PDF | Not supplied; the editable PPTX is not a PDF export. |

[Submission document details and verification](docs/submission/README.md). These approved documents are distinct from the school reference drawings and supporting walkthroughs. No missing source/export is substituted or linked as if present.
