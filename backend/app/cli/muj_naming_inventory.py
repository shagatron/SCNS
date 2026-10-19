"""Offline source naming inventory/maps; never accesses a database."""

import argparse
import csv
import json
from pathlib import Path

from app.services.muj_naming import ROOT, build_inventory, draw_map


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    raw = args.source.read_bytes()
    inventory = build_inventory(raw)
    data = ROOT / "data/muj-naming"
    docs = ROOT / "docs/data/muj-naming"
    data.mkdir(exist_ok=True)
    docs.mkdir(exist_ok=True)
    (data / "inventory.json").write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n")
    keys = [
        "marker",
        "entity",
        "id",
        "external_id",
        "current_label",
        "proposed_name",
        "confidence",
        "reason",
    ]
    with (docs / "inventory.csv").open("w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(inventory["records"])
    entrances = sorted(
        (r for r in inventory["records"] if r["entity"] == "places" and r["marker"]),
        key=lambda r: r["marker"],
    )
    points = [r["point"]["coordinates"] for r in entrances]
    bounds = (
        min(p[0] for p in points) - 0.001,
        min(p[1] for p in points) - 0.001,
        max(p[0] for p in points) + 0.001,
        max(p[1] for p in points) + 0.001,
    )
    (docs / "overview.svg").write_text(
        draw_map(raw, inventory, bounds, "MUJ entrance naming · overview")
    )
    rows = [
        "# MUJ entrance identification atlas",
        "",
        "Source-derived OSM context, not an official map or survey. Numbering is stable for this pinned source. Gray footprints/paths can include quarantined indoor or inaccessible source data; map context does not create routing connections. Open each detail image at full size for surrounding labels. North is up.",
        "",
        "[Overview](overview.svg) · [Full inventory CSV](inventory.csv) · [Evidence JSON](../../../data/muj-naming/inventory.json)",
        "",
        "|Marker|Current name / source node|Proposed name / action|Source evidence|",
        "|---|---|---|---|",
    ]
    for r in entrances:
        lon, lat = r["point"]["coordinates"]
        filename = r["marker"] + ".svg"
        (docs / filename).write_text(
            draw_map(
                raw,
                inventory,
                (lon - 0.00065, lat - 0.0005, lon + 0.00065, lat + 0.0005),
                f"{r['marker']} · {r['current_label']}",
            )
        )
        proposal = (
            r["proposed_name"] or "**Identify; unresolved.** Do not infer a building from this map."
        )
        ways = "; ".join(
            f"way {w['osm_way']}: "
            + str(
                w["tags"].get("name")
                or w["tags"].get("ref")
                or w["tags"].get("highway")
                or w["tags"].get("building")
            )
            for w in r["explicit_member_ways"]
        )
        rows.append(
            f"|[{r['marker']}]({filename})|{r['current_label']} (`{r['external_id']}`)|{proposal}|{ways}|"
        )
    rows += [
        "",
        "## Owner response",
        "",
        "For each unresolved marker, return `E## — confirmed public entrance name — how you know — any uncertainty`. Say “unknown” if unsure. Identify the specific door/gate, not just a nearby building. E05 is the current 513m/799m route destination and has no source building association. E02 belongs to both a named auditorium outline and room016 outline; exclusive identity is ambiguous. E08/E23 and their adjacent nodes retain the separately documented near-duplicate/floor ambiguity. E16/E22 carry source main tags, which do not establish an institutional main entrance. E22 alone has unique named building-outline membership; proposed wording omits main. No guessed rename is enabled.",
        "",
        "![Numbered campus overview](overview.svg)",
        "",
    ]
    (docs / "README.md").write_text("\n".join(rows))
    print(
        f"Generated {len(inventory['records'])} inventory rows, 23 entrance details and overview; no database access."
    )


if __name__ == "__main__":
    main()
