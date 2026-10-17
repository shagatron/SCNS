"""Offline source-pair accounting. No geometry repair, graph writes or publication."""

import csv
import hashlib
import html
import json
import math
import xml.etree.ElementTree as ET
from collections import defaultdict

from shapely.geometry import LineString, Point, Polygon, shape

from app.services.muj_diagnostics import diagnose
from app.services.osm_conversion import WALK, access_reason, encode, tags, vertical_reason


def account(raw, preparation):
    diagnostic = diagnose(raw, preparation)  # Hashes, bounded XML, byte reproduction first.
    root = ET.fromstring(raw)
    nodes = {int(e.attrib["id"]): e for e in root.findall("node")}
    positions = {i: [float(e.attrib["lon"]), float(e.attrib["lat"])] for i, e in nodes.items()}
    ways = {int(e.attrib["id"]): e for e in root.findall("way")}
    refs = {i: [int(n.attrib["ref"]) for n in e.findall("nd")] for i, e in ways.items()}
    batches = [json.loads(p.read_bytes()) for p in sorted(preparation.glob("batch-*.json"))]
    records = [r for b in batches for r in b["records"]]
    entities = {
        k: {r["external_id"]: r["data"] for r in records if r["entity"] == k}
        for k in ("edges", "nodes", "anchors", "places")
    }
    membership = defaultdict(set)
    supported = defaultdict(set)
    for c in diagnostic["components"]:
        for n in c["source_node_ids"]:
            membership[n].add(c["component"])
        for a in c["destinations"]:
            supported[c["component"]].add(a["id"])
    # Match ordered source-reference hashes, not geometry coincidence or nearest nodes.
    represented = defaultdict(list)
    for identity, edge in sorted(entities["edges"].items()):
        way = int(identity.split("-")[2])
        rr = refs[way]
        found = []
        for left, n in enumerate(rr):
            if f"osm-node-{n}" not in {edge["from_node_id"], edge["to_node_id"]}:
                continue
            for right in range(left + 1, len(rr)):
                part = rr[left : right + 1]
                canonical = min(tuple(part), tuple(reversed(part)))
                signature = hashlib.sha256(encode(canonical)).hexdigest()[:32]
                if (
                    edge["physical_path_id"]
                    == f"osm-way-{way}-{canonical[0]}-{canonical[-1]}-{signature}"
                ):
                    ordered = part if edge["from_node_id"] == f"osm-node-{part[0]}" else part[::-1]
                    if edge["geometry"]["coordinates"] != [positions[n] for n in ordered]:
                        raise ValueError(
                            "Stored geometry differs from full ordered source polyline"
                        )
                    found.append((left, right, ordered[0] == part[0]))
        if len(found) != 1:
            raise ValueError("Ambiguous or missing source-reference occurrence")
        left, right, forward = found[0]
        for index in range(left, right):
            represented[way, index].append({"edge_id": identity, "source_forward": forward})
    coverage = shape(diagnostic["scope"]["coverage"])
    footprints = {}
    for w, element in ways.items():
        rr = refs[w]
        if "building" in tags(element) and len(rr) >= 4 and rr[0] == rr[-1]:
            polygon = Polygon([positions[n] for n in rr])
            if polygon.is_valid:
                footprints[w] = polygon
    decisions = defaultdict(set)
    for d in diagnostic["source_decisions"]:
        decisions[d["source"]].add(d["reason"])
    rows = []
    for way, element in sorted(ways.items()):
        t, rr = tags(element), refs[way]
        if "highway" not in t:
            continue
        for index, (a, b) in enumerate(zip(rr, rr[1:], strict=False)):
            points = [positions[a], positions[b]]
            covered = coverage.covers(LineString(points))
            why = []
            for reason in (vertical_reason(t), access_reason(t)):
                if reason:
                    why.append("way:" + reason)
            if t["highway"] not in WALK:
                why.append("way:unsupported_highway")
            if t.get("area") == "yes":
                why.append("way:pedestrian_area_not_a_line")
            if t.get("construction"):
                why.append("way:not_existing_path")
            if t.get("oneway:foot", "no") not in {"yes", "1", "true", "-1", "no", "false", "0"}:
                why.append("way:unsupported_foot_direction")
            if not covered:
                why.append("pair:outside_exact_polygon_union_or_gap")
            if points[0] == points[1]:
                why.append("pair:repeated_position")
            # A blocked endpoint closes its entire original junction-to-junction arc,
            # not just the tiny pair touching the door/barrier. Find those source cuts
            # independently of the emitted graph below.
            for n in (a, b):
                for reason in (access_reason(tags(nodes[n])), vertical_reason(tags(nodes[n]))):
                    if reason:
                        why.append(f"node/{n}:{reason}")
            stored = represented[way, index]
            reasons = sorted(set(why))
            recorded = sorted(decisions[f"osm-way-{way}"])
            if not stored and not reasons:
                # Do not launder a whole-way converter diagnostic into evidence
                # about an unexplained individual pair. It needs investigation.
                reasons = ["UNEXPLAINED_OMISSION"]
            components = sorted(membership[a] | membership[b])
            direction = t.get("oneway:foot", "no")
            expected = (
                {True}
                if direction in {"yes", "1", "true"}
                else {False}
                if direction == "-1"
                else {False, True}
            )
            directions = {e["source_forward"] for e in stored}
            if stored and (reasons or directions != expected):
                raise ValueError(
                    f"Represented pair contradicts source access/coverage/direction: {way}/{index}"
                )
            rows.append(
                {
                    "segment": f"W{way}:S{index + 1}",
                    "way_id": way,
                    "pair_index": index,
                    "from_source_node": a,
                    "to_source_node": b,
                    "geometry": points,
                    "way_tags": t,
                    "endpoint_tags": {str(n): tags(nodes[n]) for n in (a, b)},
                    "within_coverage": covered,
                    "touches_coverage": coverage.intersects(LineString(points)),
                    "represented": bool(stored),
                    "stored_edges": stored,
                    "eligibility": "represented" if stored else "excluded_or_review",
                    "reasons": reasons,
                    "recorded_way_decisions": recorded,
                    "components": components,
                    "component_destinations": sorted({p for c in components for p in supported[c]}),
                    "direct_anchors": sorted(
                        k
                        for k, v in entities["anchors"].items()
                        if v["node_id"] in {f"osm-node-{a}", f"osm-node-{b}"}
                    ),
                    "building_interior_context": [
                        {
                            "way_id": w,
                            "tags": tags(ways[w]),
                            "both_endpoints_explicit_outline_members": a in refs[w]
                            and b in refs[w],
                            "assessment": "Source geometry/outline overlap only; not a new passage, floor, identity or access approval.",
                        }
                        for w, polygon in footprints.items()
                        if LineString(points).relate_pattern(polygon, "T********")
                    ],
                    "proposed_change": None,
                }
            )
    # A shared source reference must be a stored junction wherever eligible ways
    # meet. Internal shape vertices cannot secretly join separate stored arcs.
    uses = defaultdict(set)
    for row in rows:
        if row["represented"]:
            for n in (row["from_source_node"], row["to_source_node"]):
                uses[n].add(row["way_id"])
    junctions = []
    for n, ww in sorted(uses.items()):
        if len(ww) > 1:
            stored = f"osm-node-{n}" in entities["nodes"]
            junctions.append({"node": n, "ways": sorted(ww), "stored_junction": stored})
            if not stored:
                raise ValueError(f"Shared eligible source node is not a stored junction: {n}")
    entrances = []
    for n, element in sorted(nodes.items()):
        t = tags(element)
        if "entrance" not in t or not coverage.covers(Point(positions[n])):
            continue
        ext = f"osm-node-{n}"
        anchored = ext in entities["anchors"]
        reasons = [x for x in (access_reason(t), vertical_reason(t)) if x]
        if t["entrance"] in {"no", "emergency", "exit"}:
            reasons.append("not_public_arrival_entrance")
        if not anchored and not reasons:
            reasons.append("no_accepted_outdoor_path_at_exact_source_node")
        entrances.append(
            {
                "node": n,
                "tags": t,
                "anchored": anchored,
                "member_ways": sorted(w for w, rr in refs.items() if n in rr),
                "reasons": reasons,
            }
        )
    unexplained = [r["segment"] for r in rows if "UNEXPLAINED_OMISSION" in r["reasons"]]
    return {
        "format": "scns-muj-all-source-pairs-v1",
        "source_sha256": diagnostic["source_sha256"],
        "manifest_sha256": diagnostic["preparation_manifest_sha256"],
        "scope": diagnostic["scope"],
        "counts": {
            "highway_ways": len({r["way_id"] for r in rows}),
            "source_pairs": len(rows),
            "represented_pairs": sum(r["represented"] for r in rows),
            "stored": diagnostic["counts"],
            "weak_components": len(diagnostic["components"]),
            "unanchored_destinations": len(diagnostic["unanchored_destinations"]),
        },
        "unexplained_omissions": unexplained,
        "proposed_changes": [],
        "segments": rows,
        "junctions": junctions,
        "entrances": entrances,
        "components": diagnostic["components"],
        "unanchored_destinations": diagnostic["unanchored_destinations"],
        "qualification": "Original OSM only; no screenshot tracing, survey, access approval or publication. No graph patch justified automatically.",
    }


