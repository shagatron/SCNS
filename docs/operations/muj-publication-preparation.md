# Existing Windows MUJ draft: limited local OSM preview review

This guide uses `feat/muj-connectivity-review` including `ee97dbc`. It prepares the **existing** campus `afcf4f1a-635f-563b-af5b-3d7efd2ed84c`, draft `d1a8bb10-cd34-4fe3-905b-53996334dd40`. No reimport, graph repair, reseed, bootstrap, schema change or cloud publication. `.env`, accounts, uploads, named volumes, Demo and all releases stay intact. Windows Docker is separate from cloud tests; no database ports are exposed for remote access.

Owner-reported Windows evidence: v2 correction applied at6, receipt recovered without graph writes; subsequent source approval by the separate `muj-reviewer` application account. **Fetch the current version; source approval consumes a version.** Latest reported authoritative validation `cba61b0b-045a-4978-a9b2-1f2f1ff064c0`:0blocking errors/148warnings, Hostel Entrance→GHS Entrance standard found/step-free absent, Directions only, no maximum bound. Three owner-tested distances/edges:513.10m/13,23.62m/3,163.28m/6. These are owner-reported software tests, not physical/official/accessibility evidence.

**Subsequent owner report (16October2026):** MUJ is now published locally and all requested public acceptance checks passed. Source/submission/approval used separate application accounts operated by the owner; no independent human or institutional approval is claimed. The steps below remain reference for the workflow, **not an instruction to republish**. For the current wording-only update use [routing-policy update instructions](muj-routing-policy-update.md).

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
Invoke-ScnsStep { docker compose up -d --wait --no-build db api frontend import-worker }
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
- **Route evidence reason:** `Limited OSM local preview. Owner-tested stored standard Hostel Entrance to GHS Entrance route is23.62m over3edges. Unknown accessibility is not field-verified; preserve no verified step-free route. Library and cross-campus mapping gaps remain unsupported; no institutional approval or survey asserted.`

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
