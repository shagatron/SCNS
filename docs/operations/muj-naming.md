# MUJ entrance naming and readable outdoor directions

This is a source naming assessment and optional draft-only correction, not a new campus import or publication. Existing Windows MUJ is published and owner-reported acceptance passed. The owner additionally reports the updated metric/traversal controls work: University Entrance → Mapped entrance10828149259 is approximately513m under metric shortest and799m/9edges under Directions only. These are owner-reported Windows software results, not cloud inspection, field measurements or independent human/institutional approval.

## Inspect the evidence first

[Numbered atlas and identification table](../data/muj-naming/README.md), [overview](../data/muj-naming/overview.svg), [423-row CSV](../data/muj-naming/inventory.csv) and [full source-evidence JSON](../../data/muj-naming/inventory.json) use the exact pinned OSM source SHA256d4b902b01fe944acb3161026679dabbab4898d6952bee22d7019f15fd15748de. Source IDs, tags, explicit way membership, imported building associations and anchor references are retained. Contributor metadata is excluded. Source context includes excluded/indoor/private paths; it does not imply navigation eligibility or physical connectivity. Every entrance has its own zoomed map. The overview is intentionally less detailed; use individual maps for crowded markers. OSM attribution/ODbL remains visible.

Inventory “current” labels are the pinned import baseline, **not a claim to have queried Windows**. Run the helper below to bind the actual current published release ID/checksum/labels and any selected draft's fresh edit version. Its report marks missing/owner-renamed rows; it never restores a pinned dataset over owner work.

- **E22 / osm-node-11664524407:** proposed **TMA Pai Auditorium entrance** for its existing place and graph node. Exact source membership in named building way1249393737 supports this; no proximity inference. Source entrance=main is retained as evidence, but the proposed name deliberately omits main. No new building association, room/floor or accessibility claim.
- **E02 / osm-node-10773902923:** source node belongs to both the named auditorium outline and room016 outline; exclusive identity remains ambiguous. No automatic auditorium rename.
- **E05 / osm-node-10828149259:** the tested513m/799m destination has only an unnamed service-way association, no name/building identity. It remains unresolved.
- **17 entrances require identification:** E02,E05,E08–E21,E23. Return `E## — public entrance name — how you know — uncertainty`, or “unknown”. E16 is in an unnamed theatre outline; do not transfer a nearby auditorium name. E08/E23 retain the documented near-duplicate/floor ambiguity. A source wheelchair/main tag is not physical verification.

The only enabled stored rename is the exact E22 source proposal. No option accepts arbitrary guessed names or edits unresolved entrances. Identification of the remaining locations is a separate owner decision and reviewed follow-up. Five source-named entrances keep their names.295graph nodes retain their IDs/source evidence; unnamed junctions are not assigned invented landmarks.

## Data-preserving Windows update and read-only preflight

Open PowerShell in your existing clean SCNS repository, Docker Desktop running Linux containers. Existing API/database must already be configured and migrated; this change has no migration. No setup, import, correction, seed, bootstrap, warning acknowledgement or publication command is needed. Accounts, `.env`, uploads, volumes, drafts, releases, restrictions and QR records are retained. Restarting the API does not migrate the database. The existing worker is left alone.

```powershell
$ErrorActionPreference = 'Stop'
function Invoke-ScnsStep {
    param([Parameter(Mandatory=$true)][scriptblock]$Action)
    & $Action
    if ($LASTEXITCODE -ne 0) { throw 'SCNS command failed. Stop here; preserve existing data.' }
}
Invoke-ScnsStep { git status --short }
if (git status --porcelain) { throw 'Preserve local changes first; nothing reset.' }
Invoke-ScnsStep { git fetch origin feat/muj-connectivity-review }
Invoke-ScnsStep { git switch feat/muj-connectivity-review }
Invoke-ScnsStep { git pull --ff-only origin feat/muj-connectivity-review }
Invoke-ScnsStep { git merge-base --is-ancestor 278db69 HEAD }
Invoke-ScnsStep { docker compose build api frontend }
Invoke-ScnsStep { docker compose up -d --wait --no-deps --no-build api frontend }
Invoke-ScnsStep { docker compose ps }
Invoke-RestMethod 'http://localhost:5173/api/v1/health/ready'
Invoke-ScnsStep { docker compose run --rm --no-deps api python -m app.cli.muj_naming }
Start-Process 'http://localhost:5173/'
Start-Process (Resolve-Path '.\docs\data\muj-naming\overview.svg').Path
Start-Process (Resolve-Path '.\docs\data\muj-naming\E05.svg').Path
```