def write_accounting(report, output):
    output.mkdir(parents=True, exist_ok=True)
    (output / "segments.json").write_bytes(encode(report))
    keys = list(report["segments"][0])
    with (output / "segments.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        for row in report["segments"]:
            writer.writerow(
                {
                    k: json.dumps(v, ensure_ascii=False, sort_keys=True)
                    if isinstance(v, (dict, list))
                    else v
                    for k, v in row.items()
                }
            )


def draw(report, raw, bounds, questions, title):
    """Only original node-pair lines and original footprint context; no connectors."""
    west, south, east, north = bounds
    factor = math.cos(math.radians((south + north) / 2))
    scale = min(1040 / ((east - west) * factor), 660 / (north - south))

    def xy(p):
        return 45 + (p[0] - west) * factor * scale, 90 + (north - p[1]) * scale

    def points(pp):
        return " ".join(f"{x:.2f},{y:.2f}" for x, y in map(xy, pp))

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1140 810" role="img"><title>{html.escape(title)}</title>',
        '<defs><clipPath id="map"><rect x="30" y="80" width="1080" height="675"/></clipPath></defs>',
        '<rect width="1140" height="810" fill="#faf9f4"/>',
        f'<text x="30" y="30" font-family="sans-serif" font-size="22">{html.escape(title)}</text>',
        '<text x="30" y="54" font-family="sans-serif" font-size="13">Green: retained source paths · dashed red: excluded/review · numbered questions · no proposed additions</text>',
        '<g clip-path="url(#map)">',
    ]
    root = ET.fromstring(raw)
    pp = {
        n.attrib["id"]: [float(n.attrib["lon"]), float(n.attrib["lat"])]
        for n in root.findall("node")
    }
    for w in root.findall("way"):
        if "building" in tags(w) or "leisure" in tags(w):
            coords = [pp[n.attrib["ref"]] for n in w.findall("nd") if n.attrib["ref"] in pp]
            if len(coords) > 2:
                svg.append(
                    f'<polyline points="{points(coords)}" fill="#e5e2dc" stroke="#c4bfb7" stroke-width="1"/>'
                )
                if name := tags(w).get("name"):
                    x, y = xy(coords[0])
                    svg.append(
                        f'<text x="{x:.2f}" y="{y:.2f}" font-size="8" font-family="sans-serif" fill="#777">{html.escape(name[:60])}</text>'
                    )
    for row in report["segments"]:
        color = "#19745f" if row["represented"] else "#b44348"
        dash = "" if row["represented"] else ' stroke-dasharray="4 3"'
        svg.append(
            f'<polyline points="{points(row["geometry"])}" fill="none" stroke="{color}" stroke-width="1.8"{dash}><title>{row["segment"]}: {html.escape(", ".join(row["reasons"]) or "retained")}</title></polyline>'
        )
    for c in report["components"]:
        x, y = xy(pp[str(c["source_node_ids"][0])])
        svg.append(
            f'<text x="{x:.2f}" y="{y - 4:.2f}" font-family="sans-serif" font-size="10" fill="#075b43">C{c["component"]}</text>'
        )
    if east - west < 0.001:
        for identity, p in pp.items():
            if west <= p[0] <= east and south <= p[1] <= north:
                x, y = xy(p)
                svg.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2" fill="#222"/><text x="{x + 4:.2f}" y="{y:.2f}" font-family="sans-serif" font-size="8">{identity}</text>')
    for q in questions:
        x, y = xy(q["point"])
        svg.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="13" fill="#fff" stroke="#222"/><text x="{x:.2f}" y="{y + 4:.2f}" text-anchor="middle" font-family="sans-serif" font-size="12">{q["id"]}</text>'
        )
    svg.extend(
        [
            "</g>",
            '<text x="30" y="787" font-family="sans-serif" font-size="12">North up · © OpenStreetMap contributors / ODbL1.0 · source topology only, not physical/accessibility verification</text>',
            "</svg>",
        ]
    )
    return "\n".join(svg) + "\n"


