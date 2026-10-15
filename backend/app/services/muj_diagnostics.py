"""Offline diagnostics of pinned MUJ v1; never proposes executable graph mutations."""

import hashlib
import html
import json
import math
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

from shapely.geometry import LineString, shape

from app.services.osm_conversion import convert, encode, tags

HIGHLIGHTS = {
    1154145269,
    1154145270,
    1154145273,
    1246099090,
    1159217177,
    1245274146,
    926463927,
    1158509500,
    1159542817,
    1271244213,
    1568303898,
}


def diagnose(raw, preparation):
    """Verify original and complete pinned derivative before inspecting sanitized source tags."""
    manifest = json.loads((preparation / "manifest.json").read_bytes())
    if hashlib.sha256(raw).hexdigest() != manifest["source_sha256"]:
        raise ValueError("Original checksum differs from pinned MUJ preparation")
    for name, digest in manifest["files"].items():
        if (
            Path(name).name != name
            or hashlib.sha256((preparation / name).read_bytes()).hexdigest() != digest
        ):
            raise ValueError("Pinned derivative checksum mismatch")
    converted = convert(raw)  # Bounded UTF-8/XML guards, before parsing source ourselves.
    batches = [
        json.loads((preparation / name).read_bytes())
        for name in sorted(manifest["files"])
        if name.startswith("batch-")
    ]
    if encode(converted["bundles"]) != encode(batches):
        raise ValueError("Converter changed pinned v1 records; review/version separately")
    root = ET.fromstring(raw)
    source = {
        kind: {int(e.attrib["id"]): e for e in root.findall(kind)}
        for kind in ("node", "way", "relation")
    }
    positions = {
        i: [float(e.attrib["lon"]), float(e.attrib["lat"])] for i, e in source["node"].items()
    }
    refs = {i: [int(n.attrib["ref"]) for n in e.findall("nd")] for i, e in source["way"].items()}
    records = [r for b in batches for r in b["records"]]
    entities = {
        kind: {r["external_id"]: r["data"] for r in records if r["entity"] == kind}
        for kind in ("edges", "nodes", "places", "anchors", "buildings")
    }
    adjacency = defaultdict(set)
    for e in entities["edges"].values():
        adjacency[e["from_node_id"]].add(e["to_node_id"])
        adjacency[e["to_node_id"]].add(e["from_node_id"])
    remaining = set(entities["nodes"])
    groups = []
    while remaining:
        pending, found = [min(remaining)], set()
        while pending:
            n = pending.pop()
            if n not in found:
                found.add(n)
                pending.extend(adjacency[n] - found)
        remaining -= found
        groups.append(found)
    groups.sort(key=lambda g: (-len(g), min(int(n[9:]) for n in g)))
    node_component = {n: i for i, g in enumerate(groups, 1) for n in g}
    source_components = defaultdict(set)
    edges = []
    for identity, edge in sorted(entities["edges"].items()):
        way = int(identity.split("-")[2])
        component = node_component[edge["from_node_id"]]
        rr = refs[way]
        # Match original ordered references by the pinned canonical physical identity.
        # Coordinates/proximity alone never establish node membership.
        matched = False
        for left in range(len(rr)):
            if f"osm-node-{rr[left]}" not in {edge["from_node_id"], edge["to_node_id"]}:
                continue
            for right in range(left + 1, len(rr)):
                part = rr[left : right + 1]
                canonical = min(tuple(part), tuple(reversed(part)))
                sig = hashlib.sha256(encode(canonical)).hexdigest()[:32]
                if (
                    edge["physical_path_id"]
                    == f"osm-way-{way}-{canonical[0]}-{canonical[-1]}-{sig}"
                ):
                    for n in part:
                        source_components[n].add(component)
                    matched = True
        if not matched:
            raise ValueError("Cannot trace prepared segment back to original references")
        edges.append(
            {"id": identity, "way": way, "component": component, "geometry": edge["geometry"]}
        )
    components = []
    for i, group in enumerate(groups, 1):
        anchors = [a for a in entities["anchors"].values() if a["node_id"] in group]
        components.append(
            {
                "component": i,
                "node_count": len(group),
                "source_node_ids": sorted(n for n, c in source_components.items() if i in c),
                "stored_node_ids": sorted(group),
                "directed_edge_count": sum(e["component"] == i for e in edges),
                "source_way_ids": sorted({e["way"] for e in edges if e["component"] == i}),
                "source_way_tags": {
                    str(w): tags(source["way"][w])
                    for w in sorted({e["way"] for e in edges if e["component"] == i})
                },
                "destinations": [
                    {"id": a["place_id"], "name": entities["places"][a["place_id"]]["name"]}
                    for a in sorted(anchors, key=lambda a: a["place_id"])
                ],
            }
        )
    decisions = defaultdict(list)
    for d in converted["report"]["decisions"]:
        decisions[d["source"]].append(d["reason"])
    coverage = shape(converted["report"]["scope"]["coverage"])
    excluded = []
    for i, e in sorted(source["way"].items()):
        t = tags(e)
        if "highway" not in t or f"osm-way-{i}" not in decisions:
            continue
        rr = refs[i]
        line = (
            LineString([positions[n] for n in rr])
            if len(rr) > 1 and all(n in positions for n in rr)
            else None
        )
        excluded.append(
            {
                "way": i,
                "tags": t,
                "reasons": sorted(set(decisions[f"osm-way-{i}"])),
                "node_refs": rr,
                "retained_components_touched": sorted(
                    {c for n in rr for c in source_components[n]}
                ),
                "shared_source_nodes": [
                    {"node": n, "components": sorted(source_components[n])}
                    for n in rr
                    if source_components[n]
                ],
                "covered_by_exact_polygons": coverage.covers(line) if line else None,
                "geometry": {"type": "LineString", "coordinates": list(line.coords)}
                if line
                else None,
            }
        )
    unanchored = []
    for identity, p in sorted(entities["places"].items()):
        if any(a["place_id"] == identity for a in entities["anchors"].values()):
            continue
        containers = [
            b
            for b, row in entities["buildings"].items()
            if shape(row["footprint"]).covers(shape(p["point"]))
        ]
        unanchored.append(
            {
                "id": identity,
                "name": p["name"],
                "point": p["point"],
                "footprint_containment_only": containers,
                "source_tags": converted["report"]["provenance"][f"places:{identity}"]["tags"],
                "shared_path_components": sorted(source_components[int(identity[9:])])
                if identity.startswith("osm-node-")
                else [],
                "note": "Containment/display points do not establish entrance access or routing anchors.",
            }
        )
    return {
        "format": "scns-muj-connectivity-diagnostic-v1",
        "source_sha256": manifest["source_sha256"],
        "preparation_manifest_sha256": hashlib.sha256(encode(manifest)).hexdigest(),
        "status": "Diagnostic only. No changes to preparation, drafts, access, approval or publication.",
        "counts": converted["report"]["included_counts"],
        "components": components,
        "unanchored_destinations": unanchored,
        "excluded_highways": excluded,
        "source_decisions": converted["report"]["decisions"],
        "scope": converted["report"]["scope"],
        "edges": edges,
        "selected_source_nodes": [
            {"node": i, "point": positions[i], "tags": tags(source["node"][i])}
            for i in (
                10733816254,
                10733816255,
                10733816256,
                10733816257,
                10778271605,
                10769840689,
                12585506492,
            )
            if i in positions
        ],
    }


