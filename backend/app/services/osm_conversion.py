"""Conservative, offline OSM -> import-v1 preparation. Never publishes or repairs geometry."""

import hashlib
import json
import math
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import LineString, MultiPolygon, Point, Polygon, mapping
from shapely.ops import polygonize, unary_union
from shapely.validation import explain_validity

CAMPUS_WAYS = (495716022, 1158554635)
CODE = "MUJ"
TIMEZONE = "Asia/Kolkata"
ATTRIBUTION = "© OpenStreetMap contributors · https://www.openstreetmap.org/copyright · ODbL 1.0"
RIGHTS = "OpenStreetMap database, ODbL 1.0; attribution and derivative-database share-alike obligations apply. Not official MUJ data or a field survey."
VERSION = "muj-osm-v1"
WALK = {
    "path",
    "footway",
    "pedestrian",
    "steps",
    "service",
    "residential",
    "living_street",
    "unclassified",
    "track",
}
DENIED = {
    "no",
    "private",
    "customers",
    "delivery",
    "permit",
    "agricultural",
    "forestry",
    "destination",
}


def encode(value):
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def tags(element):
    # Contributor metadata is never carried into derivative data.
    return {
        t.attrib["k"]: t.attrib["v"]
        for t in element.findall("tag")
        if t.attrib["k"] not in {"user", "uid", "changeset", "created_by"}
    }


def access_reason(t):
    if any(
        k in t
        for k in (
            "foot:conditional",
            "access:conditional",
            "oneway:foot:conditional",
            "foot:forward",
            "foot:backward",
            "opening_hours",
        )
    ):
        return "conditional_or_directional_access_requires_review"
    if t.get("foot", "").lower() in DENIED:
        return "foot_access"
    if t.get("access", "").lower() in DENIED and t.get("foot") not in {
        "yes",
        "designated",
        "permissive",
    }:
        return "access_restriction"
    if t.get("barrier") and t.get("foot") not in {"yes", "designated", "permissive"}:
        return "unverified_barrier"
    return None


def vertical_reason(t):
    if (
        t.get("indoor") not in {None, "no"}
        or "room" in t
        or "corridor" in (t.get("name", "") + t.get("footway", "")).lower()
    ):
        return "indoor_or_room"
    if (
        any(t.get(k, "0") not in {"0", "0.0"} for k in ("level", "layer"))
        or t.get("highway") == "elevator"
    ):
        return "unsupported_level_or_layer"
    if any(t.get(k) not in {None, "no"} for k in ("bridge", "tunnel")) or "tunnel:name" in t:
        return "grade_separated_requires_review"
    return None


