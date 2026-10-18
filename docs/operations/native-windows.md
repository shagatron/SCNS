# Native Windows — implementation in progress

Starting point: accepted `polish/muj-homepage` at `ee683e1a61a6584147c3e39b121a8765db5e46ba`. Owner reports homepage branding, directory and routing checks passed on Windows. This report is separate from automated Linux evidence.

This unfinished checkpoint records the implementation boundary before changes: preserve UI, APIs, graph, releases and Docker rollback. Native PostgreSQL/PostGIS and all actual Windows data migration require owner-run local commands; cloud cannot inspect that database. No migration/reseed/bootstrap/publication on retained data.

Planned delivery: frozen dependency/version preflight; separate protected native configuration; native foreground process supervision with readiness, graceful shutdown and durable job recovery; fail-closed AppContainer/job-limited Windows decoder without network capabilities; portable helper locks/receipts; consistent stopped-writer Docker backup plus private storage/journals; verified restore into a new native DB/storage only; resumable verification and rollback instructions. Independent Windows verification remains required, not inferred from Linux passes.

Inspection found Linux-only `resource`/seccomp and UID dropping in floorplan decoder, unconditional `fcntl` in two helpers, `fchmod`/directory-fsync assumptions and Bash/Make/process groups in development startup. Existing workers use durable leases and bounded retry recovery; preserve these semantics. Python lock requires 3.12–3.13, Node >=22.12; Docker uses PostgreSQL 17/PostGIS 3.5. No UI/dependency lock change planned.

Official site access on 18 October 2026: nodejs.org download returned HTTP 200; postgresql.org, postgis.net, docs.astral.sh and learn.microsoft.com direct requests returned proxy `Tunnel connection failed: 403 Forbidden`. Official PostgreSQL/uv GitHub documentation mirrors returned HTTP 200. Further official-source checks, exact commands and actual validation results will replace this unfinished section.
