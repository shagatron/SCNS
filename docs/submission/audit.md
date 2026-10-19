# Academic submission audit — 19 October 2026

This bounded task prepares the accepted Docker application for main/repository assessment. No routing/UI/runtime redesign, native-Windows work, dependency upgrade, schema/data modification, import/reseed/bootstrap or campus publication is authorized/performed. The user explicitly authorized one normal history-preserving main integration while retaining all feature branches. This audit is supporting evidence, not the missing final report/PPT.

## Initial branch and source audit

| Item | Observed state before cleanup |
|---|---|
| Repository / working tree | `/workspace/SCNS`, origin shagatron/SCNS, clean feat/muj-indoor-demo |
| Accepted local/remote application |136667f690398ffdb1073222d8acf2cce2ad2638; existing accepted homepage/directory/planner, published campus/admin workflows, integrated Outdoor / Indoor demo |
| origin/main |3ad7bc47ba28613fbf6db42d619a21017eeda66e(initial commit);0main-only/157accepted-only commits. Main is an ancestor of accepted, no legitimate main-only content to resolve. |
| Default branch | Remote symbolic HEAD advertises refs/heads/main; already correct, no default-branch change needed |
| Native experiment | origin/feat/native-windows385a3352e9e8fd072a59b3612f131b8374114519,12unique commits beyond common ee683e1 ancestor; not an ancestor of accepted. No scripts/windows tree in accepted. Preserve this branch without merging it. |
| Branch inventory |22remote heads captured read-only before work. Existing feature SHAs must remain unchanged; new cleanup branch submission/academic-final is additive. |
| Local work | No pre-existing uncommitted changes; existing checkout used, no worktree/reset/discard/history rewriting |

After fetching all advertised heads explicitly (the environment originally fetched only its selected branch), no later accepted Docker application was identified beyond136667f. Supporting feature branches are ancestors of that accepted delivery; native is the excluded experiment. Cleanup uses a separate submission/academic-final branch so accepted feature tips need not move.

## Bounded corrections

- README now leads with purpose/academic scope, actual DSA/source links and bounds, stack/architecture, Docker-only prerequisites, distinct retained-data startup and explicitly new-project initial setup, exact presentation inputs/evidence and limitations. Corrected obsolete wording that MUJ was only an unpublished draft: the owner reports its local publication; Git does not contain that Windows database.
- New [database-first Windows main update/start](../operations/academic-submission.md), [DSA explanation](dsa.md), [presentation inputs/checklist](presentation.md), and [missing approved-document status](README.md). Existing phone override is preserved/excluded for laptop-only startup.
- CONTRIBUTING now scopes `make setup demo` to new disposable source-development installations and points retained users to safe startup. One stale `.env.example` comment corrected; no config value changed.
- No functional defect requiring application changes was found. No source module, algorithm/API, dependency lock, migration, Compose runtime, source fixture, original image/font/licensing or preserved visual evidence is changed.

## DSA and disclosure audit

Read actual dijkstra.py/mixed.py, public service/settings, diagnostic reachability, educational adapter and unit references. Core uses directed adjacency lists, built-in heapq/hash maps/sets/lists, positive-cost relaxation, stale-entry rank checks, deterministic multi-source/target ties and predecessor reconstruction. Mixed adapter selects metres/traversals/supported seconds, with strict eligibility; internal distance_m is a scalar cost slot, not always a physical measurement. Full details and kernel versus adapter bounds are in [dsa.md](dsa.md). BFS is a comparison; diagnostic DFS-style stacks and test-only Floyd–Warshall are identified accurately. No unimplemented/custom algorithm claim.

MUJ is incomplete OSM-based data; estimated metric lengths are not physical-survey proof. Educational room/floor geometry is original/unscaled and disconnected from real MUJ. Unknown measures/ETA/accessibility stay unknown. GPS is opt-in confirmed outdoor positioning, not tracking/floor inference. Separate owner-operated application accounts are not independent human/institutional approval. Preserve OSM/ODbL, supplied image and Inter/OFL disclosures; no code license was invented.

## Hygiene and document availability

Baseline657tracked paths checked against dependency/build/cache/log/private-upload/backup/environment patterns: no artifact-path candidates requiring removal. Legitimate committed PNGs/SVGs/synthetic PDF/source OSM/migrations/locks/fixtures/evidence retained. `.env` history lists only `.env.example`; real `.env` is ignored. Private/raw/staging/export/storage paths, dependencies/build/test output and logs have ignore coverage. Local-only development credential examples are explicitly labelled, not owner credentials.

High-confidence private-key/GitHub-token/AWS-access-ID patterns scanned **1779historical blobs across all fetched refs**, with zero matches; no values were printed and no history rewritten. This is a bounded pattern/path/manual audit, not exhaustive proof that arbitrary secrets can never exist. Runtime owner passwords remain private; no credentials were requested/copied. No secret-remediation path was identified.

No approved final report(PDF/DOCX) or final presentation(PPTX/approvedPDF) was accessible. The only attached PDF found is the school reference, not a submission report. No substitute/older document or invented final-document link is added. See [exact remaining document requirements](README.md). No submission tag is created.

## Verification and integration receipt

Fresh before-integration checks: **276backend unit tests passed18.14s** (one existing non-failing FastAPI/httpx deprecation warning), **76frontend tests/17files passed6.30s**, frontend lint/type and production build pass, Compose configuration validation pass. These are Linux/cloud checks, not Windows execution. Backend units include directed/weighted/reconstruction and40random graph/Floyd–Warshall comparisons, eligibility/version/privacy contracts and educational3/9/9/0/disconnected computations.

Reused accepted136667f evidence: source91distinct passing cases across broad/affected runs plus1existing skip; **75built nginx/API/worker passes/1existing skip**, real worker PNG processing/readiness/private paths;33PostGIS/API source-OSM metric calculations. Unchanged application/Compose/fixtures/contracts make reuse valid. Prior source run had2new locator failures corrected in an8-case rerun; it is not described as one uninterrupted green92-case run. [Detailed original evidence](../testing/educational-indoor-demo.md#explorer-integration-adjustment--final-evidence) and [rendered desktop/mobile integration](../previews/educational-indoor/integrated/README.md) remain.

Submission main merge, post-integration checks, remote/default/feature-branch verification and retained-data receipt will be appended after successful integration, or a precise protected-branch/permission blocker will be recorded. No application data is brought from Windows into cloud as a substitute.