def convert(raw: bytes, *, batch_size=400):
    if len(raw) > 5 * 1024 * 1024 or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("Only bounded OSM XML without DTD/entities is accepted (5MiB maximum)")
    if not 1 <= batch_size <= 500:
        raise ValueError("Use 1–500 rows per batch, below current import limits")
    root = ET.fromstring(raw)
    if root.tag != "osm":
        raise ValueError("Expected OSM XML")
    elements = {kind: {} for kind in ("node", "way", "relation")}
    for element in root:
        if element.tag not in elements:
            continue
        identity = int(element.attrib["id"])
        if identity in elements[element.tag]:
            raise ValueError("Duplicate OSM element identity")
        elements[element.tag][identity] = element
    if sum(map(len, elements.values())) > 100000:
        raise ValueError("Preparation element limit exceeded")
    nodes = {
        i: (float(e.attrib["lon"]), float(e.attrib["lat"])) for i, e in elements["node"].items()
    }
    if any(
        not math.isfinite(x) or not math.isfinite(y) or not -180 <= x <= 180 or not -90 <= y <= 90
        for x, y in nodes.values()
    ):
        raise ValueError("Invalid WGS84 node position")
    report = {
        "converter": VERSION,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_counts": {k: len(v) for k, v in elements.items()},
        "decisions": [],
        "provenance": {},
        "length_policy": "PostGIS geography full polyline; estimated mapping distances, not surveyed",
        "attribution": ATTRIBUTION,
    }
    decisions = report["decisions"]

    def note(kind, identity, reason):
        item = {"source": f"osm-{kind}-{identity}", "reason": reason}
        element = elements.get(kind, {}).get(identity)
        if element is not None:
            item["tags"] = tags(element)
            if kind == "relation":
                item["missing_members"] = [
                    {"type": m.attrib["type"], "id": int(m.attrib["ref"])}
                    for m in element.findall("member")
                    if int(m.attrib["ref"]) not in elements.get(m.attrib["type"], {})
                ]
        decisions.append(item)

    def refs(e):
        ids = [int(n.attrib["ref"]) for n in e.findall("nd")]
        if any(i not in nodes for i in ids):
            raise ValueError("missing_node_reference")
        return ids

    def polygon(e):
        ids = refs(e)
        if len(ids) < 4 or ids[0] != ids[-1]:
            raise ValueError("polygon_not_closed")
        poly = Polygon([nodes[i] for i in ids])
        if not poly.is_valid or poly.is_empty or poly.area == 0:
            raise ValueError("invalid_polygon: " + explain_validity(poly))
        return poly

    campus_parts = []
    for i in CAMPUS_WAYS:
        if i not in elements["way"]:
            raise ValueError(f"Required mapped MUJ campus polygon {i} is missing")
        campus_parts.append(polygon(elements["way"][i]))
    coverage = unary_union(campus_parts)
    extent = coverage.convex_hull
    report["scope"] = {
        "academic_way": CAMPUS_WAYS[0],
        "hostel_way": CAMPUS_WAYS[1],
        "coverage": mapping(coverage),
        "extent_policy": "Convex hull of the two exact mapped university polygons is an operational display extent, NOT a surveyed ownership boundary. Features must be covered by the exact polygons. Gap/off-campus features are excluded, including unverified subway links.",
        "extent": mapping(extent),
        "gap_in_hull_area_fraction": round(1 - coverage.area / extent.area, 6),
    }
    campus = {
        "code": CODE,
        "name": "Manipal University Jaipur (OSM preparation)",
        "timezone": TIMEZONE,
        "is_demo": False,
        "center": mapping(campus_parts[0].representative_point()),
        "boundary": mapping(extent),
    }
    records = []
    buildings = []
    catalog = {}
    graph = defaultdict(set)

    def add(entity, external, data, source=None, t=None):
        records.append({"entity": entity, "external_id": external, "data": data})
        if source:
            report["provenance"][f"{entity}:{external}"] = {"source": source, "tags": t or {}}

    def evidence(kind, i, t):
        useful = {
            k: t[k]
            for k in (
                "highway",
                "name",
                "surface",
                "foot",
                "access",
                "oneway",
                "oneway:foot",
                "wheelchair",
                "level",
                "layer",
                "entrance",
            )
            if k in t
        }
        return (
            f"OSM {kind}/{i}; "
            + json.dumps(useful, ensure_ascii=False, sort_keys=True)[:1200]
            + "; ODbL; no field/accessibility verification."
        )

    def destination(external, t, point, building=None, kind=None):
        name = t.get("name") or t.get("ref")
        if not name:
            return
        if len(name) > 160:
            note("feature", external, "name_exceeds_contract")
            return
        kind = kind or (
            "library"
            if t.get("amenity") == "library" or "library" in name.lower()
            else "cafe"
            if t.get("amenity") in {"cafe", "restaurant", "food_court", "fast_food"}
            else "building"
            if building
            else "help"
        )
        data = {
            "code": external.replace("-", "_").upper(),
            "name": name,
            "kind": kind,
            "visibility": "restricted" if access_reason(t) else "public",
            "description": evidence("feature", external, t)
            + " Display point only; routes require explicit mapped entrance anchors.",
            "point": mapping(point),
        }
        if building:
            data["building_id"] = building
        add("places", external, data, external, t)
        catalog[external] = {"name": name, "anchored": False}

    member_ways = set()
    # Stitch relation rings from complete member ways without snapping or repairing.
    for i, e in sorted(elements["relation"].items()):
        t = tags(e)
        if t.get("type") != "multipolygon":
            note(
                "relation",
                i,
                "excluded_bus_relation" if t.get("route") == "bus" else "unsupported_relation",
            )
            continue
        try:
            rings = {"outer": [], "inner": []}
            members = []
            for member in e.findall("member"):
                mid = int(member.attrib["ref"])
                role = member.attrib.get("role") or "outer"
                if (
                    member.attrib["type"] != "way"
                    or mid not in elements["way"]
                    or role not in rings
                ):
                    raise ValueError("missing_or_unsupported_relation_member")
                members.append(mid)
                rings[role].append(LineString([nodes[n] for n in refs(elements["way"][mid])]))
            outer = list(polygonize(rings["outer"]))
            inner = list(polygonize(rings["inner"]))
            if (
                not outer
                or sum(len(p.exterior.coords) - 1 for p in outer)
                != sum(len(line.coords) - 1 for line in rings["outer"])
                or sum(len(p.exterior.coords) - 1 for p in inner)
                != sum(len(line.coords) - 1 for line in rings["inner"])
            ):
                raise ValueError("relation_rings_not_closed_or_ambiguous")
            if any(sum(o.covers(h) for o in outer) != 1 for h in inner):
                raise ValueError("uncontained_or_ambiguous_hole")
            polys = [
                Polygon(o.exterior.coords, [h.exterior.coords for h in inner if o.covers(h)])
                for o in outer
            ]
            if not MultiPolygon(polys).is_valid or any(not p.is_valid for p in polys):
                raise ValueError("invalid_relation_geometry")
            member_ways.update(members)
            if not t.get("building") or vertical_reason(t):
                note("relation", i, "non_building_or_indoor_relation")
                continue
            for part, p in enumerate(sorted(polys, key=lambda p: p.wkt)):
                ext = f"osm-relation-{i}-part-{part}"
                if coverage.covers(p):
                    buildings.append((ext, p, t))
                else:
                    note("relation", i, "outside_exact_campus_coverage")
        except (ValueError, KeyError) as exc:
            # Never fall back to a broken relation's member polygons as filled buildings.
            member_ways.update(
                int(m.attrib["ref"]) for m in e.findall("member") if m.attrib["type"] == "way"
            )
            note("relation", i, str(exc))
    for i, e in sorted(elements["way"].items()):
        t = tags(e)
        if "building" not in t or t.get("building") == "no" or i in member_ways:
            continue
        if (
            "room" in t
            or "indoor" in t
            or "level" in t
            or t.get("name", "").isdigit()
            or "corridor" in t.get("addr:street", "").lower()
        ):
            note("way", i, "room_or_level_tagged_building_quarantined")
            continue
        try:
            p = polygon(e)
            if not coverage.covers(p):
                note("way", i, "building_outside_exact_campus_coverage")
                continue
            buildings.append((f"osm-way-{i}", p, t))
        except ValueError as exc:
            note("way", i, str(exc))
    seen_polygons = set()
    for external, p, t in buildings:
        key = p.normalize().wkb_hex
        if key in seen_polygons:
            note("feature", external, "duplicate_polygon")
            continue
        seen_polygons.add(key)
        if len(p.interiors) > 9 or any(len(r.coords) > 500 for r in [p.exterior, *p.interiors]):
            note("feature", external, "polygon_exceeds_import_contract")
            continue
        add(
            "buildings",
            external,
            {
                "code": external.replace("-", "_").upper(),
                "name": t.get("name", f"OSM building {external}")[:160],
                "footprint": mapping(p),
                "visibility": "restricted" if access_reason(t) else "public",
            },
            external,
            t,
        )
        destination(external, t, p.representative_point(), external)
    add("frames", "osm-outdoor-wgs84", {"code": "OSM_WGS84", "kind": "outdoor"})
    eligible = []
    uses = Counter()
    for i, e in sorted(elements["way"].items()):
        t = tags(e)
        if "highway" not in t:
            if "indoor" in t:
                note("way", i, "indoor_catalog_preparation_only")
            continue
        reason = vertical_reason(t) or access_reason(t)
        if not reason and t["highway"] not in WALK:
            reason = "unsupported_highway"
        if not reason and t.get("area") == "yes":
            reason = "pedestrian_area_not_a_line"
        if not reason and (
            t.get("construction") or t.get("highway") in {"construction", "proposed"}
        ):
            reason = "not_existing_path"
        if reason:
            note("way", i, reason)
            continue
        try:
            ids = refs(e)
            line = LineString([nodes[n] for n in ids])
            if not line.is_valid or not line.is_simple or line.length == 0:
                raise ValueError("invalid_line")
            if not coverage.covers(line):
                raise ValueError("path_outside_exact_campus_coverage_or_cross_campus_gap")
            if t.get("oneway:foot", "no") not in {"no", "yes", "1", "true", "-1", "false", "0"}:
                raise ValueError("unsupported_foot_direction")
            eligible.append((i, ids, t))
            uses.update(set(ids))
        except (ValueError, KeyError) as exc:
            note("way", i, str(exc))
    needed = set()
    segments = []
    for i, ids, t in eligible:
        # Shared node IDs establish topology; geometric intersections alone never do.
        cuts = {0, len(ids) - 1}
        if ids[0] == ids[-1]:
            cuts.add(len(ids) // 2)
        cuts.update(
            j
            for j, n in enumerate(ids)
            if uses[n] > 1
            or "entrance" in tags(elements["node"][n])
            or tags(elements["node"][n]).get("barrier")
            or access_reason(tags(elements["node"][n]))
            or vertical_reason(tags(elements["node"][n]))
        )
        # Bound full polylines without dropping vertices; stable OSM endpoint IDs.
        cuts.update(range(0, len(ids), 499))
        last = 0
        for end in sorted(cuts)[1:]:
            part = ids[last : end + 1]
            last = end
            if part[0] == part[-1]:
                note("way", i, "closed_loop_segment_requires_review")
                continue
            blockers = [
                n
                for n in part
                if access_reason(tags(elements["node"][n]))
                or vertical_reason(tags(elements["node"][n]))
            ]
            if blockers:
                note("way", i, "blocked_or_level_node_segment")
                continue
            points = [nodes[n] for n in part]
            if any(a == b for a, b in zip(points, points[1:], strict=False)):
                note("way", i, "repeated_position_segment")
                continue
            needed.update((part[0], part[-1]))
            segments.append((i, part, t))
    for n in sorted(needed):
        t = tags(elements["node"][n])
        ext = f"osm-node-{n}"
        add(
            "nodes",
            ext,
            {
                "frame_id": "osm-outdoor-wgs84",
                "label": (t.get("name") or t.get("ref") or f"OSM junction {n}")[:160],
                "point": {"type": "Point", "coordinates": nodes[n]},
                "evidence": evidence("node", n, t),
            },
            f"node/{n}",
            t,
        )
    for i, ids, t in segments:
        direction = t.get("oneway:foot", "no")
        for reverse in (
            [True]
            if direction == "-1"
            else [False]
            if direction in {"yes", "1", "true"}
            else [False, True]
        ):
            path = list(reversed(ids)) if reverse else ids
            ext = f"osm-way-{i}-{ids[0]}-{ids[-1]}"
            points = [nodes[n] for n in path]
            add(
                "edges",
                ext + ("-reverse" if reverse else "-forward"),
                {
                    "frame_id": "osm-outdoor-wgs84",
                    "from_node_id": f"osm-node-{path[0]}",
                    "to_node_id": f"osm-node-{path[-1]}",
                    "physical_path_id": ext,
                    "kind": "stairs" if t["highway"] == "steps" else "walkway",
                    "geometry": {"type": "LineString", "coordinates": points},
                    "distance_status": "estimated",
                    "accessibility_status": "not_step_free"
                    if t["highway"] == "steps"
                    else "unknown",
                    "evidence": evidence("way", i, t),
                    "surface": t.get("surface"),
                },
                f"way/{i}",
                t,
            )
            graph[path[0]].add(path[-1])
            graph[path[-1]].add(path[0])
    for n, e in sorted(elements["node"].items()):
        t = tags(e)
        point = Point(nodes[n])
        ext = f"osm-node-{n}"
        if not t or not coverage.covers(point) or access_reason(t) or vertical_reason(t):
            continue
        if "entrance" in t and t["entrance"] not in {"no", "emergency", "exit"}:
            # Anonymous doors are catalogued honestly, no names inferred from neighbours.
            t = {**t, "name": t.get("name") or t.get("ref") or f"Mapped entrance {n}"}
            destination(ext, t, point, kind="entrance")
            if n in needed:
                add(
                    "anchors",
                    ext,
                    {
                        "place_id": ext,
                        "node_id": ext,
                        "accessibility_status": "unknown",
                        "accessibility_evidence": evidence("node", n, t),
                    },
                    f"node/{n}",
                    t,
                )
                catalog[ext]["anchored"] = True
        elif t.get("name") and t.get("amenity") in {
            "library",
            "cafe",
            "restaurant",
            "food_court",
            "drinking_water",
            "toilets",
        }:
            destination(ext, t, point)
    components = []
    pending = set(needed)
    while pending:
        todo = [min(pending)]
        visited = set()
        while todo:
            n = todo.pop()
            if n in visited:
                continue
            visited.add(n)
            todo.extend(graph[n] - visited)
        pending -= visited
        components.append(
            {
                "nodes": len(visited),
                "example_source_node": min(visited),
                "entrances": [
                    f"osm-node-{n}"
                    for n in sorted(visited)
                    if catalog.get(f"osm-node-{n}", {}).get("anchored")
                ],
            }
        )
    report["components"] = sorted(components, key=lambda c: (-c["nodes"], c["example_source_node"]))
    report["destinations"] = catalog
    report["raw_tag_counts"] = {
        key: sum(key in tags(e) for e in elements["way"].values())
        for key in ("building", "highway", "indoor")
    }
    report["included_highway_ways"] = len({i for i, _, _ in segments})
    report["quarantined_indoor_features"] = [
        {
            "source": f"osm-{kind}-{i}",
            "tags": tags(e),
            "node_refs": [int(n.attrib["ref"]) for n in e.findall("nd")],
        }
        for kind in ("node", "way")
        for i, e in sorted(elements[kind].items())
        if tags(e).get("indoor") not in {None, "no"}
        or "room" in tags(e)
        or tags(e).get("level", "0") not in {"0", "0.0"}
    ]
    report["surrounding_feature_decisions"] = [d for d in decisions if "outside" in d["reason"]]
    report["included_counts"] = dict(sorted(Counter(r["entity"] for r in records).items()))
    report["exclusion_reason_counts"] = dict(
        sorted(Counter(d["reason"] for d in decisions).items())
    )
    report["routable_entrance_count"] = sum(p["anchored"] for p in catalog.values())
    report["unanchored_destination_count"] = sum(not p["anchored"] for p in catalog.values())
    overlay = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": mapping(p),
                "properties": {"public": True, "label": label},
            }
            for p, label in zip(
                campus_parts,
                ["OSM academic campus coverage", "OSM hostel campus coverage"],
                strict=True,
            )
        ],
    }
    bundles = [
        {
            "schema_version": "import-v1",
            "units": "WGS84_degrees_and_metres",
            "campus_code": CODE,
            "timezone": TIMEZONE,
            "records": records[i : i + batch_size],
        }
        for i in range(0, len(records), batch_size)
    ]
    return {"campus": campus, "report": report, "overlay": overlay, "bundles": bundles}


def write_conversion(result, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    files = {
        "campus.json": result["campus"],
        "report.json": result["report"],
        "coverage.geojson": result["overlay"],
        "options.json": {
            "format": "json",
            "campus_code": CODE,
            "timezone": TIMEZONE,
            "source_rights": RIGHTS,
            "provenance": f"Owner supplied OSM export SHA256 {result['report']['source_sha256']}; {VERSION}; no field survey",
            "policy": "create_only",
        },
    }
    files.update({f"batch-{i:03}.json": b for i, b in enumerate(result["bundles"], 1)})
    manifest = {
        "converter": VERSION,
        "source_sha256": result["report"]["source_sha256"],
        "files": {name: hashlib.sha256(encode(value)).hexdigest() for name, value in files.items()},
    }
    for name, value in {**files, "manifest.json": manifest}.items():
        (directory / name).write_bytes(encode(value))
