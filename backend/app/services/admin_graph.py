"""Outdoor draft editor. Validate combined state before ordered transactional writes."""

import json
from collections import defaultdict
from uuid import UUID

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select, text

from app.cli.dataset import geometry
from app.core.errors import DomainError
from app.models import Anchor, Campus, Edge, Frame, Node, Place
from app.routing.dijkstra import Arc, shortest_path
from app.schemas.graph import GraphPatch
from app.services.admin_auth import audit
from app.services.admin_catalog import referenced
from app.services.imports import final_graph_guard, write_item

MODELS = {"nodes": Node, "edges": Edge, "anchors": Anchor}


def graph_rows(db, revision):
    result = {}
    for entity, model in {**MODELS, "frames": Frame, "places": Place}.items():
        field = (
            "point" if entity in {"nodes", "places"} else "geometry" if entity == "edges" else None
        )
        query = (
            select(model, func.ST_AsGeoJSON(getattr(model, field), 15)) if field else select(model)
        )
        rows = db.execute(
            query.where(model.dataset_revision_id == revision.id).order_by(model.id).limit(15001)
        ).all()
        if len(rows) > 15000:
            raise DomainError(
                "graph_limit",
                "Editor supports at most 15,000 records per layer; reduce this draft or edit a smaller campus.",
                422,
            )
        output = {}
        for row in rows:
            obj = row[0]
            data = {
                c.name: getattr(obj, c.name)
                for c in model.__table__.columns
                if c.name
                not in {
                    "id",
                    "campus_id",
                    "dataset_revision_id",
                    "point",
                    "geometry",
                    "x_px",
                    "y_px",
                }
            }
            if field:
                data[field] = json.loads(row[1]) if row[1] else None
            output[str(obj.id)] = json.loads(json.dumps(data, default=str))
        result[entity] = output
    return result


def graph_output(db, revision):
    campus = db.get(Campus, revision.campus_id)
    state = graph_rows(db, revision)
    return {
        "revision_version": revision.edit_version,
        "campus": {
            "name": campus.name,
            "is_demo": campus.is_demo,
            "boundary": json.loads(db.scalar(select(func.ST_AsGeoJSON(campus.boundary, 15)))),
        },
        **state,
    }


def issue(code, message, entity, ids, severity="error"):
    return dict(code=code, message=message, entity=entity, ids=ids, severity=severity)


