"""Deterministic synthetic outdoor fixture. All shapes and coordinates are invented."""
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]


def uid(key):
    return str(uuid5(NAMESPACE_URL, f"https://scns.invalid/demo/{key}"))


def point(x, y):
    # An imaginary patch around (0, 0), deliberately unrelated to any real campus.
    return [round(x / 100000, 7), round(y / 100000, 7)]


def polygon(x1, y1, x2, y2):
    return {"type": "Polygon", "coordinates": [[point(x1, y1), point(x2, y1), point(x2, y2), point(x1, y2), point(x1, y1)]]}


def build():
    frame = uid("frame/outdoor")
    bundle = {
        "schema_version": "1.0", "units": "WGS84_degrees_and_metres",
        "source_rights": "Original synthetic fixture for this project; contains no institutional drawings or personal data.",
        "provenance": "Invented coordinates near (0,0). Distances measured computationally along synthetic WGS84 polylines; not surveyed real paths.",
        "campus": {"id": uid("campus"), "code": "DEMO", "name": "Demo Campus", "timezone": "Asia/Kolkata", "is_demo": True,
                   "center": {"type": "Point", "coordinates": point(170, 150)}, "boundary": polygon(-35, -30, 385, 310)},
        "frames": [{"id": frame, "code": "outdoor-wgs84", "kind": "outdoor"}],
        "buildings": [], "places": [], "nodes": [], "edges": [], "anchors": [],
    }
    for code, name, rect in [("LIB", "Library", (50, 185, 120, 240)),
                             ("ACA", "Academic House", (225, 185, 310, 245)),
                             ("HUB", "Student Hub", (245, 45, 320, 110))]:
        bundle["buildings"].append({"id": uid("building/"+code), "code": code, "name": name, "footprint": polygon(*rect), "visibility": "public"})
    nodes = {"gate": (15, 20), "courtyard": (100, 80), "west": (60, 145), "library": (70, 185),
             "library-east": (120, 205), "central": (170, 145), "academic": (250, 185),
             "hub": (245, 80), "water": (180, 80), "washroom": (275, 45),
             "garden": (350, 275), "restricted": (125, 100), "east-exit": (350, 80)}
    for key, xy in nodes.items():
        bundle["nodes"].append({"id": uid("node/"+key), "frame_id": frame, "label": key.replace("-", " ").title(),
            "visibility": "restricted" if key == "restricted" else "public", "point": {"type": "Point", "coordinates": point(*xy)}})

    def edge(a, b, *, via=(), kind="walkway", access="verified_step_free", visibility="public", opened=True, paired=True):
        shape = [point(*nodes[a]), *[point(*p) for p in via], point(*nodes[b])]
        for source, target, coords in [(a, b, shape)] + ([(b, a, shape[::-1])] if paired else []):
            bundle["edges"].append({"id": uid(f"edge/{source}/{target}"), "physical_path_id": uid(f"path/{a}/{b}"),
                "from_node_id": uid("node/"+source), "to_node_id": uid("node/"+target), "frame_id": frame,
                "kind": kind, "geometry": {"type": "LineString", "coordinates": coords},
                "accessibility_status": access, "visibility": visibility, "is_open": opened,
                "evidence": "Synthetic exercise only; no physical accessibility survey."})
    edge("gate", "courtyard", via=[(35, 45), (70, 65)])
    edge("courtyard", "west", via=[(70, 95)])
    edge("west", "library")
    edge("courtyard", "central", kind="stairs", access="not_step_free")
    edge("courtyard", "water")
    edge("water", "central", via=[(205, 105), (200, 140)], kind="ramp")
    edge("central", "library-east", via=[(150, 170)])
    edge("central", "academic", via=[(215, 155)])
    edge("water", "hub")
    edge("hub", "washroom", via=[(235, 35)])
    edge("hub", "academic", opened=False)
    edge("hub", "east-exit", paired=False, access="unknown")
    edge("courtyard", "restricted", visibility="restricted")
    edge("restricted", "central", visibility="restricted")
    places = [
        ("GATE", "Main Gate", "entrance", "gate", None, ["entry", "start"]),
        ("LIB", "Library", "library", "library", "LIB", ["reading room", "books"]),
        ("ACA", "Academic House", "building", "academic", "ACA", ["academic block", "classrooms"]),
        ("HUB", "Student Hub", "building", "hub", "HUB", ["student centre"]),
        ("CAFE", "Courtyard Café", "cafe", "hub", "HUB", ["coffee", "food", "cafe"]),
        ("WATER", "Drinking Water", "water", "water", None, ["refill", "fountain"]),
        ("WC", "Garden Washrooms", "washroom", "washroom", "HUB", ["toilet", "restroom"]),
        ("GARDEN", "Quiet Garden", "garden", "garden", None, ["isolated destination"]),
        ("EAST", "East Exit", "entrance", "east-exit", None, ["one way exit"]),
        ("HELP", "Future Help Desk", "help", None, None, ["unmapped entrance"]),
        ("STAFF", "Restricted Store", "building", "restricted", None, []),
    ]
    for code, name, kind, anchor, building, aliases in places:
        bundle["places"].append({"id": uid("place/"+code), "code": code, "name": name, "kind": kind,
            "description": ("Synthetic isolated destination: no connected walking path." if code == "GARDEN" else
                            "Synthetic directory entry; entrance not mapped yet." if code == "HELP" else "Invented destination in Demo Campus. Not a real campus location."),
            "aliases": aliases, "building_id": uid("building/"+building) if building else None,
            "visibility": "restricted" if code == "STAFF" else "public",
            "point": {"type": "Point", "coordinates": point(*nodes[anchor]) if anchor else point(40, 260)}})
        for node in ([anchor] if anchor else []) + (["library-east"] if code == "LIB" else []):
            bundle["anchors"].append({"id": uid(f"anchor/{code}/{node}"), "place_id": uid("place/"+code),
                "node_id": uid("node/"+node), "accessibility_status": "verified_step_free" if code != "EAST" else "unknown", "is_open": True})
    return bundle


if __name__ == "__main__":
    (ROOT / "data/demo/campus.json").write_text(json.dumps(build(), indent=2) + "\n")
