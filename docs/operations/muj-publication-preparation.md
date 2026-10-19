# Existing Windows MUJ draft: limited local OSM preview review

This guide uses `feat/muj-connectivity-review` including `ee97dbc`. It prepares the **existing** campus `afcf4f1a-635f-563b-af5b-3d7efd2ed84c`, draft `d1a8bb10-cd34-4fe3-905b-53996334dd40`. No reimport, graph repair, reseed, bootstrap, schema change or cloud publication. `.env`, accounts, uploads, named volumes, Demo and all releases stay intact. Windows Docker is separate from cloud tests; no database ports are exposed for remote access.

Owner-reported Windows evidence: v2 correction applied at6, receipt recovered without graph writes; subsequent source approval by the separate `muj-reviewer` application account. **Fetch the current version; source approval consumes a version.** Latest reported authoritative validation `cba61b0b-045a-4978-a9b2-1f2f1ff064c0`:0blocking errors/148warnings, Hostel Entrance→GHS Entrance standard found/step-free absent, Directions only, no maximum bound. Three owner-tested metric-shortest distances/edges:513.10m/13,23.62m/3,163.28m/6. These are owner-reported software tests, not physical/official/accessibility evidence.

**Subsequent owner report (16October2026):** MUJ is now published locally and all requested public acceptance checks passed. Source/submission/approval used separate application accounts operated by the owner; no independent human or institutional approval is claimed. The steps below remain reference for the workflow, **not an instruction to republish**. For the current wording-only update use [routing-policy update instructions](muj-routing-policy-update.md).

## E22 publication completed: owner-reported Windows results — 17 October 2026

The owner reports that the E22 naming draft was submitted, approved and published locally through the normal workflow. This is **owner-reported Windows software evidence**, separate from the automated cloud fixtures below. Both `campus-owner` and `muj-reviewer` application accounts were operated by the owner; account separation is not independent human, institutional, physical-route or accessibility verification.

| Recorded item | Owner-reported value |
|---|---|
| Draft | `bf1e8e0f-f400-4f5f-a16e-25ac11503392` |
| Validation | `9da479c1-6971-4ee3-984f-d0e46ba315a8` |
| Content checksum (dataset, not public artifact) | `99879289d754320e6242f1768bf8abc139b3de32841db442a3b2b55640304f16` |
| Submission | `12e02c58-81a7-40c8-ab91-92646ab6195d` |
| Submission/review | `campus-owner` submitted the exact draft with 145 individual reasons; `muj-reviewer` approved through the helper, reaching version **5 at approval**. |
| Publication | Owner subsequently completed publication through the normal admin UI. The post-publication edit version was not supplied. |
| Public acceptance | Explorer displays **TMA Pai Auditorium entrance**; University Entrance → Mapped entrance 10828149259, **metric shortest**, remains approximately **513m**; Demo Campus Main Gate → Library remains approximately **257m / 4min**. |
| Unresolved identities | E05 and all other unresolved identities were intentionally unchanged. |
| New release UUID / artifact checksum | **Not supplied.** Do not substitute the previous release UUID, validation UUID, submission UUID or dataset checksum. |

The E22 create/submit/approve/publication steps below are retained as historical operations reference, **not instructions to replay them on the completed release**. The helper's old-parent safeguards may correctly stop after publication changes the active release. Preserve the completed draft, receipts, reasons and release; do not recreate, resubmit or republish to obtain evidence. No helper replay or server action is needed to record this report.

### Starting the retained Windows installation

Owner-reported startup incident: the database and frontend were stopped. An API-only `--no-deps` startup waited on readiness and returned database-related **503** responses; starting the existing database and app services resolved it. This incident was not reproduced in cloud tests. `--no-deps` does not start dependencies, so check database health **before** API readiness and start the frontend before checking its localhost URL.

For an already built, existing installation, this **startup-only** PowerShell block starts retained services without helpers, migrations, seeding, account changes or publication. It does not remove volumes or change `.env`:

```powershell
$ErrorActionPreference = 'Stop'
function Invoke-ScnsStep {
    param([Parameter(Mandatory=$true)][scriptblock]$Action)
    & $Action
    if ($LASTEXITCODE -ne 0) { throw 'SCNS startup failed. Stop and preserve existing data and volumes.' }
}
Invoke-ScnsStep { docker compose up -d --wait --no-deps --no-build db }
Invoke-ScnsStep { docker compose ps db }
Invoke-ScnsStep { docker compose up -d --wait --no-deps --no-build api }
Invoke-ScnsStep { docker compose up -d --wait --no-deps --no-build frontend }
Invoke-ScnsStep { docker compose ps db api frontend }
Invoke-RestMethod 'http://localhost:5173/api/v1/health/ready'
```

If the database health step fails, stop there; do not reset/reseed, remove volumes or treat API 503s as a reason to replay publication. These commands were reviewed against `compose.yaml` for this documentation-only change, not executed against Windows or cloud services in this task.

## Existing Windows E22 naming Draft2: read-only review preparation

Historical pre-publication instructions for naming draft **bf1e8e0f-f400-4f5f-a16e-25ac11503392**; publication is now owner-reported complete above. Do not replay this workflow. Do not create another draft or replay naming. At the preparation stage, the owner reported edit3/sourceApproved; validation **9da479c1-6971-4ee3-984f-d0e46ba315a8** has0errors145warnings. The helper fetches current state and rejects stale validation; it never assumes edit3 is still current. Source approval inherited from the parent must be preserved; no source-approval action is required by this command.

Owner-pasted145warning evidence was parsed separately (SHA256e972a5dcf3550bf2af8979712bcd8ac1cbfd3e6002c9f213afd98843d1d723ee). This is owner-supplied evidence, not an agent query of Windows. It agrees with the reported delta, which the helper independently verifies against actual authenticated server history:

|Finding change|Required explanation|
|---|---|
|143unchanged warning IDs|Full diagnostic content and underlying dataset/evidence must still match; prior substantive reasons become candidates, not automatic acknowledgements.|
|E22 shortest:2e91f6527197dcf605c6bd1c →31e82f537d40675eb7d195da|Only message name changed to TMA Pai Auditorium entrance; stable place419441aa-2e6a-57b4-9981-48c31bc40a5c/topology/access unchanged.|
|E22 step-free:afc1f1a73eadcdbf2e59b416 →814311f5e36600b827d98bd1|Same naming-only hash change; no verified accessibility or route gained.|
|3import_provenance warnings absent|Normal clone has no newly committed import jobs. Original parent receipts and copied bindings remain verified/preserved. This is not reimport, lost provenance, a repaired graph or new rights approval.|

Expected categories remain52connectivity_shortest,55connectivity_step_free,33unmapped_entrance,2near_duplicate and1eachcomponents_shortest/components_step_free/unknown_accessibility. The two ambiguous source-stub pairs still require explicit current review of their unresolved floor/physical relationship. Candidate carry-forward is not a new acceptance or independent human review.

### Complete update/report command block

PowerShell in the existing clean repository, Docker Desktop Linux containers running. This starts/checks the retained database before rebuilding/replacing API/web containers; worker/accounts/.env/uploads/drafts/releases remain in place. No migration, validation creation, draft creation, naming, acknowledgements, submission, approval or publication is performed. Password stays hidden in the terminal; no `-T`, pipes, transcripts, credentials in commands/files/chat.

```powershell
$ErrorActionPreference = 'Stop'
function Invoke-ScnsStep {
    param([Parameter(Mandatory=$true)][scriptblock]$Action)
    & $Action
    if ($LASTEXITCODE -ne 0) { throw 'SCNS command failed. Stop and preserve all existing data/reasons.' }
}
Invoke-ScnsStep { git status --short }
if (git status --porcelain) { throw 'Preserve local changes first; nothing reset.' }
Invoke-ScnsStep { git fetch origin feat/muj-connectivity-review }
Invoke-ScnsStep { git switch feat/muj-connectivity-review }
Invoke-ScnsStep { git pull --ff-only origin feat/muj-connectivity-review }
Invoke-ScnsStep { git merge-base --is-ancestor 8adf3a2 HEAD }
Invoke-ScnsStep { docker compose build api frontend }
Invoke-ScnsStep { docker compose up -d --wait --no-deps --no-build db }
Invoke-ScnsStep { docker compose ps db }
Invoke-ScnsStep { docker compose up -d --wait --no-deps --no-build --force-recreate api frontend }
Invoke-RestMethod 'http://localhost:5173/api/v1/health/ready'
$E22Draft = 'bf1e8e0f-f400-4f5f-a16e-25ac11503392'
$E22Validation = '9da479c1-6971-4ee3-984f-d0e46ba315a8'
Invoke-ScnsStep {
    docker compose run --rm --no-deps api python -m app.cli.muj_publication --naming-clone --draft $E22Draft --validation $E22Validation
}
$E22Bundle = (Read-Host 'Paste the exact bundle directory printed by THIS invocation (or its report.md path)').Trim() -replace '/report\.md$', ''
if ($E22Bundle -notmatch '^/app/storage/private/muj-naming-review/bf1e8e0f-f400-4f5f-a16e-25ac11503392/[0-9a-f-]{36}/v[0-9]+-[0-9a-f]{64}-[0-9a-f-]{36}$') { throw 'Unexpected bundle path; preserve data and inspect the printed report.' }
$E22Local = Join-Path (Join-Path (Get-Location).Path 'data\staging\muj-e22-review') ([guid]::NewGuid().ToString())
New-Item -ItemType Directory -Force -Path $E22Local | Out-Null
Invoke-ScnsStep { docker compose cp "api:${E22Bundle}/." $E22Local }
notepad (Join-Path $E22Local 'report.md')
notepad (Join-Path $E22Local 'proposal.json')
```

Enter the existing owner/editor or reviewer **application account** privately. Separate owner-operated accounts are not independent human or institutional review. Use only the exact bundle printed by this invocation and check `prepared_by` matches your operator; no newest-file guess selects another account's proposal. Another account can have its own bundle. A new unique local directory preserves earlier local edits.

The command's success means a report was generated. **Inspect `blockers`, `unjustified_findings`, complete diff, prior/current validation and actual effective proposals before use.** Expected same-state result:0blockers,145one-to-one counterparts (143identical+2E22name/ID changes),3explicitly removed original import findings, exactly2changed records and unchanged source approvals. It fetches the parent/clone full checksums, approved artifact, published submission/decision, original3pinned import metadata records and current validation—not the static pasted text. Default source/geometry/topology/rights checks remain strict.

Files under `/app/storage/private/muj-naming-review/<draft>/<operator>/v<actual-version>-<full-checksum>-<validation>/`:

- `report.md` / `report.json`: full parent identity/creation audit, exact before/after diff, prior/current validator evidence, original imports, source approvals, per-ID counterparts, near-pair evidence, prior submission/reviewer reasons, current server reasons and effective proposals.
- `proposal.json`: current validation ID and proposed submitter warning reasons, with E22 wording updated and stable current warning IDs.
- `reviewer-proposal.json`: separately sourced prior approving-account reasons as candidates for current account review. This file is not a decision/approval payload.
- Per-operator `latest.json`: successful bundle pointer. Any blocked inspection records `blocked.json` without deleting prior reports/proposals.

Repeated reads at the same version/checksum/validation preserve private edited reasons and stale keys for inspection. Current server submission/approval wording is seeded when available; existing private text takes precedence. Missing/invalid/stale IDs/reasons become blockers, never silently deleted. A changed version gets a separate bundle; earlier owner files remain. Browser-unsaved textarea contents are not on the server; preserve them privately yourself. Local copied-file edits are also not automatically uploaded or applied. If intentionally editing the private server proposal, copy only the reviewed JSON back to its exact current `$E22Bundle` and rerun the same preflight; this changes a helper file, not the dataset or server acknowledgements. Retain all prior copies.

### Explicit submission of the already reviewed E22 proposal

The owner reports that Draft2 preflight passed with zero blockers and `proposal.json` now has **145 individually reviewed reasons**, including explicit unresolved near-duplicate assessments. This is owner-reported Windows evidence, not cloud access. The following **explicit submit** path uses that existing file unchanged; default `--naming-clone` remains read-only. No new draft, naming replay, validation creation, source approval, decision or publication occurs.

