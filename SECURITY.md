# Security and reporting

This is a local-development synthetic demonstration. Do not deploy its local database credentials or grant public access to its database. Production startup is deliberately gated until the deployment milestone. There is no default administrator and no unauthenticated mutation/upload interface.

Keep `.env`, `data/raw`, staging, exports and storage private. Browser `VITE_*` settings are public. Public catalog/map/route requests project only active-release public rows; frozen revisions are protected in the database. Route bodies and raw errors are not logged. Errors carry generated request IDs and safe messages.

No security contact was provided. Report vulnerabilities privately to the repository owner through an available private channel (for example GitHub private vulnerability reporting if the owner enables it). Do not post source plans, credentials or sensitive location details in public issues. No monitored emergency service or response SLA is claimed.

Before a real pilot: implement scoped admin authentication, session/CSRF controls, bounded authenticated ingestion, audit, verified public derivatives, HTTPS, dependency review, least-privilege database roles, rate limits and a tested backup/restore runbook. These remain milestone work, not deployed controls.
