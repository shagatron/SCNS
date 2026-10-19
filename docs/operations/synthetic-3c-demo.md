# Unpublished synthetic 3C demo — one-command local setup

This helper prepares **a new, separate draft** of the assigned synthetic campus using the current published release as its parent. It never selects or edits Draft3, never replaces existing ACA floors/plans/tracing, and never submits, publishes or rolls back a release. Both new floors, source titles, entrance places, room names and connector labels explicitly say **Synthetic 3C demo**. Record IDs are deterministically namespaced to this demo run. All supplied scale, costs and accessibility assertions are invented test data, not surveyed campus claims.

## Windows PowerShell command

Use the **updated existing checkout on `feat/milestone-3c-indoor-routing`**, Docker Desktop running **Linux containers**, Compose v2, and a regular interactive PowerShell console. Inspect/preserve local changes before a fast-forward Git update; do not reset or discard them. Existing installation must already have a published synthetic Demo Campus with ACA, Main Gate, Library, Central and its outdoor graph, and your two assigned accounts. No bootstrap or seed is needed. From the repository root run exactly:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\setup-3c-demo.ps1
```

`RemoteSigned` applies only to this child process; it does not change your machine's execution policy or application approval checks. The script builds API/frontend **before** stopping API/worker, ensures the existing DB is running, migrates **forward**, starts the local app/actual worker and opens the interactive helper. It stops on a failed Compose/build/migration/helper command. Ports remain loopback-only. `.env` is not rewritten, existing accounts are reused, and both named database/private-upload volumes remain intact. There is a brief API interruption during update. No environment publication, deployment or paid service is involved.

When the current images/services are already updated and healthy, the equivalent helper-only command is:

```powershell
docker compose run --rm --no-deps api python -m app.cli.indoor_demo
```

Do not use `-T`, pipe input, put passwords in commands/environment variables, or record terminal input. The helper refuses noninteractive or echoing password fallback. It accepts only the local API, bypasses HTTP proxies for this local traffic, and refuses redirects.

## Credentials and approvals

1. Enter the **existing owner/editor username and hidden password**. The account needs campus-scoped draft-create/catalog-edit/review-submit permissions. If more than one assigned synthetic campus exists, choose its displayed number. Real campuses are refused.
2. After the first worker-processed plan is applied/calibrated, enter the **existing independent reviewer username and hidden password**. The reviewer must be a different account with current campus-scoped source/calibration approval permission. Those normal API endpoints enforce separation of duties and exact derivative integrity; the helper never writes approval flags or accesses the database.
3. Credentials and session/CSRF tokens stay only in process memory, never in the journal, command arguments, files or output. Helper-created sessions are logged out on exit where the API is reachable. A completed rerun needs only the owner login; existing approvals are checked for live validity. Normal login/logout audit records still occur.

The reviewer is approving only the explicitly synthetic masked plan and its calibration. Full draft review/publication remains a separate deliberate workflow. An unavailable or unsuitable reviewer causes a safe stop with already-completed work retained; never use owner credentials as the reviewer.

## Automated data and expected results

For each of **D3C_Ground / Synthetic 3C demo Ground** and **D3C_Upper / Synthetic 3C demo Upper** in ACA, the helper:

- Uploads `data/demo/floorplans/synthetic-ground.png` with synthetic rights/provenance, page1 and mask `(480,320,100,60)`. The actual combined import/floorplan worker renders and sanitizes the image. The helper decodes the returned600×400PNG and verifies the white mask before applying; it never fabricates a ready job or approval.
- Applies to the new floor only, with no replacement/reset. Records primary `(100,100)→(300,100)=10m` and independent check `(100,100)→(100,300)=10m`, uncertainty0.05m, uniform quality, synthetic date2026-10-01. Scale is0.05m/reference-pixel; elevations/heights remain unknown.
- Requests normal independent sanitized-source and exact-calibration approvals. Previews and saves namespaced `ground.json` / `upper.json` tracing through the indoor editor API. The same source image describes two separate test frames, not identical real floors.
- Adds **two new labelled demo entrance places and anchors**, using the original explicit ACA entrance's outdoor node and the stored public Central node respectively. It does not change the original ACA place/anchors or infer geography from floor pixels.
- Binds `connections.json` to the new floors/current layers/building/anchors and namespaced stored nodes. Previews/saves four groups (stairs, lift, west/east entrances), directed stops/traversals and metric floor policies. Unknown width/slope/step count/heights remain null. Synthetic stairs are6m/12s/not-step-free; lift15m/8s movement+20s wait/step-free; entrances2m/12m with3s movement.
- Runs authoritative whole-draft validation with **14 route cases**: both profiles for Ground101→102, Upper201→202, Ground101↔Upper201 and MainGate↔Upper201, plus two explained no-route cases Ground101→ISO. Distances come from Dijkstra over saved geometry/traversals. It asserts18m same-floor,36m shortest across floors/stairs and57m step-free/lift against the computed evidence.

Expected output identifies **Draft N and its UUID**, completed steps, a validation UUID, computed18/36/57m results, and a private resume-journal path. In the isolated built-worker check, validation returned **0 errors /70 warnings**; warning counts can differ with the cloned published dataset. Warnings include intentionally incomplete/unknown and disconnected synthetic coverage. They are not automatically acknowledged. Restricted R1/R2 stay private; ISO deliberately lacks a connected corridor. Public Main Gate→Library continues on its current release (original fixture256.88m/three stored edges); indoor demo rooms remain absent from public search/maps/routes.

Open `http://localhost:5173/admin`, select the printed **Draft N**, inspect its two labelled floors in **Floors and floorplans**, graph in **Indoor floor editor**, groups in **Connections and entrances**, and exact computed evidence/diagnostics in **Review and releases**. Do not confuse this draft with existing Draft3/ACA Ground. The public homepage remains `http://localhost:5173/` with the existing published release.

