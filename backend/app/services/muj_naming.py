"""Reproducible, sanitized naming evidence. No database or graph mutation."""

import hashlib
import html
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from app.services.imports import stable_id
from app.services.muj_setup import CAMPUS_ID
from app.services.osm_conversion import ATTRIBUTION, tags

ROOT = Path(__file__).resolve().parents[3]
INVENTORY = ROOT / "data/muj-naming/inventory.json"


def build_inventory(raw):
    manifest = json.loads((ROOT / "data/muj-v2/manifest.json").read_bytes())
    if hashlib.sha256(raw).hexdigest() != manifest["source_sha256"]:
        raise ValueError("Source checksum mismatch; no naming evidence generated")
    source = ET.fromstring(raw)
    elements = {
        f"osm-{kind}-{e.attrib['id']}": e
        for kind in ("node", "way", "relation")
        for e in source.findall(kind)
    }
    records = []
    for name, digest in sorted(manifest["files"].items()):
        if Path(name).name != name:
            raise ValueError("Invalid preparation path")
        content = (ROOT / "data/muj-v2" / name).read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError("Pinned preparation checksum mismatch")
        if name.startswith("batch-"):
            records.extend(json.loads(content)["records"])
    members = {}
    for e in source.findall("way"):
        for ref in sorted({n.attrib["ref"] for n in e.findall("nd")}):
            members.setdefault("osm-node-" + ref, []).append(e)
    entrances = sorted(
        (
            r["external_id"]
            for r in records
            if r["entity"] == "places" and r["data"]["kind"] == "entrance"
        ),
        key=lambda x: int(x.split("-")[-1]),
    )
    markers = {i: f"E{n:02}" for n, i in enumerate(entrances, 1)}
    result = []
    for row in records:
        entity, external, data = row["entity"], row["external_id"], row["data"]
        if entity not in {"places", "nodes", "buildings", "anchors"}:
            continue
        base = re.sub(r"-part-[0-9]+$", "", external)
        element = elements.get(base)
        evidence = tags(element) if element is not None else {}
        ways = [{"osm_way": e.attrib["id"], "tags": tags(e)} for e in members.get(external, [])]
        building_ways = [w for w in ways if w["tags"].get("building")]
        label = data.get("name", data.get("label"))
        proposed = label
        confidence = "existing imported label; not field verified"
        reason = "Retain existing label; no new identity asserted."
        if label and re.fullmatch(r"Mapped entrance [0-9]+", label):
            proposed = None
            confidence = "unresolved; owner identification required"
            reason = "No unique explicitly named containing source building way. Proximity is not identity."
            if len(building_ways) == 1 and building_ways[0]["tags"].get("name"):
                proposed = building_ways[0]["tags"]["name"] + " entrance"
                confidence = "source-supported explicit outline membership; not surveyed"
                reason = f"Entrance node is an explicit nd member of named building way {building_ways[0]['osm_way']}. No main/accessibility claim."
        if label and label.startswith("OSM building "):
            proposed = None
            confidence = "unnamed source building; owner identification required"
            reason = "No source name; retain administrative provenance without inventing building identity."
        if entity == "nodes" and re.fullmatch(r"OSM junction [0-9]+", label or ""):
            proposed = None
            confidence = "unnamed intermediate; no stored rename proposed"
            reason = "Public directions use neutral path wording; stable ID/label/evidence remain administrative provenance."
        result.append(
            {
                "entity": entity,
                "id": str(stable_id(CAMPUS_ID, entity, external)),
                "external_id": external,
                "marker": markers.get(external) if entity in {"nodes", "places"} else None,
                "current_label": label,
                "proposed_name": proposed,
                "confidence": confidence,
                "reason": reason,
                "source_tags": evidence,
                "explicit_member_ways": ways,
                "existing_building_id": data.get("building_id"),
                "point": data.get("point"),
                "anchor_place_id": str(stable_id(CAMPUS_ID, "places", data["place_id"]))
                if entity == "anchors"
                else None,
                "anchor_node_id": str(stable_id(CAMPUS_ID, "nodes", data["node_id"]))
                if entity == "anchors"
                else None,
            }
        )
    # The same source-supported entrance name may label its actual anchored graph
    # node; never transfer a nearby building name to a node.
    supported = {
        r["external_id"]: r
        for r in result
        if r["entity"] == "places"
        and r["proposed_name"]
        and r["proposed_name"] != r["current_label"]
    }
    for row in result:
        if row["entity"] == "nodes" and row["external_id"] in supported:
            proof = supported[row["external_id"]]
            for key in ("proposed_name", "confidence", "reason"):
                row[key] = proof[key]
    return {
        "format": "scns-muj-naming-v1",
        "campus_id": str(CAMPUS_ID),
        "source_sha256": manifest["source_sha256"],
        "attribution": ATTRIBUTION,
        "records": sorted(result, key=lambda r: (r["entity"], r["id"])),
    }


