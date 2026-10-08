Improve the existing public homepage and route planner with consistent teal/neutral typography, spacing, aligned form controls, readable restriction/error/loading states, distance/ETA summary and directions, plus clearer outdoor/floor view controls. Public-scoped styles and presentation wrappers keep admin, QR location confirmation, restriction freshness and synthetic/accessibility qualifications intact.

Presentation-only follow-up from completed4B129cb63: no algorithms, API, database/schema, permissions, publication, dependencies or new features changed;4C remains unstarted.

Validation: frontend lint/type/build and47unit tests;24affected desktop/mobile navigation/closure/QR/indoor journeys; source and built public checks at1440/360/320px with unchanged256.88m/3edge baseline, no overflow, zero axe violations and visible keyboard focus. Frozen frontend image passed; only local frontend replaced and developer data/.env/release/count receipts unchanged. Prior4B backend/migration/full-container evidence reused. Actual Windows/physical devices/Safari/Firefox/human AT remain unverified.

Complete Windows update and short synthetic walkthrough: docs/operations/public-polish.md. Progress/verification/checklist updated. No admin redesign, LAN/public access, merge/deployment, reseed or volume removal.

Base: feat/milestone-4b-closures (verified129cb63a4a01d117c4913d7e330ac42769d932a5).
Head: polish/public-route-planner.
Suggested title: Polish the public homepage and route planner
