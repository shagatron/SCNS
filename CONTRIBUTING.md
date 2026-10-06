# Contributing

Read `docs/product/master-spec.md`, the requirements checklist and architecture decisions before changing behavior. Keep work within the current authorized milestone. Use a focused branch/PR and include the problem, implemented behavior and actual checks run. In cloud tasks use the existing isolated checkout unless a worktree is explicitly requested.

Run `make setup demo`, then `make check build test-unit test-integration` and the relevant Playwright journeys before submitting changes. Run `make generate-api` after contract changes and commit generated contracts together. Pin changed dependencies with their lockfiles. Test schema migrations against an isolated PostGIS database; do not patch production tables by hand.

Use synthetic fixtures for code tests. Do not commit institutional source plans, secrets, personal records or claimed accessibility measurements without authorized evidence. All real data must eventually pass a draft import/review/publication process.

No owner-approved code license was supplied. No open-source license grant has been invented; obtain the owner's license decision before redistribution. Dataset and floorplan rights are separate from source-code licensing. Preserve any supplied C prototype under `legacy/c-prototype/`.