Run this complete block in PowerShell in the existing repository. Docker Desktop must already have the retained local database/services running. Use the **same existing owner application account that prepared the bundle**; enter credentials privately when prompted. Never add `-T`, pipe the interactive command, use a transcript or paste credentials into chat. Select the existing **server-side private bundle containing your final reviewed proposal**, not an older local copy. If your final reasons are only in a local copied file, first deliberately copy that exact reviewed `proposal.json` back to its original private bundle with `docker compose cp`; retain a backup. This block never uploads or replaces reasons on your behalf.

```powershell
$ErrorActionPreference = 'Stop'
function Invoke-ScnsStep {
    param([Parameter(Mandatory=$true)][scriptblock]$Action)
    & $Action
    if ($LASTEXITCODE -ne 0) { throw 'SCNS command failed. Preserve this bundle and all existing data; stop here.' }
}
Invoke-ScnsStep { git status --short }
if (git status --porcelain) { throw 'Preserve local changes first; nothing reset.' }
Invoke-ScnsStep { git fetch origin feat/muj-connectivity-review }
Invoke-ScnsStep { git switch feat/muj-connectivity-review }
Invoke-ScnsStep { git pull --ff-only origin feat/muj-connectivity-review }
Invoke-ScnsStep { git merge-base --is-ancestor 8eed084 HEAD }
Invoke-ScnsStep { docker compose build api }
Invoke-ScnsStep { docker compose up -d --wait --no-deps --no-build db }
Invoke-ScnsStep { docker compose ps db }
Invoke-ScnsStep { docker compose up -d --wait --no-deps --no-build --force-recreate api }
Invoke-ScnsStep { docker compose up -d --wait --no-deps --no-build frontend }
Invoke-RestMethod 'http://localhost:5173/api/v1/health/ready'
$E22Draft = 'bf1e8e0f-f400-4f5f-a16e-25ac11503392'
$E22Validation = '9da479c1-6971-4ee3-984f-d0e46ba315a8'
$E22Checksum = '99879289d754320e6242f1768bf8abc139b3de32841db442a3b2b55640304f16'
$E22Bundle = (Read-Host 'Paste the existing private bundle directory containing your 145 reviewed reasons (or its report.md path)').Trim() -replace '/report\.md$', ''
$E22Pattern = '^/app/storage/private/muj-naming-review/' + $E22Draft + '/[0-9a-f-]{36}/v3-' + $E22Checksum + '-' + $E22Validation + '$'
if ($E22Bundle -notmatch $E22Pattern) { throw 'Bundle does not match the reviewed Draft2/version3/checksum/validation. Stop and preserve reasons.' }
Invoke-ScnsStep {
    docker compose run --rm --no-deps api python -m app.cli.muj_publication --naming-clone --action submit --draft $E22Draft --validation $E22Validation --expected-version 3 --expected-checksum $E22Checksum --bundle $E22Bundle
}
```

The helper prints the selected bundle, draft/version/checksum, exact JSON payload and its canonical SHA256. **Read all145 selected reasons, including both unresolved near-duplicate findings.** Type **`SUBMIT E22`** only if this is your reviewed payload. Anything else stops without submission. It re-fetches the entire parent/clone/provenance/validation proof after confirmation and checks that report/proposal files have not changed, then posts once through the normal authenticated `/submissions` endpoint with `If-Match: "3"`. Session, Origin/CSRF, campus permission, validation and audit rules remain server-enforced. No graph/catalog/source/anchor data is written.

Expected first success: prints the actual **submission UUID**, saves private `intent-submit.json` before POST and `receipt-submit.json` after the real response, and locks existing Draft2 for review (normally version3→4 with **the same dataset checksum**). The two already-applied E22 names remain the only dataset changes. E05/all other identities and the current public release remain unchanged. This is submission only, not approval or publication.

**Safe retry/recovery:** if the response or local receipt saving fails, rerun the **identical submit command with the same bundle, validation, expected-version3 and checksum**. Do not change the command to version4 or rerun creation/naming/import. Full safeguards run again; the helper verifies an exact server submission with the same actor/validation/checksum/145 reasons and submission version4 before any POST. A match prints its real UUID and writes `receipt-submit-recovery.json`, with no duplicate submission, new submit audit or confirmation prompt. Recovery explicitly does **not** claim the original request audit ID; an existing successful response receipt is retained. If no submission exists and the unchanged draft remains editable at3, another explicit `SUBMIT E22` is required before retry. If intent/payload/history differs, evidence is stale, or parent/release changed, it stops—preserve all files and inspect **Review and releases**; do not delete the journal, overwrite reasons or create another draft to force a retry. Changed reasons after a committed submission require the normal explicit return-to-draft/revalidation/review workflow, outside this command.

A missing/stale/extra warning ID, duplicate JSON key, empty/short reason, other operator's bundle, unexpected dataset/provenance change or changed report/proposal during confirmation stops without a workflow write. Text is never automatically replaced, truncated or filled during submission. Authentication still records normal login/logout audits. No passwords/session tokens are persisted in helper files.

After submission, open **Admin → Assigned campus → MUJ → Selected draft (Draft2) → Review and releases** and verify the actual submission, unchanged145 reasons and locked state. A separately authenticated eligible reviewer account must assess the current findings and reasons, then use the explicit E22 approval command below or provide review notes/reasons and choose **Approve exact reviewed content**. Separate owner-operated accounts are application account separation, not independent human/institutional approval. Final publication remains a separate explicit workflow; do not publish as part of this task.

### Explicit E22 approval: owner-operated muj-reviewer account

Owner identifies the already submitted **Draft2 bf1e8e0f-f400-4f5f-a16e-25ac11503392**, submission **12e02c58-81a7-40c8-ab91-92646ab6195d**, validation **9da479c1-6971-4ee3-984f-d0e46ba315a8**, dataset checksum **99879289d754320e6242f1768bf8abc139b3de32841db442a3b2b55640304f16**. Windows is separate: cloud tests cannot inspect that live submission or approve it. Run the following only locally, using the existing **muj-reviewer** application account and its private password. Do not use the submitter account, add `-T`, pipe the command, enable a transcript or put credentials in arguments/files/chat.

