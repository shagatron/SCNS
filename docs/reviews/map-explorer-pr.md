# Preserve baseline public behavior with dark outdoor map presentation

The original redesign replaced directory/planner interactions beyond the requested visual scope. Restore the public shell, complete directory/cards/details/actions/pagination, planner/defaults/messages/focus/scroll, full-width independent directions and floor behavior from a30810d. Keep the dark outdoor map, mint route/halo and original category icons, with the baseline direct map-to-destination action and all original pins/permanent names. No sidebar replacement, new modes or result collapse states.

App, focusPlanner, FloorRouteMap, PublicExperience, public.css, RouteDetails, OutdoorLocation and useClosures match baseline byte-for-byte; CampusExplorer state/queries/handlers and outdoor fit/resize match exactly. Only bounded map styling, map-only exception fallback and unchanged API route/shared-place feedback placed beside planner controls remain. No algorithms, contracts, data, dependencies, permissions, admin or publication changes.

The complete source/test audit, matched desktop/mobile baseline/original/corrected observations and screenshots are in docs/testing/map-preservation-audit.md and docs/previews/map-preservation/. Old changed assertions were reviewed against baseline: direct indoor qualification visibility and original planner style assertions restored; only approved map stroke/overlay colour selectors differ. New parity checks enforce a runtime contract captured from actual baseline; passing old redesign tests is not used as parity proof. Final comparative/core/container outcomes are recorded in docs/testing/verification.md when complete.

Existing developer/Windows data and published MUJ/E22/Demo releases are untouched. Verification uses disposable databases/storage only; MUJ source visual responses are explicitly simulated, not actual Windows/MUJ/physical/accessibility evidence. Windows/phone, human AT and real GPS checks are not claimed. Data-preserving frontend-only update instructions retain the existing temporary phone override and start/check database before API readiness.

Target feat/muj-connectivity-review. Do not merge, publish data or deploy.
