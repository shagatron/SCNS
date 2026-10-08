# Synthetic 3C route fixture

Every location, distance, availability and accessibility assertion is invented for isolated software tests. This is not campus survey data. It does not seed a database or publish a release.

Use two independently approved floors in the same synthetic Academic House building, each with a selected 600×400 reference plan and independently approved 0.05m/reference-pixel calibration. `ground.json` and `upper.json` are explicit tracing-v1 proposals; load each in its own floor editor and save to the draft. The private source/evidence sentinel must never appear in a public artifact.

`connections.json` is a connections-v1 proposal. The admin fixture loader binds `$GROUND`, `$UPPER`, their selected `$GROUND_LAYER`/`$UPPER_LAYER`, `$BUILDING`, and two explicitly selected outdoor building anchors `$ENTRANCE_A`/`$ENTRANCE_B`. It first asks the server for a non-mutating preview. Save remains explicit. IDs are stable; repeat loads update these same records rather than adding duplicates. Keep fixture floors in one disposable test draft. Existing developer tracing must not be overwritten accidentally.

The fixtures retain NULL widths, slopes, elevations and vertical rise. Synthetic measured connector traversals and static baseline times are labelled as test assertions. The stairs cannot be step-free. The lift has an explicit synthetic 20-second baseline wait; it is not a live queue prediction. Unknown or unavailable connectors cannot carry a route.

Expected stored-graph results:

| Input | Standard | Step-free |
| --- | --- | --- |
| Ground101 → Ground102 (and reverse) | 18m | 18m |
| Ground101 → Upper201 (and reverse) | 36m through stairs | 57m through lift |
| Main Gate ↔ Upper201 | Stored outdoor + explicit entrance + indoor + connector edges | Eligible lift and verified paths |
| Ground101 → isolated destination | No route | No route |
| Lift unavailable, cross-floor | Stairs route | No verified step-free route |
| All connector distances unknown | No metric cross-floor route | No metric cross-floor route |
| Unknown connector distance/time + explicit directions-only | Eligible traversal count, unknown total distance/ETA | Only verified step-free edges |

`expected.json` gives exact stable place IDs. The original public Main Gate → Library route remains approximately256.88m over3 stored edges. See `docs/operations/indoor-routing.md` for data-preserving update and manual inputs. To regenerate only these JSON files: `python scripts/generate-indoor-routing-demo.py` (no database access).