Select the **existing private bundle** that contains the prepared `reviewer-proposal.json` and unchanged full preflight report. An original submitter-prepared version3 bundle is supported; a separately prepared current reviewer bundle also works. The helper verifies its preparer is either this reviewer or the actual submission's submitter. It reads only **reviewer-proposal.json** for candidate reasons: it never substitutes `proposal.json`, accepts current submitter acknowledgements, seeds missing reasons or edits the candidate. If your reviewed candidate changes exist only in a local copy, deliberately copy that exact reviewed JSON back to the original private bundle after retaining backups; the command does not upload/replace it automatically.

PowerShell from the existing repository with retained Docker services running:

```powershell
$ErrorActionPreference = 'Stop'
function Invoke-ScnsStep {
    param([Parameter(Mandatory=$true)][scriptblock]$Action)
    & $Action
    if ($LASTEXITCODE -ne 0) { throw 'SCNS command failed. Stop; preserve the submitted draft, candidate reasons and approval journal.' }
}
Invoke-ScnsStep { git status --short }
if (git status --porcelain) { throw 'Preserve local changes first; nothing reset.' }
Invoke-ScnsStep { git fetch origin feat/muj-connectivity-review }
Invoke-ScnsStep { git switch feat/muj-connectivity-review }
Invoke-ScnsStep { git pull --ff-only origin feat/muj-connectivity-review }
Invoke-ScnsStep { git merge-base --is-ancestor ab3424f HEAD }
Invoke-ScnsStep { docker compose build api }
Invoke-ScnsStep { docker compose up -d --wait --no-deps --no-build db }
Invoke-ScnsStep { docker compose ps db }
Invoke-ScnsStep { docker compose up -d --wait --no-deps --no-build --force-recreate api }
Invoke-ScnsStep { docker compose up -d --wait --no-deps --no-build frontend }
Invoke-RestMethod 'http://localhost:5173/api/v1/health/ready'
$E22Draft = 'bf1e8e0f-f400-4f5f-a16e-25ac11503392'
$E22Submission = '12e02c58-81a7-40c8-ab91-92646ab6195d'
$E22Validation = '9da479c1-6971-4ee3-984f-d0e46ba315a8'
$E22Checksum = '99879289d754320e6242f1768bf8abc139b3de32841db442a3b2b55640304f16'
$E22Bundle = (Read-Host 'Paste the existing private bundle directory containing reviewer-proposal.json (or its report.md path)').Trim() -replace '/report\.md$', ''
Invoke-ScnsStep {
    docker compose run --rm --no-deps api python -m app.cli.muj_publication --naming-clone --action approve --draft $E22Draft --submission $E22Submission --validation $E22Validation --expected-checksum $E22Checksum --bundle $E22Bundle
}
```

The helper first re-fetches full parent/release/artifact/diff/source/import/validation/finding evidence and the exact current submission. It requires **muj-reviewer** to have current MUJ `review_decide`, `review_read` and `audit_read` permissions, a different user ID from the submitter, and no contribution to this revision. It reads the complete campus audit history through bounded normal pagination (up to10050entries; incomplete/changing/unavailable history stops), using the same contribution categories as the server; the normal decision API remains authoritative, including races, revoked grants and contributor separation for system administrators. No permission or source approval is granted by this helper.

**Current version is fetched**, never assumed to remain4. The submission must be locked for review with exact UUID/validation/checksum/current version and all145current warning IDs. An optional `--expected-version 4` adds a caller version pin if deliberately desired, but is unnecessary for the command above. Any unexpected state/diff/provenance/finding/permission change stops while preserving the submitted draft and both reason files.

Enter substantive review notes (10–4000characters) only after inspecting the current evidence and every reviewer candidate, including both unresolved near-duplicate pairs. Example wording **only if true after your review**:

> Owner-operated muj-reviewer separate-account review of the E22 naming-only draft and all145 current warnings. The two source-stub near-duplicate relationships remain unresolved; source/topology/accessibility limitations are retained. No independent human, institutional or field-survey approval is claimed. See the individual reviewer reasons.

The normal API trims surrounding note whitespace; the helper displays that exact normalized note text and the full **145 selected reviewer reasons**, their payload hash, actual actor, submission and fetched current version. Candidate reason text itself is retained verbatim. Type **`APPROVE E22`** only after that explicit review; any other response cancels without approval. The full safeguards/current permissions/history/files are checked again after confirmation. It posts only `decision: approve` to the normal decision endpoint with current `If-Match`, Origin/CSRF and normal audit recording. There is no submit/publish/withdraw/reject/create/data-edit action in this approval path.

Expected first success on an unchanged version4 submission: normal approval advances Draft2/submission to **version5**, submission status **approved**, draft remains **review**, same dataset checksum and unchanged active public release. Actual current version is printed and bound to the request. Files are stored separately under `<bundle>/approval/<reviewer-user-id>/<submission-id>/`: durable `intent.json` before POST, `receipt.json` after the actual response. Submitter reasons and prepared reviewer candidate remain untouched. This is **owner-operated separate-account review**, not independent human or institutional approval.

**Interrupted retry:** rerun the identical command and same bundle as muj-reviewer. The journal retains your exact selected reasons and normalized notes; the helper rechecks full evidence and matches the real server decision's actor, notes, all145reasons and expected version increment. An exact match writes `receipt-recovery.json` and performs no new decision POST or approval audit, no repeated confirmation or notes prompt. It retains an existing successful response receipt and never invents an original request ID. If the original decision did not commit and the exact review state remains, it shows the same saved payload and requires APPROVE E22 again before retry. Changed candidate/intent, a different decision/account, missing intent for an already approved submission, stale source/release/version or unavailable history stops for inspection—do not erase the journal, overwrite reasons, recreate or resubmit the draft. No approval replay is used to repair uncertainty.

Finally open **Admin → Assigned campus → MUJ → Selected draft (Draft2) → Review and releases**. Verify the exact submission UUID, approved status, actual reviewer account, notes, individual reasons and unchanged checksum. Confirm the public explorer still uses the previous release. **Do not choose Prepare publication or Confirm publish immutable release.** Publication remains a separate explicitly authorized workflow.

### Verification boundaries and explicit next steps

