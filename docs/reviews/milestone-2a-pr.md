Milestone 2A adds campus-scoped administration while public search, maps and Dijkstra routes continue using the existing published release. An editor can copy that release into a private draft and maintain buildings, places, departments, aliases and anchors without changing public navigation.

This PR is based on `feat/milestones-0-1` at `86e1591`; `main` does not yet contain that baseline. Review this as a stacked, admin-only change. Do not merge automatically.

- Argon2id local login, hashed opaque server sessions, logout/expiry/revocation, durable login throttles, exact Origin and CSRF checks, no-store responses and one-time trusted-host bootstrap with no default password.
- Campus-scoped editor, reviewer/publisher, operations and system-administrator permissions, server-side authorization, campus account provisioning, live permission checks and last-administrator protection.
- Normal fresh login with a settled anonymous session query; known-session invalidation, private cache cleanup, quiet logout and late-response cancellation are regression-tested.
- Responsive dashboard/catalog/user/audit UI; revision-wide optimistic writes, preserved conflict input and explicit reconciliation; transactional append-only audit. Step-free anchor edits require evidence notes.
- Migrations backfill normalized aliases and add administrative identity/catalog foundations without changing active public release fields. Browser/migration tests use isolated disposable databases; browser credentials are random and admin traces are disabled.

Validation on 7 October 2026: Ruff, TypeScript, ESLint, Vite build and Python compilation passed; 21 Python unit, 28 real PostGIS integration and 14 frontend tests passed; all 22 desktop/360px Chromium journeys passed, including public navigation regressions and axe checks. Migration fresh/downgrade/re-upgrade, frozen alias backfill/protection, release preservation, schema alignment and actual bootstrap CLI replay checks passed. API/frontend images built. Generated contracts reproduce byte-for-byte. See `docs/testing/verification.md` for exact evidence and limitations.

Milestones 2B/2C (imports, graph editing, validation/review, publication/rollback) remain unimplemented. No public deployment, real-campus survey, owner manual test, production security certification or physical-device verification is claimed. Setup/bootstrap/test commands are in `docs/operations/admin.md`; the progress log and requirements checklist are updated.