def write_atlas(report, raw, output):
    """Stable numbered source-only questions, not implied or proposed connectors."""
    root = ET.fromstring(raw)
    nodes = {
        int(n.attrib["id"]): [float(n.attrib["lon"]), float(n.attrib["lat"])]
        for n in root.findall("node")
    }
    questions = [
        (
            1,
            10778271605,
            "10778271605; ways1159217177/1245274146",
            "What current pedestrian audience is permitted at the explicitly private subway entrance? Retain private exclusion until documented permission/source evidence supersedes it.",
        ),
        (
            2,
            10733816254,
            "10733816254/255/256/257; ways1154145270/1154145273/1246099090/1154145269",
            "Clarify approach/tunnel extent, actual landings and permitted road-gap coverage. Shared source chain exists, but tunnel:name, layer=-1, stairs and polygon gap remain unresolved. No new source evidence resolves the earlier finding.",
        ),
        (
            3,
            12585506492,
            "Library node12585506492; Administrative Block way1158522861",
            "Identify an actual permitted Library arrival door, floor and continuous mapped approach. Library display point/outline containment and screenshot wording do not establish an entrance.",
        ),
        (
            4,
            10773902923,
            "ways926463927/1158509500/1158055386/1247085145; entrances10773902923/11664524407",
            "Which corridor sections are outdoor, covered or indoor, on which floor and through which permitted doors? Retain conservative corridor/level exclusions. Existing E22 identity stays TMA Pai Auditorium entrance; no new identity inferred.",
        ),
        (
            5,
            11809063446,
            "nodes11809063446/11593739317 and11594340527/11809063447; ways1247085147/1271670518/1245278034",
            "Do the distinct near-duplicate source stubs actually join at the same permitted level/door? Need source/annotated evidence before any merge; proximity alone is insufficient and physical separation is not established.",
        ),
        (
            6,
            10770949033,
            "ways1158191367/1158191368/1164590129 (C8)",
            "If a connection from this mapped sports-path component is wanted, identify its actual continuous permitted approach and shared source-node evidence. No excluded highway touches this component; source does not provide the missing join.",
        ),
        (
            7,
            10771011953,
            "way1158192973 (C16)",
            "Identify a continuous permitted approach to this isolated hostel-side footway if needed. No excluded highway shares a retained node; do not snap it to adjacent lanes.",
        ),
        (
            8,
            10634009265,
            "ways1141643441/1141643442/1141643443 (C6)",
            "Identify a continuous permitted approach to the source-labelled jogging loop if needed. No excluded highway shares its retained nodes; no nearby-road shortcut is supported.",
        ),
    ]
    questions = [
        {"id": identity, "point": nodes[node], "source_ids": sources, "question": text}
        for identity, node, sources, text in questions
    ]
    (output / "questions.json").write_bytes(encode(questions))
    bounds = shape(report["scope"]["extent"]).bounds
    maps = {
        "overview": (bounds, "All-source MUJ path accounting · questions1–8"),
        "academic": (
            (75.5631, 26.8409, 75.5676, 26.8441),
            "Academic paths, Library context and corridor questions",
        ),
        "hostel-crossing": (
            (75.5604, 26.8398, 75.5644, 26.8431),
            "Hostel paths and unresolved boundary/subway approaches",
        ),
        "cricket": (
            (75.5625, 26.8440, 75.5682, 26.8470),
            "Northern campus / sports-path source context",
        ),
        "near-pairs": (
            (75.56405, 26.8428, 75.56455, 26.84325),
            "Distinct source stubs · no proximity merge (question5)",
        ),
    }
    for name, (bounds, title) in maps.items():
        (output / f"{name}.svg").write_text(
            draw(report, raw, bounds, questions, title), encoding="utf-8"
        )
    (output / "questions.md").write_text(
        "# Questions requiring campus/source evidence\n\n"
        "Numbered circles match the [overview](overview.svg) and detail maps. Red dashed lines are excluded **original OSM geometry**, never proposed connections. Distinct source IDs remain distinct; no physical separation or access approval is inferred. Coordinates are original OSM mapping, not screenshot tracing or a survey.\n\n"
        "| Map number | Exact OSM references | Specific evidence needed |\n|---|---|---|\n"
        + "\n".join(f"| {q['id']} | {q['source_ids']} | {q['question']} |" for q in questions)
        + "\n\nScreenshot-only apparent connections are questions, not routing data. No Google labels, imagery or highlighted geometry are used in any figure or dataset. © OpenStreetMap contributors / ODbL1.0.\n",
        encoding="utf-8",
    )