The helper verifies the draft's actual creation parent via paginated normal audit GETs (up to10050entries; unavailable audit stops), reconstructs the complete original parent from its authenticated review diff, and checks its full checksum and public artifact. If the parent is itself a clone/incomplete history, it stops for separate assessment. It then reconstructs the entire naming draft and requires the exact two E22 records plus correct derived search_text regeneration; any extra owner/source/binding/frame/catalog/graph change or hidden checksum difference is flagged and preserved. Parent/current route evidence must remain equivalent (human explanation text may differ), with the same validator and exact finding semantics except the allowed name/ID delta. A change in route inputs/policy/results, validator, warning content/counts, source approval or active release stops rather than asserting equivalence. Original pinned-dataset mode is unchanged and still rejects the clone; clone bundles cannot enter its submit/approve path.

On stale validation, open **Admin → Assigned campus → MUJ → Selected draft (Draft2) → Review and releases → Run authoritative validation** using the intended route evidence; preserve meaningful expected no-route cases. Rerun with the new actual validation ID. Do not force the old ID/version/checksum or assume a new validation alone resolves an unexpected data diff. If route-policy/evidence changed, inspect it against the parent's exact displayed evidence rather than fabricating matching outcomes. Any data/source diff needs separate review; this tool never repairs it.

After the report is justified, use the explicit confirmed naming-clone submission above, or enter each individual reason in **Reason for warning <current ID>** and choose **Submit exact validated version for review**. A separately authenticated eligible reviewer account must independently assess each current finding/reason and choose **Approve exact reviewed content**; owner-operated account separation is not a separate human review. Final **Prepare publication / Confirm publish immutable release** remains a separate explicit owner action, outside this preparation task. Do not bulk-acknowledge undisclosed warnings, run the old create/naming/import helper, or publish merely because a candidate proposal exists. MUJ's active public release and Demo remain unchanged throughout preflight.

The sections below describe the original first-publication helper and remain historical workflow reference. They do not authorize a new submission/publication of the old draft or apply automatically to the naming clone.

## 1. Complete PowerShell update and read-only preflight (existing owner)

Open PowerShell in the existing repository with Docker Desktop Linux containers running. This block does **not** submit, approve, validate or publish. Normal login/logout still create/revoke a session and record authentication audits; dataset reads are read-only. Passwords are entered privately in the secure terminal, never arguments/chat/files. Do not pipe the login command or add `-T`.

```powershell
$ErrorActionPreference = 'Stop'
function Invoke-ScnsStep {
    param([Parameter(Mandatory=$true)][scriptblock]$Action)
    & $Action
    if ($LASTEXITCODE -ne 0) { throw "SCNS command failed (exit $LASTEXITCODE). Stop here; preserve data." }
}
Invoke-ScnsStep { git status --short }
if (git status --porcelain) { throw 'Preserve local changes before continuing. Nothing reset.' }
Invoke-ScnsStep { git fetch origin feat/muj-connectivity-review }
Invoke-ScnsStep { git switch feat/muj-connectivity-review }
Invoke-ScnsStep { git pull --ff-only origin feat/muj-connectivity-review }
Invoke-ScnsStep { git merge-base --is-ancestor ee97dbc HEAD }
Invoke-ScnsStep { docker compose build api }
Invoke-ScnsStep { docker compose stop api frontend import-worker }
Invoke-ScnsStep { docker compose up -d --wait --no-deps --no-build db }
Invoke-ScnsStep { docker compose ps db }
Invoke-ScnsStep { docker compose up -d --wait --no-build api frontend import-worker }
Invoke-RestMethod 'http://localhost:5173/api/v1/health/ready'
$scnsMujDraft = 'd1a8bb10-cd34-4fe3-905b-53996334dd40'
$scnsValidation = 'cba61b0b-045a-4978-a9b2-1f2f1ff064c0'
Invoke-ScnsStep { docker compose run --rm --no-deps api python -m app.cli.muj_publication --draft $scnsMujDraft --validation $scnsValidation }
$scnsOwnerBundle = docker compose exec -T api python -c "from pathlib import Path; import json; print(json.loads(Path('/app/storage/private/muj-publication/$scnsMujDraft/latest.json').read_text())['bundle'])"
if ($LASTEXITCODE -ne 0) { throw 'Cannot locate preflight bundle. Stop.' }
$scnsOwnerBundle = $scnsOwnerBundle.Trim()
$scnsOwnerFiles = Join-Path (Get-Location).Path 'data\staging\muj-publication-owner'
New-Item -ItemType Directory -Force -Path $scnsOwnerFiles | Out-Null
Invoke-ScnsStep { docker compose cp "api:${scnsOwnerBundle}/." $scnsOwnerFiles }
notepad (Join-Path $scnsOwnerFiles 'report.md')
```

No migration is needed for this helper. Existing startup dependencies are used; nothing removes volumes. If Git switch/pull fails, preserve changes and stop. If the selected validation is stale/missing, preflight writes a **blocked report**; it never creates a validation or repairs records. See step3. Preflight's exit0 means the report was written, **not** that it is ready to submit. Check `blockers` and `unjustified_findings`.

Keep the copied report private and out of Git/public issues. `data/staging/` is ignored. `latest.json` is only a convenience pointer; retain `$scnsOwnerBundle` to the exact per-account/version/checksum/validation directory. Another operator's preflight can move the pointer but cannot change this captured variable. Repeated preflight preserves existing `proposal.json` reasons; a fresh version gets a separate bundle. Files are0600/directories0700 in Linux private storage. Local Windows copy inherits your folder permissions.

## 2. Inspect the actual report, sources, provenance and near duplicates

The report includes the live version/checksum, selected validation and evidence, independently approved source metadata/attribution/derivative, exact committed import IDs/checksums/options/actors, profile-specific components and reference reachability, two node-pair records/incident paths/anchors, exact proposed ID→reason payload and any blockers. It compares current nodes/edges/anchors/places against the corrected v2 pin; unexpected edits are preserved and require a separate assessment. It does not guess that a changed dataset is still covered by this guide. Current source metadata approval is shown; the server rechecks reviewer authorization during normal publication.

