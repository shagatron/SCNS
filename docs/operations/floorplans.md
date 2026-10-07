# Floors and private floorplans — Milestone 3A

3A delivers draft floor management, private PDF/image processing, floor-local preview and evidence-bound uniform calibration. It extends independent source/release review; it does not add rooms, corridors, indoor edges, entrance tracing, connectors, indoor routes, QR, location or deployment. Demo Campus and the checked-in drawings are invented software fixtures, never real MUJ data. Full two-floor navigation acceptance remains 3B/3C.

## Update an existing Windows installation without losing data

Use PowerShell in your existing SCNS repository folder with Docker Desktop running **Linux containers** and Compose v2. Preserve `.env`, your database and private-import named volumes. Use your existing admin credentials; there is no new/default password. If `git status` shows local changes, commit or otherwise preserve them before switching; do not reset/discard them. Run these commands in order and stop if a command fails. Build before stopping the old app where possible; migration failure is a reason to keep it stopped and investigate, never delete a volume or seed again.

```powershell
git status --short
git fetch origin
git switch feat/milestone-3a-floorplans
git pull --ff-only origin feat/milestone-3a-floorplans
docker compose build api frontend
docker compose stop api frontend import-worker
docker compose up -d --wait db
docker compose run --rm --no-deps api alembic upgrade head
docker compose up -d --wait --no-build api frontend import-worker
docker compose ps
Invoke-RestMethod http://localhost:5173/api/v1/health/ready
Start-Process http://localhost:5173/admin
```

Migration head is `0012_floorplans`; it adds floor/layer/job tables and guards without reseeding, changing existing accounts or moving the active release. The same `import-worker` image now also processes floorplans. Do **not** run `down -v`, database reset/downgrade, `seed-demo`, bootstrap or publication/rollback merely to update an existing installation. Floorplan originals and PNGs are private database BYTEA and belong in consistent database backups; existing staged text-import originals still use `private-imports`. This is a data-retaining local update, not a production backup/restore certification. Native Windows Python cannot run the Linux decoder sandbox: use the containers. These PowerShell commands are documented; Linux Compose execution is the automated evidence, not an actual Windows execution claim.

For an entirely new, empty installation use the README's explicit migration/demo steps and [one-time admin bootstrap](admin.md). Bootstrap prompts for your chosen password. No seed/bootstrap is needed for the existing installation.

## Draft workflow

1. Sign in at `/admin`, choose your assigned campus and an editable draft, and open **Floors and floorplans**. Create/select a building through the existing catalog first. A floor has a stable UUID, unique code within its draft building, label, ordering (`B1 = -1`, ground `G = 0` are conventions, not measured elevations), optional elevation and visibility. Blank elevation means unknown. IDs/building ownership cannot be changed by editing the floor.
2. Select a private PDF, PNG or JPEG and record title, rights, provenance, public attribution, page and optional opaque masks. `synthetic` rights require an explicitly demo campus; real sources need authorization for the intended audience. `restricted` originals cannot become public display assets. Actual signature, extension and decoded content are checked; MIME supplied by a browser is not trusted. No SVG/CAD, password-protected PDF, animated images, remote URL or arbitrary filesystem path is accepted.
3. Upload creates a private durable job. Status/history shows uploaded → processing → ready/failed, with attempts and original checksum. A ready preview does not edit or publish the draft. Inspect masks against the private original. Select another PDF page or change masks with **Create a new selected-page/mask batch**; it reuses the retained original, preserves the prior job and needs a new independent approval if later selected.
4. Explicitly apply a ready page to its target floor. Replacement requires the exact current layer ID and confirmation to clear old calibration. A referenced indoor frame cannot be replaced/recalibrated while graph-node dependencies exist; 3A does not create those nodes. Old draft layers/originals remain private history. An unselected historic derivative cannot block approval of the current page or appear in the public projection. Applying never moves the public pointer.
5. Preview using a separate floor-local map with pan, zoom and **Fit plan**. Enter or pick two endpoints for a known metric line and a nonparallel independent check line. Record actual known metres, measurement date, uncertainty and substantive evidence/quality. Confirm they refer to the current plan, then save. Software validates consistency; it does not survey a campus or infer dimensions from a building footprint.
6. A different authorized reviewer inspects the private original, masks, exact selected sanitized PNG, rights/provenance and attribution, then approves that derivative. Separately inspect/approve the calibration evidence; its author cannot approve it. A system administrator cannot bypass independence. Source and calibration approval can be by the same independent reviewer as overall review, provided that person did not edit/upload the draft content.
7. Use the existing **Review and releases** workflow: authoritative validation, computed outdoor acceptance routes, individual warning acknowledgements, exact-content submission, independent decision and explicit consequence confirmation. Public floors need an approved permitted selected derivative. Uncalibrated public plans require a display-only warning acknowledgement. All 3A floors, even calibrated ones, explicitly expose `metric_navigation=false`: no indoor distance, ETA or routing is available.