def inspect_state(db, revision, state):
    findings = []
    nodes, edges, anchors = (state[e] for e in ("nodes", "edges", "anchors"))

    def report(code, message, entity, ids, severity="error"):
        findings.append(issue(code, message, entity, ids, severity))

    for identity, node in nodes.items():
        frame = state["frames"].get(node["frame_id"])
        if not frame:
            report("missing_frame", "Select an existing coordinate frame.", "nodes", [identity])
        elif frame["kind"] == "outdoor" and not node["point"]:
            report("invalid_coordinate", "Outdoor nodes need a WGS84 point.", "nodes", [identity])
    groups = defaultdict(list)
    for identity, edge in edges.items():
        source, target = nodes.get(edge["from_node_id"]), nodes.get(edge["to_node_id"])
        if not source or not target:
            report(
                "missing_node",
                "Restore the endpoint or explicitly remove its dependent paths before deleting a node.",
                "edges",
                [identity],
            )
            continue
        coords = edge["geometry"]["coordinates"]
        if (
            source["point"] is None
            or target["point"] is None
            or not (source["frame_id"] == target["frame_id"] == edge["frame_id"])
            or source is target
        ):
            report(
                "invalid_frame",
                "Use distinct endpoints in the same outdoor frame.",
                "edges",
                [identity],
            )
        elif (
            coords[0] != source["point"]["coordinates"]
            or coords[-1] != target["point"]["coordinates"]
        ):
            report(
                "endpoint_mismatch",
                "Snap the polyline start/end to its directed endpoint nodes.",
                "edges",
                [identity],
            )
        if edge["visibility"] == "public" and (
            source["visibility"] != "public" or target["visibility"] != "public"
        ):
            report(
                "visibility",
                "Restrict this path or use public endpoint nodes.",
                "edges",
                [identity],
            )
        if edge["accessibility_status"] == "verified_step_free" and (
            edge["kind"] == "stairs" or not edge["evidence"].strip()
        ):
            report(
                "accessibility",
                "Stairs cannot be step-free. Verification requires source/date evidence.",
                "edges",
                [identity],
            )
        shape = func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(edge["geometry"])), 4326)
        valid, simple, length, inside = db.execute(
            select(
                func.ST_IsValid(shape),
                func.ST_IsSimple(shape),
                func.ST_Length(cast(shape, Geography)),
                func.ST_Covers(Campus.boundary, shape),
            ).where(Campus.id == revision.campus_id)
        ).one()
        if (
            not valid
            or not simple
            or length <= 0
            or any(a == b for a, b in zip(coords, coords[1:], strict=False))
        ):
            report(
                "invalid_geometry",
                "Remove repeated vertices, loops or zero-length segments; draw a simple path.",
                "edges",
                [identity],
            )
        if not inside:
            report(
                "outside_boundary",
                "Move the entire path inside the campus boundary.",
                "edges",
                [identity],
            )
        if length > 500:
            report(
                "unusual_length",
                "Path exceeds 500m; review geometry and source evidence.",
                "edges",
                [identity],
                "warning",
            )
        groups[edge["physical_path_id"]].append((identity, edge))
    for pair in groups.values():
        if len(pair) > 2:
            report(
                "direction_pair",
                "A physical path supports one direction or two reversed directions. Split distinct paths into separate IDs.",
                "edges",
                [x[0] for x in pair],
            )
        elif len(pair) == 2:
            (_, a), (_, b) = pair
            fields = [
                "kind",
                "frame_id",
                "visibility",
                "is_open",
                "accessibility_status",
                "distance_status",
                "evidence",
            ]
            if (
                a["from_node_id"] != b["to_node_id"]
                or a["to_node_id"] != b["from_node_id"]
                or a["geometry"]["coordinates"] != b["geometry"]["coordinates"][::-1]
                or any(a[k] != b[k] for k in fields)
            ):
                report(
                    "direction_pair",
                    "Reconcile both directions: reverse endpoints/geometry and keep physical attributes consistent.",
                    "edges",
                    [x[0] for x in pair],
                )
    links = set()
    for identity, anchor in anchors.items():
        node, place = nodes.get(anchor["node_id"]), state["places"].get(anchor["place_id"])
        if not node or not place:
            report(
                "missing_anchor_reference",
                "Choose an existing draft place and node, or remove this anchor.",
                "anchors",
                [identity],
            )
        elif place["visibility"] == "public" and node["visibility"] != "public":
            report(
                "anchor_visibility",
                "A public place entrance must use a public node.",
                "anchors",
                [identity],
            )
        if (
            anchor["accessibility_status"] == "verified_step_free"
            and not anchor["accessibility_evidence"].strip()
        ):
            report(
                "anchor_evidence",
                "Record source and verification date before asserting step-free access.",
                "anchors",
                [identity],
            )
        key = anchor["place_id"], anchor["node_id"]
        if key in links:
            report(
                "duplicate_anchor",
                "Remove the duplicate place/node entrance link.",
                "anchors",
                [identity],
            )
        links.add(key)
    return findings