Enter the existing MUJ owner/editor username and hidden password **in that terminal only**. Do not use `-T`, piping, command-line passwords, transcripts, environment credentials or chat. The helper uses normal server-side sessions/CSRF/Origin, RAM cookies, localhost-only transport and no redirects. It validates the real top-level SessionOut.user_id. Login/logout have their normal session audits; default mode performs only dataset GETs. It verifies the downloaded immutable artifact checksum and current release twice, then saves a private per-user preflight JSON in the existing private upload volume. No draft is created automatically.

Expected on unchanged current source labels: actual MUJ release/checksum printed, `draft version None`,0blockers,2proposed fields: E22 nodes.label and places.name → TMA Pai Auditorium entrance. Actual release ID must be read from Windows output, not invented here. If already published under those names, zero proposed changes is valid. Other owner labels/moved target/missing anchor in a selected draft cause blockers; preserve and inspect rather than force/apply. Current release/restriction or draft version changes while reviewing cause a safe stop.

To inspect the exact report outside the container, paste its printed path at the private prompt below. The file has no credentials, but keep it out of git:

```powershell
$ReportPath = Read-Host 'Paste the printed /app/storage/private/muj-naming/.../preflight-....json path'
if ($ReportPath -notmatch '^/app/storage/private/muj-naming/[0-9a-f-]{36}/preflight-[0-9a-f-]{36}\.json$') { throw 'Unexpected report path' }
$LocalReport = Join-Path $env:TEMP 'scns-muj-naming-preflight.json'
Invoke-ScnsStep { docker compose cp "api:$ReportPath" $LocalReport }
notepad $LocalReport
```

## Optional source-supported E22 draft rename

Do this only after reading the proposal and choosing to accept that **source-only** name. Unresolved locations remain pending owner identification; nothing guesses them.

1. Open `http://localhost:5173/admin`, **Sign in** as owner/editor, **Assigned campus → MUJ**. Select **Draft catalog**, then **Create draft from published release**. This clones the local active release through the normal API; it preserves your original published/frozen draft and all other drafts. Alternatively select an intentionally chosen existing **editable** naming draft. Do not return the published revision to draft or reuse an unrelated work draft.
2. The draft dropdown displays its version/status/date, not its UUID. After creating/selecting the intended draft, rerun the default read-only helper below. It lists editable drafts with full UUIDs, draft numbers and current edit versions. Match the new draft number from **Selected draft** and copy that UUID. It is not necessarily the old d1a8bb10… draft; no ID/version is assumed. Then preview that selected draft:

```powershell
Invoke-ScnsStep { docker compose run --rm --no-deps api python -m app.cli.muj_naming }
$NamingDraft = Read-Host 'Editable MUJ naming draft UUID from the matching draft number above'
$ParsedNamingDraft = [guid]::Parse($NamingDraft)
Invoke-ScnsStep { docker compose run --rm --no-deps api python -m app.cli.muj_naming --draft $ParsedNamingDraft }
```

3. Inspect its printed private report, including full before/after fields. Only nodes.label/places.name may differ. Geometry, stable IDs, costs, direction, visibility, accessibility, description, evidence and anchors remain unchanged. If there are blockers or any unexpected input, stop. This helper never merges source nodes or repairs topology.
4. If accepting **only E22**, run:

```powershell
Invoke-ScnsStep { docker compose run --rm --no-deps api python -m app.cli.muj_naming --draft $ParsedNamingDraft --apply-source-name }
```

Enter credentials privately again. This still prints/saves a fresh exact preview. Type **APPLY NAMES** only after inspecting that report; anything else stops. Each normal server transaction requires If-Match, permissions, CSRF and full validation/audits. Node and catalog writes are **two transactions**, not a single atomic batch. Version/source fields are rechecked between them. A conflict/storage/connection failure can leave exactly one rename applied; it does not imply rollback.