## Reruns and partial recovery

One private journal per campus is stored in the retained `private-imports` volume at `/app/storage/private/local-demo-3c/<campus UUID>.json`. It contains only IDs, fixture fingerprint, step results and expected draft version; file permissions600, directory700, atomic fsynced writes and an exclusive lock. Keep it with private storage/backups; do not commit/export it as public data or delete it to force another run. The same owner and fixture fingerprint are required on resume.

Rerun **the same command** after a terminal interruption, API interruption or worker wait. Applied steps are reused. Uploads have stable normal-service retry keys; draft creation has an actor/campus-scoped `Idempotency-Key` saved in the append-only audit. Lost successful apply/edit responses are reconciled against actual saved content and the one expected version increment. A completed rerun creates no new draft/floors/jobs/tracing/anchors/connectors/approvals/validation runs, apart from normal authentication audit/session activity.

The helper waits up to120s per worker job. A still-running job is retained; verify `docker compose ps` / worker readiness and rerun. A failed job is reported by UUID; inspect its private status in **Floors and floorplans**, use the normal **Retry** control if eligible, and rerun. Cancelled jobs, changed fixture versions, missing/invalid journals, changed public baselines, externally edited demo drafts and frozen/submitted drafts stop for manual reconciliation; existing data is not replaced. Version conflicts are never retried as blind upserts. Do not edit the demo concurrently with setup. Preserve the journal and use its draft/job IDs with the normal dashboard/audit controls; do not hand-edit its version to ignore a user change.

The helper validates the **whole cloned draft**, so previously published indoor capabilities or source approval changes can produce additional blocking diagnostics needing their own evidence. It reports partial completion and returns nonzero when checks fail. No failure removes existing uploads/volumes or rewinds migrations. Inspect exact retained diagnostics before review; changing the parent or working draft is a deliberate separate decision.

## Remaining review/publication actions — not automated

The result stays **draft/unpublished**. Inspect source rights, sanitized plans, calibration, restricted projection, topology,14route results and all other cloned capability diagnostics. Resolve errors and independently assess/acknowledge each warning with a substantive reason. If you later explicitly choose publication: submit exact validated current content, have an independent authorized reviewer inspect/approve the submission, then deliberately confirm publication against the expected active release. The helper does none of these actions. Until then, draft route evidence is the way to inspect indoor routing; the public planner cannot route these unpublished rooms.

## Checks

```bash
make check build test-unit test-integration test-migrations generate-api
python scripts/cloud-build.py                         # cloud TLS/proxy helper; local: docker compose build api frontend
python scripts/smoke-3c-demo-containers.py             # built API + actual worker, unique disposable test DB only
pwsh -NoProfile -File scripts/test-setup-3c-demo.ps1   # mocked Docker argument/failure checks; no developer writes
```

Built smoke verifies independent HTTP approval/audit, actual masked processing, retained approved/calibrated tracing and separate Draft3 preservation, lost-response recovery, duplicate-free reruns, stale-edit refusal,14computed routes and unchanged public release. Existing M3C browser evidence remains valid: no frontend behavior changed (only the generated optional draft retry-header contract). PowerShell syntax/control-flow was exercised on Linux; **actual Windows Docker Desktop/PowerShell5.1 and your installation/accounts were not executed in cloud**. Official maps/surveys and real accessibility remain external inputs; no M4 work.
