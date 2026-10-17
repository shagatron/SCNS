# Dark public map explorer workspace

Reorganize the existing public explorer into a charcoal map workspace with a compact destination sidebar, synchronized list/pin selection and place details, and mint routes over published geometry. Mobile uses ordinary page scrolling and button-controlled panels; restrictions, connection failures and location expiry remain visible when the panel is collapsed. Preserve the scrolling editorial homepage and existing admin interface.

Use the existing planner, immutable release APIs, approved overlays and unfiltered floor images. Add keyboard selection/focus recovery, map resizing without unwanted refitting, and a map-renderer failure boundary that retains text navigation. Entrance indicators use only explicitly shared stored outdoor endpoints, never floor pixels or guessed coordinates. No backend algorithm, API contract, schema, permission, dependency or campus data changes.

Verification: final frontend lint/type/build and **67 units** pass; **56 unchanged contracts** pass. Full built nginx/API/worker suite: **99 passed /1 intentional duplicate-width skip**. After a rendered-inspection fix keeping the desktop place card clear of zoom controls, affected source checks pass **23/1skip** and rebuilt-container checks pass **23/1skip**, including explicit non-overlap, five-width axe/overflow, keyboard/focus and renderer-failure checks. Retain unaffected full-suite evidence; exact source rerun/failure sequence is in `docs/testing/verification.md`. No original behavior, authorization or publication assertion removed. Retained22table count/content digests and `.env` presence unchanged.16decoded screenshots and SHA256 manifest are in `docs/previews/map-explorer/`.

The MUJ visual fixture is a read-only source-response simulation using committed source preparation, not the owner's Windows release or an actual MUJ database. New Windows, physical-device keyboard, live GPS, human assistive-technology and field/accessibility verification are not claimed. Existing owner-reported E22 publication evidence remains separate.

Windows update/start and manual inputs: `docs/operations/map-explorer.md`. The update preserves `.env`, accounts, drafts/releases, private uploads and volumes, reuses any existing temporary phone-access override unchanged, and starts/checks the database before API readiness. No migration, reseeding, helper replay, publication or deployment.

Target: `feat/muj-connectivity-review`. Do not merge or deploy as part of this change.

Creation attempted after verified completion5a81226: GitHub CLI returned `Post "https://api.github.com/graphql": Forbidden` (exit1). Git push succeeded. Open the prepared PR manually: https://github.com/shagatron/SCNS/compare/feat/muj-connectivity-review...redesign/map-explorer?expand=1 . No merge or deployment performed.