def apply_patch(db, revision, patch: GraphPatch, actor_id, request_id):
    state = graph_rows(db, revision)
    original = json.loads(json.dumps(state))
    explicit_edges = {str(c.id) for c in patch.changes if c.entity == "edges"}
    for change in patch.changes:
        identity = str(change.id)
        old = state[change.entity].get(identity)
        if change.data is None:
            if old is None:
                raise DomainError(
                    "location_not_found", "Deleted graph item is not in this draft.", 404
                )
            del state[change.entity][identity]
        else:
            if change.entity == "nodes" and old and old["point"] is None:
                raise DomainError(
                    "invalid_input", "Indoor nodes cannot be edited by the outdoor editor."
                )
            state[change.entity][identity] = change.data.model_dump(mode="json")
    # Moving a node adjusts every incident endpoint atomically, retaining interior vertices.
    for identity, node in state["nodes"].items():
        old = original["nodes"].get(identity)
        if not old or old["point"] == node["point"]:
            continue
        for edge_id, edge in state["edges"].items():
            if (
                identity not in {edge["from_node_id"], edge["to_node_id"]}
                or edge_id in explicit_edges
            ):
                continue
            if edge["from_node_id"] == identity:
                edge["geometry"]["coordinates"][0] = node["point"]["coordinates"]
            if edge["to_node_id"] == identity:
                edge["geometry"]["coordinates"][-1] = node["point"]["coordinates"]
            edge["accessibility_status"] = "unknown"
            edge["distance_status"] = "estimated"
    errors = [x for x in inspect_state(db, revision, state) if x["severity"] == "error"]
    if errors:
        error = errors[0]
        raise DomainError(
            "graph_validation_failed",
            f"{error['code']}: {error['message']} Item: {error['ids'][0]}",
        )
    changes = []
    for entity in MODELS:
        for identity in sorted(set(original[entity]) | set(state[entity])):
            before, after = original[entity].get(identity), state[entity].get(identity)
            # distance is always recomputed, never accepted from the client.
            if before and after and entity == "edges":
                before = {k: v for k, v in before.items() if k != "distance_m"}
                after = {k: v for k, v in after.items() if k != "distance_m"}
            if before != after:
                changes.append((entity, UUID(identity), before, after))
    for entity in ("anchors", "edges", "nodes"):
        for kind, identity, _, after in changes:
            if kind == entity and after is None:
                db.delete(referenced(db, MODELS[entity], revision.id, identity))
        db.flush()
    for entity in ("nodes", "edges", "anchors"):
        for kind, identity, _, after in changes:
            if kind != entity or after is None:
                continue
            if entity == "nodes":
                row = db.get(Node, (revision.id, identity)) or Node(
                    id=identity, campus_id=revision.campus_id, dataset_revision_id=revision.id
                )
                frame = referenced(db, Frame, revision.id, UUID(after["frame_id"]))
                if frame.kind != "outdoor":
                    raise DomainError(
                        "invalid_input", "Outdoor editor requires an outdoor WGS84 frame."
                    )
                shape = func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(after["point"])), 4326)
                if not db.scalar(
                    select(func.ST_Covers(Campus.boundary, shape)).where(
                        Campus.id == revision.campus_id
                    )
                ):
                    raise DomainError("invalid_input", "Node falls outside the campus boundary.")
                for key, value in after.items():
                    setattr(
                        row,
                        key,
                        geometry(change_point(after))
                        if key == "point"
                        else UUID(value)
                        if key == "frame_id"
                        else value,
                    )
                db.add(row)
                db.flush()
            else:
                write_item(db, revision, {"entity": entity, "id": str(identity), "data": after})
    try:
        final_graph_guard(db, revision)
    except ValueError as error:
        raise DomainError("graph_validation_failed", str(error)) from None
    for entity, identity, before, after in changes:
        audit(
            db,
            f"graph.{entity}.{'delete' if after is None else 'create' if before is None else 'update'}",
            request_id,
            actor_id=actor_id,
            campus_id=revision.campus_id,
            revision_id=revision.id,
            resource_id=identity,
            before=before,
            after=after,
        )
    return graph_output(db, revision)


def change_point(data):
    from app.schemas.api import Point

    return Point.model_validate(data["point"])


def reachable(adjacency, starts):
    found, queue = set(starts), list(starts)
    while queue:
        node = queue.pop()
        for target in adjacency[node]:
            if target not in found:
                found.add(target)
                queue.append(target)
    return found