def diagnostic_svg(report, *, subway=False):
    """Standalone geographic figure. Dashed lines are excluded SOURCE geometry, never new paths."""
    bounds = (
        (75.56305, 26.84165, 75.5641, 26.8423)
        if subway
        else shape(report["scope"]["extent"]).bounds
    )
    x0, y0, x1, y1 = bounds
    factor = math.cos(math.radians((y0 + y1) / 2))
    scale = min(1040 / ((x1 - x0) * factor), 650 / (y1 - y0))

    def xy(p):
        return (70 + (p[0] - x0) * factor * scale, 760 - (p[1] - y0) * scale)

    def line(points):
        return " ".join(f"{x:.2f},{y:.2f}" for x, y in map(xy, points))

    chunks = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="860" viewBox="0 0 1200 860" role="img"><title>MUJ source connectivity diagnostic</title><desc>Numbered coloured components are prepared paths. Dashed red paths are excluded raw OSM geometry requiring review, not routable proposals. No basemap or proximity joins.</desc><rect width="1200" height="860" fill="white"/>',
        '<text x="30" y="30" font-family="sans-serif" font-size="22">MUJ — UNPUBLISHED SOURCE DIAGNOSTIC</text>',
        '<text x="30" y="58" font-family="sans-serif" font-size="14">Colour + C number: retained component · red dashed: EXCLUDED source path, review only · north ↑</text>',
        '<defs><clipPath id="plot"><rect x="30" y="90" width="1140" height="690"/></clipPath></defs><g clip-path="url(#plot)">',
    ]
    for polygon in shape(report["scope"]["coverage"]).geoms:
        chunks.append(
            f'<polygon points="{line(polygon.exterior.coords)}" fill="#f4f5ee" stroke="#a7ada3"/>'
        )
    seen = set()
    for e in report["edges"]:
        points = e["geometry"]["coordinates"]
        key = min(tuple(map(tuple, points)), tuple(reversed(list(map(tuple, points)))))
        if key in seen:
            continue
        seen.add(key)
        colour = f"hsl({e['component'] * 137 % 360},65%,32%)"
        chunks.append(
            f'<polyline points="{line(points)}" fill="none" stroke="{colour}" stroke-width="2.4"><title>C{e["component"]} OSM way {e["way"]}</title></polyline>'
        )
    for e in report["excluded_highways"]:
        if e["way"] not in HIGHLIGHTS or not e["geometry"]:
            continue
        pts = e["geometry"]["coordinates"]
        chunks.append(
            f'<polyline points="{line(pts)}" fill="none" stroke="#b52828" stroke-width="2" stroke-dasharray="6 4"><title>EXCLUDED {e["way"]}: {html.escape(", ".join(e["reasons"]))}</title></polyline>'
        )
        if subway:
            x, y = xy(pts[len(pts) // 2])
            chunks.append(
                f'<text x="{x:.1f}" y="{y - 7:.1f}" font-size="12" fill="#8a1111">{e["way"]}</text>'
            )
    for c in report["components"]:
        edge = next(e for e in report["edges"] if e["component"] == c["component"])
        x, y = xy(edge["geometry"]["coordinates"][0])
        chunks.append(
            f'<text x="{x:.1f}" y="{y - 4:.1f}" font-family="sans-serif" font-size="12" font-weight="bold">C{c["component"]}</text>'
        )
    for n in report["selected_source_nodes"]:
        x, y = xy(n["point"])
        label = str(n["node"]) if subway else n["tags"].get("name", "")
        chunks.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#111"/><text x="{x + 6:.1f}" y="{y + 15:.1f}" font-family="sans-serif" font-size="12">{html.escape(label)}</text>'
        )
    chunks += [
        '</g><text x="30" y="810" font-family="sans-serif" font-size="14">WGS84 [longitude, latitude] · visual latitude correction only · no survey, access or accessibility verification</text>',
        '<text x="30" y="838" font-family="sans-serif" font-size="13">© OpenStreetMap contributors · ODbL 1.0 · https://www.openstreetmap.org/copyright</text></svg>',
    ]
    return "\n".join(chunks) + "\n"


def write_diagnostics(report, output):
    output.mkdir(parents=True, exist_ok=True)
    (output / "diagnostic.json").write_bytes(encode(report))
    for filename, subway in (("components.svg", False), ("subway.svg", True)):
        (output / filename).write_text(diagnostic_svg(report, subway=subway), encoding="utf-8")
    rows = [
        "# Pinned MUJ component inventory\n",
        "Diagnostic only; no proposed line is an applied path. Exact IDs/tags and all exclusions: [diagnostic.json](diagnostic.json). [Overview](components.svg), [subway detail](subway.svg).\n",
        "| Component | Stored nodes | Directed edges | Anchored destinations | Source ways |",
        "|---|---:|---:|---|---|",
    ]
    for c in report["components"]:
        rows.append(
            f"| C{c['component']} | {c['node_count']} | {c['directed_edge_count']} | "
            + ("; ".join(f"{d['name']} ({d['id']})" for d in c["destinations"]) or "None")
            + " | "
            + ", ".join(map(str, c["source_way_ids"]))
            + " |"
        )
    rows += [
        "\n## Unanchored catalog destinations\n",
        "Containment is descriptive only; it does not establish a usable door.\n",
        "| Destination | Identity | Containing imported footprint(s) |",
        "|---|---|---|",
    ]
    for p in report["unanchored_destinations"]:
        rows.append(
            f"| {p['name']} | {p['id']} | {', '.join(p['footprint_containment_only']) or 'None'} |"
        )
    (output / "README.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