def draw_map(raw, inventory, bounds, title, width=1000, height=800):
    """Source footprints and paths are context, never new topology/entrance evidence."""
    root = ET.fromstring(raw)
    positions = {
        n.attrib["id"]: (float(n.attrib["lon"]), float(n.attrib["lat"]))
        for n in root.findall("node")
    }
    west, south, east, north = bounds
    factor = math.cos(math.radians((south + north) / 2))
    scale = min((width - 60) / ((east - west) * factor), (height - 135) / (north - south))

    def xy(p):
        return 30 + (p[0] - west) * factor * scale, 75 + (north - p[1]) * scale

    def inside(p):
        return west <= p[0] <= east and south <= p[1] <= north

    esc = html.escape
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img"><title>{esc(title)}</title>',
        '<defs><clipPath id="map"><rect x="20" y="65" width="960" height="660"/></clipPath></defs>',
        f'<rect width="{width}" height="{height}" fill="#faf9f4"/>',
        f'<text x="24" y="28" font-family="sans-serif" font-size="20" font-weight="bold">{esc(title)}</text>',
        '<text x="24" y="51" font-family="sans-serif" font-size="12">Source context only · orange: identify · purple: proposed · green: already named · no access/floor inference</text>',
        '<g clip-path="url(#map)">',
    ]
    labels = []
    for way in root.findall("way"):
        t = tags(way)
        points = [
            positions[n.attrib["ref"]] for n in way.findall("nd") if n.attrib["ref"] in positions
        ]
        if not points or not any(inside(p) for p in points):
            continue
        coords = " ".join(f"{x:.2f},{y:.2f}" for x, y in map(xy, points))
        if "building" in t:
            svg.append(
                f'<polygon points="{coords}" fill="#dedbd2" stroke="#aaa69b" stroke-width="1"/>'
            )
        elif "highway" in t:
            svg.append(
                f'<polyline points="{coords}" fill="none" stroke="#8b9ba0" stroke-width="2"/>'
            )
        if t.get("name") and ("building" in t or t.get("highway") in {"service", "tertiary"}):
            center = tuple(sum(p[k] for p in points) / len(points) for k in (0, 1))
            if inside(center):
                x, y = xy(center)
                labels.append(
                    f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#454943">{esc(t["name"])}</text>'
                )
    svg.extend(labels)
    for row in inventory["records"]:
        if row["entity"] != "places" or not row["marker"]:
            continue
        p = row["point"]["coordinates"]
        if not inside(p):
            continue
        x, y = xy(p)
        n = int(row["marker"][1:])
        dx = 23 if n % 2 else -23
        dy = -20 if n % 3 else 23
        color = (
            "#ae520e"
            if row["proposed_name"] is None
            else "#6147a1"
            if row["current_label"] != row["proposed_name"]
            else "#167163"
        )
        svg.extend(
            [
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>',
                f'<path d="M{x:.1f},{y:.1f} L{x + dx:.1f},{y + dy:.1f}" stroke="{color}"/>',
                f'<rect x="{x + dx - 16:.1f}" y="{y + dy - 10:.1f}" width="32" height="20" rx="4" fill="{color}"/>',
                f'<text x="{x + dx:.1f}" y="{y + dy + 4:.1f}" text-anchor="middle" font-family="sans-serif" font-size="11" fill="white">{row["marker"]}</text>',
            ]
        )
    svg.extend(
        [
            "</g>",
            f'<text x="24" y="755" font-family="sans-serif" font-size="12">{esc(ATTRIBUTION)}</text>',
            '<text x="24" y="777" font-family="sans-serif" font-size="12">WGS84 longitude/latitude · source tags may be incomplete · paths include excluded/indoor source context</text>',
            "</svg>",
        ]
    )
    return "\n".join(svg) + "\n"