def validate_graph(db, revision):
    state = graph_rows(db, revision)
    findings = inspect_state(db, revision, state)
    for profile in ("shortest", "step_free"):
        adjacency, reverse = defaultdict(set), defaultdict(set)
        for e in state["edges"].values():
            if (
                e["visibility"] != "public"
                or not e["is_open"]
                or (
                    profile == "step_free"
                    and (e["kind"] == "stairs" or e["accessibility_status"] != "verified_step_free")
                )
            ):
                continue
            adjacency[e["from_node_id"]].add(e["to_node_id"])
            reverse[e["to_node_id"]].add(e["from_node_id"])
        entrances = defaultdict(set)
        for a in state["anchors"].values():
            if (
                a["is_open"]
                and a["node_id"] in state["nodes"]
                and state["nodes"][a["node_id"]]["visibility"] == "public"
                and (profile == "shortest" or a["accessibility_status"] == "verified_step_free")
            ):
                entrances[a["place_id"]].add(a["node_id"])
        starts = next(iter(entrances.values()), set())
        forward, backward = reachable(adjacency, starts), reachable(reverse, starts)
        for identity, place in state["places"].items():
            if place["visibility"] != "public":
                continue
            candidates = entrances[identity]
            if not candidates or not (candidates & forward and candidates & backward):
                findings.append(
                    issue(
                        "connectivity_" + profile,
                        f"{place['name']}: add an eligible entrance/path or document legitimate isolation ({profile}).",
                        "places",
                        [identity],
                        "warning",
                    )
                )
    for identity, node in state["nodes"].items():
        if node["point"] and not node.get("evidence", "").strip():
            findings.append(
                issue(
                    "unverified_source",
                    "Record source and last verification notes; geometry is unverified.",
                    "nodes",
                    [identity],
                    "warning",
                )
            )
    for a, b in db.execute(
        text(
            """SELECT a.id,b.id FROM navigation_nodes a JOIN navigation_nodes b ON a.dataset_revision_id=b.dataset_revision_id AND a.id<b.id AND a.frame_id=b.frame_id AND a.point && ST_Expand(b.point,0.00001) WHERE a.dataset_revision_id=:revision AND ST_DWithin(a.point::geography,b.point::geography,1) LIMIT 100"""
        ),
        {"revision": revision.id},
    ):
        findings.append(
            issue(
                "near_duplicate",
                "Nodes are within 1m. Review and deliberately reconnect paths/anchors if appropriate.",
                "nodes",
                [str(a), str(b)],
                "warning",
            )
        )
    for a, b in db.execute(
        text(
            """SELECT a.id,b.id FROM navigation_edges a JOIN navigation_edges b ON a.dataset_revision_id=b.dataset_revision_id AND a.id<b.id AND a.physical_path_id<>b.physical_path_id AND a.frame_id=b.frame_id AND a.geometry && b.geometry WHERE a.dataset_revision_id=:revision AND ST_Crosses(a.geometry,b.geometry) LIMIT 100"""
        ),
        {"revision": revision.id},
    ):
        findings.append(
            issue(
                "unmapped_intersection",
                "Crossing is not connected. Review bridge/overlap evidence; split both paths at the same node only when physically connected.",
                "edges",
                [str(a), str(b)],
                "warning",
            )
        )
    return {
        "revision_version": revision.edit_version,
        "errors": sum(x["severity"] == "error" for x in findings),
        "warnings": sum(x["severity"] == "warning" for x in findings),
        "diagnostics": findings[:500],
        "truncated": len(findings) > 500,
        "spatial_warning_limit": 100,
    }


def route_test(db, revision, source, target, profile):
    state = graph_rows(db, revision)
    for identity in (source, target):
        if str(identity) not in state["places"]:
            raise DomainError("location_not_found", "Place is not in this draft.", 404)

    def candidates(place):
        return {
            a["node_id"]
            for a in state["anchors"].values()
            if a["place_id"] == str(place)
            and a["is_open"]
            and state["nodes"].get(a["node_id"], {}).get("visibility") == "public"
            and (profile == "shortest" or a["accessibility_status"] == "verified_step_free")
        }

    arcs = [
        Arc(
            i,
            e["from_node_id"],
            e["to_node_id"],
            e["distance_m"],
            e["kind"],
            e["accessibility_status"],
            e["is_open"],
            e["visibility"],
        )
        for i, e in state["edges"].items()
    ]
    path = shortest_path(arcs, candidates(source), candidates(target), profile)
    return {
        "revision_version": revision.edit_version,
        "profile": profile,
        "found": path is not None,
        "distance_m": path.distance_m if path else None,
        "edge_ids": path.edges if path else [],
        "node_ids": path.nodes if path else [],
        "notice": "Draft-only computed Dijkstra preview; unverified synthetic data, never published.",
    }
