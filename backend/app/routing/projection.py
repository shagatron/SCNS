"""Explicit allowlists for immutable public routing metadata; no private evidence."""

TRAVERSAL = (
    "id",
    "connector_id",
    "physical_path_id",
    "distance_m",
    "distance_status",
    "horizontal_distance_m",
    "vertical_rise_m",
    "baseline_traversal_s",
    "wait_estimate_s",
    "uncertainty_note",
    "accessibility_status",
    "width_m",
    "slope_percent",
    "step_count",
    "surface",
    "is_open",
)


def project_connections(result, full):
    fields = {
        "floor_routing": ("id", "floor_id", "frame_id", "enabled", "mode"),
        "connectors": ("id", "building_id", "code", "label", "kind", "operational_status"),
        "connector_stops": ("id", "connector_id", "floor_id", "frame_id", "node_id"),
        "connector_paths": (*TRAVERSAL, "from_stop_id", "to_stop_id"),
        "entrance_transitions": (*TRAVERSAL, "stop_id", "anchor_id", "direction", "priority"),
    }
    for entity, allowed in fields.items():
        result[entity] = {}
        for identity, row in full.get(entity, {}).items():
            if row["visibility"] != "public":
                continue
            if "floor_id" in row and row["floor_id"] not in result["floors"]:
                continue
            if entity == "connectors" and row["building_id"] not in result["buildings"]:
                continue
            if "connector_id" in row and row["connector_id"] not in result["connectors"]:
                continue
            if entity == "connector_stops" and row["node_id"] not in result["indoor_nodes"]:
                continue
            if entity == "connector_paths" and any(
                row[k] not in result["connector_stops"] for k in ("from_stop_id", "to_stop_id")
            ):
                continue
            if entity == "entrance_transitions" and (
                row["stop_id"] not in result["connector_stops"]
                or row["anchor_id"] not in result["anchors"]
            ):
                continue
            result[entity][identity] = {
                **{key: row[key] for key in allowed},
                "verified": bool(row.get("verified_on")),
            }
    for identity, floor in result["floors"].items():
        policy = result["floor_routing"].get(identity)
        ready = policy and policy["enabled"] and policy["verified"]
        floor["navigation_mode"] = policy["mode"] if ready else "display_only"
        floor["metric_navigation"] = bool(ready and policy["mode"] == "metric")
    for identity, room in result["indoor_rooms"].items():
        floor = result["floors"][room["floor_id"]]
        routable = floor["navigation_mode"] != "display_only" and any(
            a["room_id"] == identity and a["is_open"] for a in result["indoor_access"].values()
        )
        result["places"][identity].update(
            routable=routable,
            navigation_mode=floor["navigation_mode"] if routable else "indoor_catalog_only",
        )
