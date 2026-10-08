# Operational closures v1

`closure.schema.json` and `decision.schema.json` regenerate with `make generate-api`. These are API input templates, not staged-import data. Live restriction writes never apply to drafts or automatically publish a map. Choose stable target IDs from current authenticated inventory; do not invent a campus/edge/connector identity. Use a unique actor/campus retry key and quoted current overlay version, normal session/CSRF/Origin.

Example body (replace placeholders using current inventory):

```json
{
  "key": "unique-incident-key",
  "target_kind": "connector",
  "target_id": "00000000-0000-4000-8000-000000000001",
  "reason": "Synthetic lift outage: software exercise only.",
  "starts_at": "2026-10-08T10:00:00+05:30",
  "estimated_end_at": null,
  "reopening_policy": "operator_verified"
}
```

Reopening body: `{ "key": "unique-reopen-key", "evidence": "Synthetic incident resolution only, not a physical repair.", "confirmed": true }`. Rebind additionally requires target_kind and target_id. Dates require explicit UTC/offset; the UI converts device-local input to UTC and labels that time convention. Estimated end never reopens. Decision evidence stays private. [Contract](../../../docs/data/closures.md) and [Windows/manual operation](../../../docs/operations/closures.md).