**Public disclosure check before any submission/publication:** current public UI exposes the OSM-preparation campus name, approved map attribution and each place's source/no-survey/display-point qualifiers. It has no dedicated long-form campus-specific “limited academic preview” notice editor, and private warning/review text is not a public notice. If your intended use requires stronger always-visible scope wording, stop before step4 and request that bounded change; this helper does not fabricate a notice or alter approved source metadata.

Expected equivalent data yields146 proposed reasons and **two near_duplicate findings requiring explicit assessment**. The helper does not blindly acknowledge148warnings. Errors, changed/unapproved sources/provenance, stale validation, changed pin, unfamiliar findings or missing expected evidence block action. A fully reviewed proposal must cover exactly the current warning IDs; stale IDs/reasons are retained for reconciliation, not silently discarded. Existing submitted owner reasons appear separately in `report.md`; independent reviewer reasons are a separate payload. Browser-unsaved textarea text is not available from the API: copy any such wording privately into `proposal.json` before proceeding.

| Category | Reported count | Meaning and proposed limited-preview basis |
|---|---:|---|
| connectivity_shortest |52|Reachability against the validator's **first eligible anchor reference**, not proof every other pair is unroutable. Actual anchors and forward/return flags included per place. Retain mapping gaps; only eligible stored journeys, no physical-isolation assertion.|
| connectivity_step_free |55|No verified chain from the reference; OSM unknown accessibility is not a survey. Preserve no verified route.|
| unmapped_entrance |33|Catalog/display point has no open mapped arrival anchor. No centroid/nearest-path/door/floor invented; destination routing remains unavailable.|
| import_provenance |3|Each actual job must be committed to this draft and match exact original v1 batch checksum, filename and normalized create-only options. Source rights/actor recorded; ODbL obligations retained. No reimport.|
| near_duplicate |2|Explicit manual assessment below; **no automatically supplied reason**.|
| components_shortest |1|29weak stored components in the unchanged preparation, not29proven physically isolated areas. Private subway/access/coverage and floor ambiguity remain unresolved.|
| components_step_free |1|295public nodes become separate components with no eligible verified step-free edges in this pin; this is an eligibility/evidence result.|
| unknown_accessibility |1|Summary of unknown eligible-edge accessibility; no wheelchair/physical verification promoted by acknowledging it.|

Graph-only validation had111findings; whole-publication validation adds33unmapped entrances+3imports+1accessibility summary =148. A different current count must be inspected, not forced to this count.

Near-pair source investigation (exact private original checksum verified in cloud; inspect live report for differences):

| Stored nodes | OSM node IDs / retained ways | Findings |
|---|---|---|
|2355ef5c-c611-567d-9e5e-9bb983986b00 / b7823a47-64ca-50e1-8d8e-159c48273de4|11809063446 (`entrance=staircase`) /11593739317 (`entrance=yes`); ways1247085147/1271670518|Distinct source IDs within1m; same issue at opposite ends below. Proximity is not a source junction.|
|bb717aa9-1b70-516a-b1e5-f6e4df4134a0 / fd76f58a-b463-5d95-93f6-f952c4f999a2|11594340527 /11809063447; same two ways|Each way has two original nodes, `highway=path` and `building:levels=0;1;2;3`. These tags do not assign an actual floor or prove outdoor/indoor/duplicate/physical separation.|

Each stored two-node component has **one** mapped entrance (11809063446 or11593739317), not zero. No distinct-place route joins these stubs to the three tested journeys. A GPS start on a stub could nevertheless approach its own entrance. Therefore do not justify them as unused/unanchored, declare physically separate, or waive them as surveyed safe. No merge/removal/connection/geometry change is proposed. Any actual correction requires a separately justified plan and fresh normal validation/review.

For each exact near-duplicate warning ID, inspect `manual-findings.json`. Default acceptance is false. If you cannot justify retaining this ambiguity for a clearly limited local OSM preview, **leave false and stop**; obtain evidence/plan rather than fabricating a reason. An owner and an independent reviewer each make their own assessment. If acceptable, enter truthful concrete `reason` and `evidence_reviewed` strings (20–800characters each) and explicitly set `accept_limited_osm_preview` to true for those two IDs. Do not accept unknown future categories.

Possible wording **only if it reflects your actual review and intended limited use**; equivalent findings can share it:

- Reason: `Retain the original source IDs without merging for this limited local OSM preview. The nearby stubs' shared junction, floor relationship and duplication status remain unresolved. This acceptance is not physical-separation, outdoor-floor, access or accessibility verification; no full campus wayfinding claim.`
- Evidence reviewed: `Inspected the two exact node pairs, source ways1247085147/1271670518, ambiguous building:levels tags and one mapped entrance per two-node component. They do not connect to the tested routes, but a GPS-on-stub approach remains possible. Any graph correction requires separate evidence and review.`

A substantive reason records acceptance of a disclosed **source-data limitation**, not new evidence. If you intend actual physical wayfinding beyond this limited evaluation, source/floor/access evidence remains missing. Source rights approval is separate from institutional endorsement.

## 3. Refresh stale validation only through the normal owner UI

Open `http://localhost:5173/admin`, sign in privately with the existing **owner**. Select **Assigned campus → Manipal University Jaipur (OSM preparation)**, the existing **Selected draft**, then **Review and releases**. Check **Validation and review**, **Revision state**, **edit version**, **Reviewed content SHA-256**, and source **Approved**. Do not reapprove an already approved source or rerun the correction.

If preflight says the supplied validation is current, retain it. If stale/missing, under **Expected-route evidence and whole-draft validation** set:

- **Evidence start:** Hostel Entrance.
- **Evidence destination:** GHS Entrance.
- **Expected standard route:** Route found.
- **Expected step-free route:** No verified route · documented gap.
- **Evidence distance policy:** Directions only.
- **Optional maximum distance in metres:** leave empty.
- **Route evidence reason:** `Limited OSM local preview. Owner-tested metric-shortest Hostel Entrance to GHS Entrance route is23.62m over3edges. This Directions-only validation checks route presence using fewest traversals, not that metric distance. Unknown accessibility is not field-verified; preserve no verified step-free route. Library and cross-campus mapping gaps remain unsupported; no institutional approval or survey asserted.`

