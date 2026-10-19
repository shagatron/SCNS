"""Generate explicitly invented 3C tracing/connection templates; never touches a DB."""

import json
from copy import deepcopy
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/demo/indoor-routing"
BASE = json.loads((ROOT / "data/demo/indoor/synthetic-ground.json").read_text())
DATE = "2026-10-01"
NOTE = "Invented synthetic 3C topology/accessibility test evidence; no real campus survey. PRIVATE-CONNECTION-NOTE"


def uid(name):
    return str(uuid5(NAMESPACE_URL, "https://scns.invalid/demo/3c/" + name))


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + "\n")


def main():
    ground = deepcopy(BASE)
    for values in ground["records"].values():
        for row in values.values():
            row.update(evidence=NOTE, verified_on=DATE)
            if "accessibility_status" in row:
                row["accessibility_status"] = "verified_step_free"
    nodes = ground["records"]["nodes"]
    west = next(k for k, n in nodes.items() if n["label"] == "Synthetic west")
    centre = next(k for k, n in nodes.items() if n["label"] == "Synthetic centre")
    east = next(k for k, n in nodes.items() if n["label"] == "Synthetic east")
    nodes[west]["kind"] = nodes[east]["kind"] = "entrance"
    upper = deepcopy(ground)
    identities = {k: uid("upper/" + k) for rows in upper["records"].values() for k in rows}
    for row in upper["records"]["edges"].values():
        identities.setdefault(row["physical_path_id"], uid("upper/" + row["physical_path_id"]))

    def remap(value):
        if isinstance(value, dict):
            return {identities.get(k, k): remap(v) for k, v in value.items()}
        if isinstance(value, list):
            return [remap(v) for v in value]
        return identities.get(value, value) if isinstance(value, str) else value

    upper = remap(upper)
    for room in upper["records"]["rooms"].values():
        room["code"] = (
            ("2" + room["code"][1:])
            if room["code"].startswith("1")
            else room["code"].replace("1", "2")
        )
        room["name"] = "Upper " + room["name"]
        room["aliases"] = []
    iso = uid("isolated-room")
    door = uid("isolated-door")
    ground["records"]["rooms"][iso] = {
        "code": "ISO",
        "name": "Synthetic disconnected room",
        "kind": "room",
        "description": "Deliberately isolated synthetic destination.",
        "aliases": [],
        "department_ids": [],
        "x_px": 530,
        "y_px": 280,
        "visibility": "public",
        "evidence": NOTE,
        "verified_on": DATE,
    }
    ground["records"]["nodes"][door] = {
        "kind": "door",
        "label": "Synthetic isolated door",
        "x_px": 530,
        "y_px": 260,
        "visibility": "public",
        "evidence": NOTE,
        "verified_on": DATE,
    }
    ground["records"]["access"][uid("isolated-access")] = {
        "room_id": iso,
        "node_id": door,
        "role": "door",
        "priority": 0,
        "accessibility_status": "verified_step_free",
        "is_open": True,
        "visibility": "public",
        "evidence": NOTE,
        "verified_on": DATE,
    }
    records = {k: {} for k in ("policies", "connectors", "stops", "paths", "transitions")}
    evidence = dict(evidence=NOTE, verified_on=DATE, visibility="public")
    for floor in ("GROUND", "UPPER"):
        records["policies"]["$" + floor] = {
            **evidence,
            "floor_id": "$" + floor,
            "layer_id": "$" + floor + "_LAYER",
            "enabled": True,
            "mode": "metric",
        }
    for kind, label in (
        ("stairs", "Synthetic stairs"),
        ("lift", "Synthetic lift"),
        ("entrance", "Synthetic west entrance"),
        ("entrance-east", "Synthetic east entrance"),
    ):
        cid = uid(kind)
        records["connectors"][cid] = {
            **evidence,
            "building_id": "$BUILDING",
            "code": kind.upper(),
            "label": label,
            "kind": "entrance" if kind.startswith("entrance") else kind,
            "operational_status": "available",
        }
        for floor in ("GROUND",) if kind.startswith("entrance") else ("GROUND", "UPPER"):
            node = (
                west
                if kind == "entrance"
                else east
                if kind in ("lift", "entrance-east")
                else centre
            )
            if floor == "UPPER":
                node = identities[node]
            records["stops"][uid(kind + "/" + floor)] = {
                **evidence,
                "connector_id": cid,
                "floor_id": "$" + floor,
                "layer_id": "$" + floor + "_LAYER",
                "node_id": node,
            }
        physical = uid(kind + "/physical")
        costs = {
            **evidence,
            "connector_id": cid,
            "physical_path_id": physical,
            "distance_m": 6
            if kind == "stairs"
            else 15
            if kind == "lift"
            else 2
            if kind == "entrance"
            else 12,
            "distance_status": "measured",
            "horizontal_distance_m": None,
            "vertical_rise_m": None,
            "baseline_traversal_s": 12 if kind == "stairs" else 8 if kind == "lift" else 3,
            "wait_estimate_s": 20 if kind == "lift" else None,
            "uncertainty_note": "Synthetic test estimates only; no measured real heights/waits.",
            "accessibility_status": "not_step_free" if kind == "stairs" else "verified_step_free",
            "width_m": None,
            "slope_percent": None,
            "step_count": None,
            "surface": None,
            "is_open": True,
        }
        if kind.startswith("entrance"):
            for direction in ("in", "out"):
                records["transitions"][uid(kind + "/" + direction)] = {
                    **costs,
                    "stop_id": uid(kind + "/GROUND"),
                    "anchor_id": "$ENTRANCE_A" if kind == "entrance" else "$ENTRANCE_B",
                    "direction": direction,
                    "priority": 0 if kind == "entrance" else 1,
                }
        else:
            for a, b in (("GROUND", "UPPER"), ("UPPER", "GROUND")):
                records["paths"][uid(kind + "/" + a + "/" + b)] = {
                    **costs,
                    "from_stop_id": uid(kind + "/" + a),
                    "to_stop_id": uid(kind + "/" + b),
                }
    dump("ground.json", ground)
    dump("upper.json", upper)
    dump(
        "connections.json", {"format": "scns-connections-v1", "synthetic": True, "records": records}
    )
    dump(
        "expected.json",
        {
            "synthetic": True,
            "ground_101": next(
                k for k, r in ground["records"]["rooms"].items() if r["code"] == "101"
            ),
            "ground_102": next(
                k for k, r in ground["records"]["rooms"].items() if r["code"] == "102"
            ),
            "upper_201": next(
                k for k, r in upper["records"]["rooms"].items() if r["code"] == "201"
            ),
            "upper_202": next(
                k for k, r in upper["records"]["rooms"].items() if r["code"] == "202"
            ),
            "isolated": iso,
            "stairs": uid("stairs"),
            "lift": uid("lift"),
            "same_floor_101_to_102_m": 18,
            "cross_floor_101_to_201_shortest_m": 36,
            "cross_floor_101_to_201_step_free_m": 57,
        },
    )


if __name__ == "__main__":
    main()