5. Recovery: run the same command **without** `--apply-source-name` first. It reports exact already-present and remaining names, without data writes. Reaccept only the fresh remaining proposal if still intended. Exact target names are no-ops; repeated completed applications do not increment draft version or duplicate naming audits. Real successful responses save actual request IDs/actor receipts privately. Lost response/receipt recovery proves current state only; it cannot invent the original audit actor/request. Original server audits remain authoritative. No old receipt is replaced.
6. Refresh **Draft catalog → Places** and **Outdoor graph**: E22 name/label should match, IDs/point/anchor unchanged. All17unresolved entrances remain as before. Public explorer must still show the **existing release names** until you separately review and publish this draft. The source naming helper has no publish/source-approval/submission capability.

## Readable direction wording and manual checks

The server's two existing outdoor route engines now share a small instruction formatter. An exact numeric `OSM junction <ID>` placeholder becomes **Continue along the walkway.**, **Follow the path.**, **Take the stairs.** or **Follow the ramp.**, according to the stored edge kind. Meaningful existing labels still appear as destinations in each step; final **Arrive at …**, entrance transitions, indoor floor/room/connector instructions are unchanged. No turn bearings, corridor identity or left/right turns are invented. Stored labels/IDs/evidence stay available in admin and in the immutable artifact; edge/node identifiers remain in route responses for provenance. This wording update requires an API restart, not a campus republication.

Hard-refresh Chrome (**Ctrl+Shift+R**), select MUJ:

|Inputs|Expected on the unchanged owner release/restrictions|
|---|---|
|University Entrance → Mapped entrance10828149259; Metric · stored path distances; Shortest walking route|~513m/13edges; intermediate raw OSM junction IDs replaced by neutral instructions; final arrival retains exact current destination name|
|Same endpoints; Directions only · unknown distance allowed; Fewest eligible traversals|~799m/9edges; unchanged traversal objective/disclosure|
|Hostel Entrance → GHS Entrance; metric shortest|~23.62m/3edges (rounded public card permitted)|
|Hostel Entrance → Faculty Block Entrance; metric shortest|~163.28m/6edges|
|Hostel Entrance → Central Library; University Entrance → Hostel Entrance|No permitted route|
|Hostel Entrance → GHS Entrance; verified step-free|No verified route; never infer accessibility from a renamed entrance|
|Demo Main Gate → Library|257m/4min baseline retained|

Check desktop and phone width: readable directions, named final arrival, existing Outdoor/floor section controls. Existing QR/GPS confirmation, restriction freshness and indoor floor transitions must remain as before. No real-device/Windows naming-helper execution is claimed by cloud tests. The reported Windows routing-control/publication checks above remain separate owner evidence.

## Separate review/publication gate

After any actual draft rename, use **Review and releases**, run **Run authoritative validation** against the fresh version, inspect all current findings and provide truthful per-warning reasons. Previously supplied validation IDs/acknowledgements are not reusable for a changed clone. Existing sources may require **Approve source …** by an eligible separate account; inspect rather than assuming approval carried forward. Then the normal **Submit exact validated version for review**, a separately authenticated eligible account's decision and explicit **Prepare publication / Confirm publish immutable release** remain separate owner actions. Do not publish as part of this task. Separate application accounts operated by one owner are not independent human or institutional approval.

The old `muj_publication` helper deliberately expects the original exact pinned labels/records. It will reject a renamed/cloned draft; **do not relax those checks or rerun old correction/setup helpers**. Use the normal review UI with fresh evidence for a naming draft. Keep prior release/history/rollback available. Atlas identification does not certify paths, accessibility or new institutional approval.

## Reproduce offline evidence

With frozen backend dependencies installed and the original private source retained (not committed):

```powershell
Push-Location backend
uv run --frozen python -m app.cli.muj_naming_inventory --source '../data/raw/muj/source.osm'
Pop-Location
```

This verifies source and prepared-file hashes and deterministically regenerates only the sanitized inventory/atlas files. It has no database/API connection. The source file is never copied into the image or committed. Existing v1/v2 manifests/batches remain byte-identical.