With no queued cases, click **Run authoritative validation**. If cases are queued, only those cases are validated; include these exact two profiles or remove unintended queue entries. Read the new validation ID, errors and warnings. Validation is an explicit audited action but does not edit graph geometry or publish. Any blocking errors stop this workflow. Set `$scnsValidation` to that actual new ID and rerun only the preflight command from step1; capture the new bundle and inspect it. Do not reuse old warning IDs or claim version6. Source approval by `muj-reviewer` was owner-reported; live preflight is the required check.

## 4. Preserve/edit reasons, then explicitly submit as owner

Open the two private files locally. Copy only your edited input files back, not the report snapshot:

```powershell
notepad (Join-Path $scnsOwnerFiles 'manual-findings.json')
notepad (Join-Path $scnsOwnerFiles 'proposal.json')
Invoke-ScnsStep { docker compose cp (Join-Path $scnsOwnerFiles 'manual-findings.json') "api:${scnsOwnerBundle}/manual-findings.json" }
Invoke-ScnsStep { docker compose cp (Join-Path $scnsOwnerFiles 'proposal.json') "api:${scnsOwnerBundle}/proposal.json" }
Invoke-ScnsStep { docker compose run --rm --no-deps api python -m app.cli.muj_publication --draft $scnsMujDraft --validation $scnsValidation }
Invoke-ScnsStep { docker compose cp "api:${scnsOwnerBundle}/report.md" (Join-Path $scnsOwnerFiles 'report.md') }
Invoke-ScnsStep { docker compose cp "api:${scnsOwnerBundle}/proposal.json" (Join-Path $scnsOwnerFiles 'proposal.json') }
notepad (Join-Path $scnsOwnerFiles 'report.md')
```

Do not overwrite an existing reason with a generic sentence. Rerunning adds newly justified missing reasons but preserves already entered values, even stale ones so they can be reconciled. Check **zero blockers**, no unjustified findings, exact148(or actual current) IDs, source rights, current version/checksum, and every reason. If any version/checksum changed, capture/review the new printed bundle instead; never copy old input wholesale to it. This preflight still does not save acknowledgements on the server.

When you have actually reviewed the complete report/payload:

```powershell
Invoke-ScnsStep { docker compose run --rm --no-deps api python -m app.cli.muj_publication --draft $scnsMujDraft --action submit --bundle $scnsOwnerBundle }
```

Enter existing **owner** credentials privately. The helper rechecks evidence and **shows the report and exact payload again**. Type **SUBMIT** only after reviewing it. This saves the per-ID acknowledgement map and submits the exact validation through the same API as **Submit exact validated version for review**; there is no separate server acknowledgement-save API. Other input stops. Submission locks the revision and increments its version; it does not publish. Source approval is untouched. Do not additionally click the UI submission button after helper success.

If submission response or receipt saving fails, rerun **the same action with the same bundle/account**. It first verifies an exact existing server submission (validation/checksum/actor/reasons) and returns without another workflow write. A verification receipt does not invent the original request audit ID. A stale/different submission or reason stops; never edit old version/checksum to force replay. GUI rejection/withdrawal/edit requires fresh evidence and bundle.

## 5. Review by the separate existing muj-reviewer application account

In admin click **Sign out**, sign in privately as **muj-reviewer**, choose the same campus/draft and **Review and releases**. Source approval alone is not content approval. “Independent” in the application means a distinct permitted non-contributor identity; it does not establish an independent human reviewer. The owner reports operating all these accounts. Review **Changes from parent release**, **Approved public projection counts**, **Source rights and public derivatives**, **Validation evidence**, **Computed route acceptance evidence**, **Imported batch provenance** and **Submitter warning acknowledgements**. The independent reviewer must inspect source/content and decide whether this limited scope is justified. The owner/contributor cannot approve or publish, including as system administrator.

To avoid retyping148reasons, generate the reviewer's **own** read-only bundle:

```powershell
Invoke-ScnsStep { docker compose run --rm --no-deps api python -m app.cli.muj_publication --draft $scnsMujDraft --validation $scnsValidation }
$scnsReviewerBundle = docker compose exec -T api python -c "from pathlib import Path; import json; print(json.loads(Path('/app/storage/private/muj-publication/$scnsMujDraft/latest.json').read_text())['bundle'])"
if ($LASTEXITCODE -ne 0) { throw 'Cannot locate reviewer preflight.' }
$scnsReviewerBundle = $scnsReviewerBundle.Trim()
$scnsReviewerFiles = Join-Path (Get-Location).Path 'data\staging\muj-publication-reviewer'
New-Item -ItemType Directory -Force -Path $scnsReviewerFiles | Out-Null
Invoke-ScnsStep { docker compose cp "api:${scnsReviewerBundle}/." $scnsReviewerFiles }
notepad (Join-Path $scnsReviewerFiles 'report.md')
notepad (Join-Path $scnsReviewerFiles 'manual-findings.json')
notepad (Join-Path $scnsReviewerFiles 'proposal.json')
```

Enter **muj-reviewer** credentials at that preflight prompt. It shows current review-locked version/checksum and original submission reasons separately; it does not copy owner approval implicitly. For this original first-release draft it reads complete authenticated review-diff rows because editable graph GET correctly refuses review-locked records. An incomplete/cloned-parent diff is refused, never filled with guessed rows.

Reviewer records their **own** two manual assessments and per-warning reasons, and edits **notes** in `proposal.json` to reflect actual independent review. Suggested starting notes (only after genuine review):

> Limited local OSM academic preview only; not official MUJ data or a field survey. Reviewed exact source attribution/rights, three import checksums, current content checksum, computed route evidence and individual warning explanations. Library, cross-campus and verified step-free gaps remain unavailable. The two nearby source-stub relationships remain unresolved; I accept only the stated local source-preview scope, not physical/accessibility or institutional approval. No graph merge or new connection is authorized by this decision.

Copy only the two edited input files back, rerun preflight **as muj-reviewer**, then inspect the refreshed report/proposal:

```powershell
Invoke-ScnsStep { docker compose cp (Join-Path $scnsReviewerFiles 'manual-findings.json') "api:${scnsReviewerBundle}/manual-findings.json" }
Invoke-ScnsStep { docker compose cp (Join-Path $scnsReviewerFiles 'proposal.json') "api:${scnsReviewerBundle}/proposal.json" }
Invoke-ScnsStep { docker compose run --rm --no-deps api python -m app.cli.muj_publication --draft $scnsMujDraft --validation $scnsValidation }
Invoke-ScnsStep { docker compose cp "api:${scnsReviewerBundle}/report.md" (Join-Path $scnsReviewerFiles 'report.md') }
Invoke-ScnsStep { docker compose cp "api:${scnsReviewerBundle}/proposal.json" (Join-Path $scnsReviewerFiles 'proposal.json') }
notepad (Join-Path $scnsReviewerFiles 'report.md')
```
 If not acceptable, stop or use **Review decision notes → Reject and return to draft** with a concrete reason. The owner can use **Withdraw and return to draft**; these invalidate prior evidence and increment versions.

When zero blockers and all current findings are individually justified, the reviewer can explicitly save the normal decision:

```powershell
Invoke-ScnsStep { docker compose run --rm --no-deps api python -m app.cli.muj_publication --draft $scnsMujDraft --action approve --bundle $scnsReviewerBundle }
```

Enter **muj-reviewer** credentials; inspect full displayed payload and type **APPROVE**. Normal server independence/permissions/CSRF/If-Match/checksum/audit rules apply. Any other input stops. Retry the same bundle after an interrupted response; an exact existing reviewer decision is verified without duplication. This is the API equivalent of **Approve exact reviewed content** with reviewer reasons/notes; final publication is still a separate UI action. Do not also click approval in the browser. The helper has **no publish/rollback/source-approve/graph-edit option**.

## 6. Explicit final local publication (muj-reviewer)

After helper approval, in the same review page click **Refresh review packet** and verify **Review submission: approved**, intended checksum/version, source and computed evidence. Click **Prepare publication**. In **Confirm publication**, inspect current public MUJ release (`none` for first publication), new revision UUID and approved version. Check **I reviewed the consequences and the exact approved content**, then click **Confirm publish immutable release** only when you intend to switch the local public explorer.

This creates an immutable release/artifact and changes only this campus's public pointer transactionally. It preserves Demo and history. It does not host/deploy the application or publish a cloud copy. If an action conflicts, preserve notes and refresh; do not invent an idempotency key/pointer or retry blindly. Current normal UI action preparation retains its key for network retry. Do not use the old setup/updater or reimport bundles.

## 7. Local public acceptance, attribution and rollback availability

Open/refresh `http://localhost:5173/`. Choose MUJ in the public campus selector; its name identifies **OSM preparation**. Choose **Metric · stored path distances** under **Distance policy** (historically labelled **Verified metric paths**), **Shortest walking route** under **Route preference**, then set **Starting point**/**Destination** and **Find walking route**:

| Inputs (metric shortest unless stated) | Expected unchanged stored result |
|---|---|
|University Entrance → Mapped entrance 10828149259|513.10m /13edges|
|Hostel Entrance → GHS Entrance|23.62m /3edges|
|Hostel Entrance → Faculty Block Entrance|163.28m /6edges|
|Hostel Entrance → Central Library|No eligible arrival route; missing mapped entrance|
|University Entrance → Hostel Entrance|No eligible route across unresolved access/grade/coverage gap|
|Hostel Entrance → GHS Entrance; Step-free · verified access only|No verified step-free route|

Public route cards may round known distances to whole metres; exact decimals/edge counts remain in the approved computed evidence and public route response (browser Network inspector if needed). Route distances are mapping estimates, not survey measurements; no distance upper bound was set for validation. Do not claim actual-device GPS verification. **Correction to the earlier guide:**513.10m/13edges is the metric-shortest University Entrance result, not a Directions-only expectation. Owner reports Directions only gives approximately799m/9edges and explicitly says fewest eligible traversals. That objective minimises unit-cost traversals, not metres or time. Metric eligibility permits estimated outdoor OSM lengths and does not imply field verification; step-free eligibility is separate. See the [exact objectives and wording update](muj-routing-policy-update.md).

Inspect public **Campus map**: approved coverage overlay attribution should display `© OpenStreetMap contributors`, copyright URL and ODbL1.0. **Place details** retains source/no-field-verification/display-point/explicit-anchor limitations. **Clear paths. Clear limits.** explains published source/accessibility limitations and estimated travel. Neither private warning reasons nor reviewer notes are published as public notices. Current UI has **no dedicated campus-specific long-form “limited academic preview” notice editor**; the existing OSM-preparation name, source attribution and place descriptions qualify the data, but do not claim all warning explanations appear publicly. The pre-publication disclosure check in step2 must be completed before approval; this helper does not redesign the explorer or fabricate a public notice.

Switch to **Demo Campus**: synthetic label stays; Main Gate→Library standard route remains257m/4min (256.88m/3stored edges). Confirm no Demo release pointer changed.

Return as muj-reviewer to **Review and releases → Release history and rollback**, click **Refresh release history**. Confirm MUJ active release/checksums and **Download approved public release …** artifact link. Retain ODbL attribution/applicable adapted-database availability obligations; artifact download is the application's explicit public projection, not an assertion of comprehensive legal/institutional approval.

For a **first MUJ release there is no earlier MUJ target**, so rollback preparation is absent. This is expected; do not publish an extra release just to test it or choose Demo as a target. Once an earlier eligible MUJ immutable release exists, controls are **Earlier release**, **Rollback reason**, **Prepare rollback**, checkbox **I understand public navigation will use the earlier release**, then **Confirm rollback to earlier release**. This is an explicit authorized pointer change, not a DB/schema reset. The release history and rollback workflow already have separate automated evidence; no owner Windows rollback is claimed here.

## Evidence and limitations

The actual Windows report exists only after step1 runs there; cloud output is isolated fixture evidence, never a substitute. Full source topology/coverage collection questions remain in [MUJ connectivity review](../data/muj-connectivity-review.md). Initial helper tests caught a fixture with synthetic import filenames/provenance and a review-locked graph404; fixture now uses exact normal MUJ imports and helper reads the supported complete review diff. See [verification](../testing/verification.md) for final actual check results. No app API/schema/permission/publication algorithm changes.