Editor/system administrator can read and edit draft floors/jobs/calibration. Reviewer/publisher can read private plans/evidence and independently approve/review/publish, but cannot edit them without an editor grant. Operations has no private draft access. Permissions, campus/revision ownership, session expiry/revocation, Origin, CSRF and draft `If-Match` are enforced server-side and rechecked after queued locks/upload streaming. Submitted/approved/frozen revisions are read-only; return/reject/withdraw through the existing workflow before editing.

## Limits, retry and recovery

| Boundary | Enforced behavior |
|---|---|
| Original upload | Nonempty, at most 10 MiB; safe PDF/PNG/JPEG filename; encoded metadata header at most 24,000 characters; nginx transports 10 MiB/32 KiB header buffer |
| PDF | Unencrypted, 1–30 pages, selected page exists; reference raster 150 DPI; every page dimension checked |
| Reference image | At most 10,000 px per side and 32 million pixels; EXIF orientation normalized |
| Public/private preview | Fresh RGB PNG, metadata removed, at most 2,048 px per side; original reference bounds retained |
| Masks | At most 20, positive dimensions, entirely inside selected reference pixels; applied opaque at reference resolution before resampling, with outward edge padding |
| Decoder child | Linux x86_64/aarch64 only, no inherited database/session/proxy environment, no ambient file opens/network/process creation; non-root when started as root; seccomp fails closed |
| Processing resources | 1 GiB address space, 20 s CPU, 30 s wall, 24 MiB output/file limit, no core dumps, bounded file descriptors/processes |
| Durable recovery | 120 s stale lease, at most three processing claims/attempts, competing workers use `SKIP LOCKED`; cancellation invalidates lease and discards late output |
| Storage | 256 MiB per campus across job original/output, layer PNG and source-original copies; existing 100 MiB source-original quota still applies at apply/clone |
| UI/catalog | First 500 floors / 1,000 buildings; job history 50/page, offset at most 10,000; explicit truncation/pagination |

Retry a failed unchanged job while attempts are below three; unsupported inputs will fail again and should be corrected as a new batch. Retry/cancel require an editable draft/version. Cancellation retains original/checksum/history and removes preview access; already applied jobs are immutable. Matching upload key + actor/campus + identical payload returns the same job; changed payload with that key conflicts. Matching apply retry cannot create duplicate source/layer rows; stale versions or different apply options conflict. Upload/page processing does not increment content version; floor edits/apply/calibration/approvals do. Every administrative change and worker completion records actor/job/checksums in transactional append-only audit, without credential values.

409 conflicts retain form input and show the latest floor/plan metadata. **Keep my inputs and reconcile latest version** reads without writing; reconfirm measurements/replacement before an explicit save. Same-tab recovery retains bounded form/page/mask/measurement metadata for two hours, keyed by user and draft. After reload choose the same campus/draft and restore inputs, then reconcile. Private file bytes and credentials are never in recovery; reselect files. Logout clears recovery. Closing the tab, storage policy/quota or expiry can remove it. No automatic draft save is claimed.

Floor deletion lists all draft layers, pending jobs and graph nodes. Cancel pending uploaded/processing/ready batches first; graph dependencies prevent deletion. Explicit confirmation must name the exact layer IDs to remove. Only those draft layer/private source copies and unused frame are removed; applied/cancelled job history/originals and all frozen release assets remain intact. Building deletion is refused while floors reference it.

## Repeatable verification

On Linux from repository root, with Docker, Python/uv, Node/npm and Chromium available:

```bash
make setup
make check build test-unit test-integration test-migrations
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium make test-e2e
make generate-api validate-dataset
python scripts/cloud-build.py             # this cloud's existing proxy/CA build helper
python scripts/smoke-publication-containers.py
```

On a normal local Docker host replace the cloud helper with `docker compose build api frontend`. Built smoke tests the built nginx/API **and image worker**, provisions only a unique disposable `*_e2e_test` database/network/containers, and removes only its owned resources. Source browser/migration harnesses reset only their guarded dedicated test databases; private import storage/accounts are temporary. Do not point any harness at developer data. Authenticated traces/screenshots/video are disabled. Results and unverified platform/field/production limits: [verification](../testing/verification.md).

Templates/contracts and coordinate formulae: [floorplan-v1](../../data/templates/floorplan-v1/README.md), [floorplan data contract](../data/floorplans.md). Neither CSV preparation templates nor the existing outdoor importer are an indoor bulk-upload API. 3B room/corridor tracing and 3C connectors/indoor routing require separate authorization; they have not started.
