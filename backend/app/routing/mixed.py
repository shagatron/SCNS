"""Pure Dijkstra over a permitted immutable projection, with explicit cost units."""

from app.core.errors import DomainError
from app.routing.dijkstra import Arc, shortest_path


def compute(data, source, target, profile="shortest", mode="metric", speed=1.3):
    places = data["places"]
    if source not in places or target not in places:
        raise DomainError("location_not_found", "This public location could not be found.", 404)
    if profile not in {"shortest", "step_free", "fastest"} or mode not in {
        "metric",
        "directions_only",
    }:
        raise ValueError("Unsupported routing cost/profile")
    if profile == "fastest" and mode == "directions_only":
        raise DomainError(
            "invalid_input",
            "Fastest routing requires supported traversal times; choose shortest or step-free for directions-only.",
        )
    floors = data.get("floors", {})
    enabled = {
        i for i, f in floors.items() if f.get("navigation_mode") in {"metric", "directions_only"}
    }
    indoor = {i: n for i, n in data.get("indoor_nodes", {}).items() if n["floor_id"] in enabled}
    outdoor = data.get("nodes", {})

    def access(a):
        return a["is_open"] and (
            profile != "step_free" or a["accessibility_status"] == "verified_step_free"
        )

    def candidates(identity):
        if identity in data.get("indoor_rooms", {}):
            return sorted(
                [
                    (a.get("priority", 0), a["id"], "i:" + a["node_id"])
                    for a in data.get("indoor_access", {}).values()
                    if a["room_id"] == identity and a["node_id"] in indoor and access(a)
                ]
            )
        return sorted(
            [
                (0, a["id"], "o:" + a["node_id"])
                for a in data.get("anchors", {}).values()
                if a["place_id"] == identity and a["node_id"] in outdoor and access(a)
            ]
        )

    starts, ends = candidates(source), candidates(target)
    if not starts or not ends:
        code = "no_verified_step_free_route" if profile == "step_free" else "location_not_routable"
        raise DomainError(
            code,
            "No eligible mapped door/entrance is available for this profile. Choose another mapped location or request surveyed access information.",
        )
    segments = {}
    seconds_by_edge = {}
    arcs = []

    def add(
        key,
        a,
        b,
        row,
        kind,
        geometry=None,
        polyline=None,
        floor_id=None,
        to_floor_id=None,
        seconds=None,
        label=None,
    ):
        if not row["is_open"] or (
            profile == "step_free"
            and (kind == "stairs" or row["accessibility_status"] != "verified_step_free")
        ):
            return
        distance = row.get("distance_m")
        status = row.get("distance_status", "unknown")
        if mode == "directions_only":
            cost = 1.0
        elif profile == "fastest":
            if seconds is None:
                return
            cost = seconds
        else:
            if distance is None or (
                status not in {"measured", "calibrated"}
                and not (kind == "outdoor" and status == "estimated")
            ):
                return
            cost = distance
        if floor_id and mode == "metric" and floors[floor_id]["navigation_mode"] != "metric":
            return
        if to_floor_id and mode == "metric" and floors[to_floor_id]["navigation_mode"] != "metric":
            return
        arcs.append(
            Arc(key, a, b, cost, kind, row["accessibility_status"], priority=row.get("priority", 0))
        )
        seconds_by_edge[key] = seconds
        f = floors.get(floor_id, {})
        t = floors.get(to_floor_id, {})
        building = data.get("buildings", {}).get(f.get("building_id") or t.get("building_id"), {})
        if kind == "outdoor":
            verb = (
                "Take the stairs"
                if row["kind"] == "stairs"
                else "Follow the ramp"
                if row["kind"] == "ramp"
                else "Follow the path"
            )
            instruction = f"{verb} to {outdoor[b[2:]]['label']}."
        elif kind == "indoor":
            instruction = f"{'Pass through the door' if row['kind'] == 'door' else 'Follow the corridor'} to {indoor[b[2:]]['label']} on {f['label']} in {building['name']}."
        elif kind == "entrance_transition":
            instruction = (
                f"Enter {building['name']} through {label} onto {t['label']}."
                if row["direction"] == "in"
                else f"Exit {building['name']} through {label} to the campus map."
            )
        else:
            instruction = (
                f"Take {label} ({kind}) from {f['label']} to {t['label']} in {building['name']}."
            )
        segments[key] = {
            "edge_id": row["id"],
            "from_node_id": a[2:],
            "to_node_id": b[2:],
            "kind": kind,
            "geometry": geometry,
            "polyline": polyline,
            "distance_m": round(distance, 2) if distance is not None else None,
            "distance_status": status,
            "estimated_duration_s": round(seconds, 1) if seconds is not None else None,
            "floor_id": floor_id,
            "to_floor_id": to_floor_id,
            "building_id": f.get("building_id") or t.get("building_id"),
            "frame_id": f.get("frame_id"),
            "connector_id": row.get("connector_id"),
            "from_local_point": {k: indoor[a[2:]][k] for k in ("x_px", "y_px")}
            if a.startswith("i:")
            else None,
            "to_local_point": {k: indoor[b[2:]][k] for k in ("x_px", "y_px")}
            if b.startswith("i:")
            else None,
            "instruction": instruction,
        }

    for identity, e in sorted(data.get("edges", {}).items()):
        if e["from_node_id"] not in outdoor or e["to_node_id"] not in outdoor:
            continue
        # Existing outdoor graph uses its documented calibrated walking-speed policy.
        if profile == "step_free" and e["kind"] == "stairs":
            continue
        add(
            "o:" + identity,
            "o:" + e["from_node_id"],
            "o:" + e["to_node_id"],
            e,
            "outdoor",
            geometry=e["geometry"],
            seconds=e["distance_m"] / speed if e["kind"] != "stairs" else None,
        )
    for identity, e in sorted(data.get("indoor_edges", {}).items()):
        if e["from_node_id"] not in indoor or e["to_node_id"] not in indoor:
            continue
        add(
            "i:" + identity,
            "i:" + e["from_node_id"],
            "i:" + e["to_node_id"],
            e,
            "indoor",
            polyline=e["polyline"],
            floor_id=e["floor_id"],
            to_floor_id=e["floor_id"],
            seconds=e["distance_m"] / speed if e["distance_m"] is not None else None,
        )
    stops = data.get("connector_stops", {})

    def usable(row):
        c = data.get("connectors", {}).get(row["connector_id"])
        return (
            c
            if c and c["operational_status"] == "available" and c["verified"] and row["verified"]
            else None
        )

    def time(row, kind):
        movement = row["baseline_traversal_s"]
        wait = row["wait_estimate_s"]
        if movement is None or (kind == "lift" and wait is None):
            return None
        return movement + (wait or 0)

    for identity, e in sorted(data.get("connector_paths", {}).items()):
        c = usable(e)
        a, b = stops.get(e["from_stop_id"]), stops.get(e["to_stop_id"])
        if (
            not c
            or not a
            or not b
            or not a.get("verified")
            or not b.get("verified")
            or a["node_id"] not in indoor
            or b["node_id"] not in indoor
        ):
            continue
        add(
            "c:" + identity,
            "i:" + a["node_id"],
            "i:" + b["node_id"],
            e,
            c["kind"],
            floor_id=a["floor_id"],
            to_floor_id=b["floor_id"],
            seconds=time(e, c["kind"]),
            label=c["label"],
        )
    for identity, e in sorted(
        data.get("entrance_transitions", {}).items(),
        key=lambda pair: (pair[1]["priority"], pair[0]),
    ):
        c = usable(e)
        stop = stops.get(e["stop_id"])
        anchor = data.get("anchors", {}).get(e["anchor_id"])
        if (
            not c
            or not stop
            or not stop.get("verified")
            or stop["node_id"] not in indoor
            or not anchor
            or anchor["node_id"] not in outdoor
            or not access(anchor)
        ):
            continue
        a, b = "o:" + anchor["node_id"], "i:" + stop["node_id"]
        floor_id, to_floor_id = None, stop["floor_id"]
        if e["direction"] == "out":
            a, b = b, a
            floor_id, to_floor_id = to_floor_id, floor_id
        add(
            "t:" + identity,
            a,
            b,
            e,
            "entrance_transition",
            floor_id=floor_id,
            to_floor_id=to_floor_id,
            seconds=time(e, "entrance"),
            label=c["label"],
        )
    # Deterministic node/edge ordering; priorities select duplicate anchors only after cost.
    path = shortest_path(
        arcs,
        {c[2] for c in starts},
        {c[2] for c in ends},
        source_priorities={n: min(p for p, _, node in starts if node == n) for _, _, n in starts},
        target_priorities={n: min(p for p, _, node in ends if node == n) for _, _, n in ends},
    )
    if path is None:
        code = "no_verified_step_free_route" if profile == "step_free" else "no_route"
        raise DomainError(
            code,
            "No eligible route has the required costs and available connections. Unknown accessibility and stairs are excluded for step-free; unknown distance/time is never guessed. Try another mapped entrance or explicit directions-only mode.",
        )
    selected = [segments[e] for e in path.edges]
    distance_known = all(s["distance_m"] is not None for s in selected)
    time_known = all(s["estimated_duration_s"] is not None for s in selected)
    known_distance = round(sum(s["distance_m"] or 0 for s in selected), 2)
    # Aggregate unrounded physical values from stored rows, not displayed rounded segments.
    physical = {"o:" + i: e.get("distance_m") for i, e in data.get("edges", {}).items()}
    for prefix, layer in (
        ("i:", "indoor_edges"),
        ("c:", "connector_paths"),
        ("t:", "entrance_transitions"),
    ):
        physical.update({prefix + i: e.get("distance_m") for i, e in data.get(layer, {}).items()})
    known_distance = round(sum(physical[e] or 0 for e in path.edges), 2)
    return dict(
        segments=selected,
        distance_m=known_distance if distance_known else None,
        known_distance_m=known_distance,
        distance_status="complete"
        if distance_known
        else "partial"
        if known_distance
        else "unknown",
        estimated_duration_s=round(sum(seconds_by_edge[e] for e in path.edges), 1)
        if time_known
        else None,
        optimization_cost=round(path.distance_m, 4),
        cost_units="traversals"
        if mode == "directions_only"
        else "seconds"
        if profile == "fastest"
        else "metres",
        source_anchor_id=next(c[1] for c in starts if c[2] == path.nodes[0]),
        destination_anchor_id=next(c[1] for c in ends if c[2] == path.nodes[-1]),
        arrival_instruction=f"Arrive at {places[target]['name']}.",
    )
