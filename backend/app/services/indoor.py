"""Atomic, floor-scoped tracing; local pixels never enter the outdoor route graph."""

import json
import math
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select

from app.core.errors import DomainError
from app.models import Building, Campus, Frame, Place
from app.models.admin import Department, DepartmentPlace, PlaceAlias, User
from app.models.floorplans import Floor, MapLayer
from app.models.indoor import IndoorAccess, IndoorEdge, IndoorNode, Room
from app.models.publication import SourceAsset
from app.schemas.indoor import IndoorAccessFields, IndoorEdgeFields, IndoorNodeFields, RoomFields
from app.services.admin_auth import audit, permissions
from app.services.catalog import normalize

MODELS = {"rooms": Room, "nodes": IndoorNode, "edges": IndoorEdge, "access": IndoorAccess}
FIELDS = {
    "rooms": RoomFields,
    "nodes": IndoorNodeFields,
    "edges": IndoorEdgeFields,
    "access": IndoorAccessFields,
}
LIMIT = 2000


def floor_row(db, revision, identity):
    floor = db.get(Floor, (revision.id, identity))
    if floor is None or floor.campus_id != revision.campus_id:
        raise DomainError("location_not_found", "Floor not found in this campus/revision.", 404)
    return floor


def prerequisite(db, revision, floor, mode=None):
    frame = db.get(Frame, (revision.id, floor.frame_id)) if floor.frame_id else None
    layer = db.get(MapLayer, (revision.id, floor.layer_id)) if floor.layer_id else None
    source = db.get(SourceAsset, (revision.id, layer.source_id)) if layer else None
    if (
        not frame
        or not layer
        or frame.kind != "indoor"
        or layer.floor_id != floor.id
        or layer.frame_id != frame.id
    ):
        raise DomainError(
            "indoor_prerequisite",
            "Apply an exact selected sanitized floorplan before tracing.",
            409,
        )
    reviewer = (
        db.get(User, source.approved_by, populate_existing=True)
        if source and source.approved_by
        else None
    )
    if (
        not reviewer
        or not reviewer.active
        or "source_approve" not in permissions(db, reviewer.id, revision.campus_id)
    ):
        raise DomainError(
            "indoor_prerequisite",
            "The selected sanitized derivative needs a live independent approval before tracing.",
            409,
        )
    calibration = frame.calibration
    if frame.metres_per_pixel is not None:
        reviewer = (
            db.get(User, UUID(calibration["reviewer"]), populate_existing=True)
            if calibration and calibration.get("reviewer")
            else None
        )
        if (
            not reviewer
            or not reviewer.active
            or "source_approve" not in permissions(db, reviewer.id, revision.campus_id)
            or calibration.get("layer_checksum") != layer.checksum
        ):
            raise DomainError(
                "indoor_prerequisite",
                "Independently approve current calibration evidence before metric tracing.",
                409,
            )
    elif mode == "metric":
        raise DomainError(
            "indoor_prerequisite",
            "Scale is unknown: calibrate/review first or explicitly choose directions-only tracing; pixels are not metres.",
            409,
        )
    return frame, layer


def record(db, revision, entity, item):
    data = {k: getattr(item, k) for k in FIELDS[entity].model_fields if hasattr(item, k)}
    if entity == "rooms":
        place = db.get(Place, (revision.id, item.id))
        data.update(
            name=place.name,
            kind=place.kind,
            description=place.description,
            aliases=place.aliases,
            department_ids=list(
                db.scalars(
                    select(DepartmentPlace.department_id).where(
                        DepartmentPlace.dataset_revision_id == revision.id,
                        DepartmentPlace.place_id == item.id,
                    )
                )
            ),
        )
    return json.loads(
        json.dumps(data, default=lambda x: x.isoformat() if isinstance(x, date) else str(x))
    )


def rows(db, revision, floor):
    result = {}
    for entity, model in MODELS.items():
        items = db.scalars(
            select(model)
            .where(model.dataset_revision_id == revision.id, model.floor_id == floor.id)
            .order_by(model.id)
            .limit(LIMIT + 1)
        ).all()
        if len(items) > LIMIT:
            raise DomainError(
                "indoor_limit",
                "Floor editor supports at most 2,000 records per layer; reduce this floor.",
                422,
            )
        result[entity] = {str(item.id): record(db, revision, entity, item) for item in items}
    return result


def output(db, revision, floor):
    frame = db.get(Frame, (revision.id, floor.frame_id)) if floor.frame_id else None
    campus = db.get(Campus, revision.campus_id)
    ready, error = True, None
    try:
        prerequisite(db, revision, floor)
    except DomainError as exc:
        ready, error = False, exc.message
    state = rows(db, revision, floor)
    metrics = {
        str(e.id): {"distance_m": e.distance_m, "distance_status": e.distance_status}
        for e in db.scalars(
            select(IndoorEdge).where(
                IndoorEdge.dataset_revision_id == revision.id, IndoorEdge.floor_id == floor.id
            )
        )
    }
    return {
        "revision_version": revision.edit_version,
        "status": revision.status,
        "campus": {"name": campus.name, "is_demo": campus.is_demo},
        "floor": {
            "id": str(floor.id),
            "label": floor.label,
            "building_id": str(floor.building_id),
            "frame_id": str(floor.frame_id) if frame else None,
            "width_px": frame.width_px if frame else None,
            "height_px": frame.height_px if frame else None,
            "metres_per_pixel": frame.metres_per_pixel if frame else None,
            "layer_id": str(floor.layer_id) if floor.layer_id else None,
        },
        "ready": ready,
        "prerequisite_error": error,
        "metrics": metrics,
        "departments": {
            str(d.id): d.name
            for d in db.scalars(
                select(Department).where(Department.dataset_revision_id == revision.id)
            )
        },
        **state,
    }


def shape(points):
    return func.ST_GeomFromText("LINESTRING(" + ",".join(f"{x} {y}" for x, y in points) + ")", 0)


def pixel_length(points):
    return sum(
        math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:], strict=False)
    )


def inspect(db, revision, floor, state, *, mode=None):
    findings = []

    def report(code, message, entity, ids, severity="error"):
        findings.append(dict(code=code, message=message, entity=entity, ids=ids, severity=severity))

    try:
        frame, _ = prerequisite(db, revision, floor, mode)
    except DomainError as exc:
        report("indoor_prerequisite", exc.message, "floors", [str(floor.id)])
        frame = db.get(Frame, (revision.id, floor.frame_id)) if floor.frame_id else None
    if not frame:
        return findings
    width, height = frame.width_px, frame.height_px
    today = (
        datetime.now(UTC).astimezone(ZoneInfo(db.get(Campus, revision.campus_id).timezone)).date()
    )
    codes = set()
    groups = defaultdict(list)
    for entity, records in state.items():
        if len(records) > LIMIT:
            report(
                "indoor_limit", "Reduce this layer below 2,000 records.", entity, list(records)[:1]
            )
        for identity, item in records.items():
            if item["visibility"] == "public" and (
                floor.visibility != "public"
                or db.get(Building, (revision.id, floor.building_id)).visibility != "public"
            ):
                report(
                    "indoor_visibility",
                    "Restrict indoor records before restricting their floor/building.",
                    entity,
                    [identity],
                )
            verified = date.fromisoformat(item["verified_on"]) if item.get("verified_on") else None
            if verified and (verified > today or len(item["evidence"].strip()) < 10):
                report(
                    "indoor_evidence",
                    "Verification needs a nonfuture campus date and substantive source notes.",
                    entity,
                    [identity],
                )
            elif not verified or verified < today - timedelta(days=365):
                report(
                    "indoor_unverified",
                    "Record/review current source and verification date; drawing alone is not a field survey.",
                    entity,
                    [identity],
                    "warning",
                )
            if item.get("accessibility_status") == "verified_step_free" and (
                not verified
                or len(item["evidence"].strip()) < 10
                or (item.get("step_count") or 0) > 0
            ):
                report(
                    "indoor_accessibility",
                    "Affirmative step-free access needs dated evidence and cannot contain positive steps.",
                    entity,
                    [identity],
                )
            if entity in {"rooms", "nodes"}:
                if not 0 <= item["x_px"] <= width or not 0 <= item["y_px"] <= height:
                    report(
                        "indoor_bounds",
                        "Move the label/node inside the selected reference image bounds.",
                        entity,
                        [identity],
                    )
            if entity == "rooms":
                if item["code"] in codes:
                    report(
                        "indoor_duplicate_code",
                        "Room codes are unique within building/floor, names may repeat.",
                        entity,
                        [identity],
                    )
                codes.add(item["code"])
                normalized = [normalize(a) for a in item["aliases"]]
                if any(not n for n in normalized) or len(set(normalized)) != len(normalized):
                    report(
                        "indoor_alias",
                        "Aliases need unique meaningful normalized values.",
                        entity,
                        [identity],
                    )
                departments = item["department_ids"]
                if len(set(departments)) != len(departments) or any(
                    not db.get(Department, (revision.id, UUID(d))) for d in departments
                ):
                    report(
                        "indoor_department",
                        "Select unique department links in this same campus/revision.",
                        entity,
                        [identity],
                    )
            if entity == "edges":
                source = state["nodes"].get(item["from_node_id"])
                target = state["nodes"].get(item["to_node_id"])
                points = item["polyline"]
                if not source or not target or source is target:
                    report(
                        "indoor_reference",
                        "Restore distinct same-floor endpoints or explicitly delete dependent paths.",
                        entity,
                        [identity],
                    )
                    continue
                if points[0] != [source["x_px"], source["y_px"]] or points[-1] != [
                    target["x_px"],
                    target["y_px"],
                ]:
                    report(
                        "indoor_endpoints",
                        "Snap polyline endpoints to their actual directed nodes; proximity never creates connectivity.",
                        entity,
                        [identity],
                    )
                if any(not 0 <= x <= width or not 0 <= y <= height for x, y in points):
                    report(
                        "indoor_bounds",
                        "All vertices must stay inside the selected reference frame.",
                        entity,
                        [identity],
                    )
                simple, valid = db.execute(
                    select(func.ST_IsSimple(shape(points)), func.ST_IsValid(shape(points)))
                ).one()
                if (
                    not simple
                    or not valid
                    or pixel_length(points) <= 0
                    or any(a == b for a, b in zip(points, points[1:], strict=False))
                ):
                    report(
                        "indoor_geometry",
                        "Remove loops/repeated vertices and zero-length path segments.",
                        entity,
                        [identity],
                    )
                if item["kind"] == "door" and "door" not in {source["kind"], target["kind"]}:
                    report(
                        "indoor_door",
                        "A door path must explicitly meet a door node.",
                        entity,
                        [identity],
                    )
                if item["visibility"] == "public" and any(
                    n["visibility"] != "public" for n in (source, target)
                ):
                    report(
                        "indoor_visibility",
                        "Public paths cannot expose restricted endpoints.",
                        entity,
                        [identity],
                    )
                groups[item["physical_path_id"]].append((identity, item))
                if frame.metres_per_pixel and pixel_length(points) * frame.metres_per_pixel > 500:
                    report(
                        "indoor_unusual_length",
                        "Path exceeds 500m; review reference vertices/scale.",
                        entity,
                        [identity],
                        "warning",
                    )
            if entity == "access":
                node, room = (
                    state["nodes"].get(item["node_id"]),
                    state["rooms"].get(item["room_id"]),
                )
                if not node or not room or node["kind"] != "door":
                    report(
                        "indoor_door_reference",
                        "Select an existing same-floor room and explicit door node, never its label centre.",
                        entity,
                        [identity],
                    )
                elif item["visibility"] == "public" and (
                    node["visibility"] != "public" or room["visibility"] != "public"
                ):
                    report(
                        "indoor_visibility",
                        "Public door access cannot expose restricted rooms/nodes.",
                        entity,
                        [identity],
                    )
    for pair in groups.values():
        if len(pair) > 2:
            report(
                "indoor_pair",
                "A physical path has one direction or two reversed consistent directions.",
                "edges",
                [p[0] for p in pair],
            )
        elif len(pair) == 2:
            (a_id, a), (b_id, b) = pair
            ignored = {"from_node_id", "to_node_id", "polyline"}
            if (
                a["from_node_id"] != b["to_node_id"]
                or a["to_node_id"] != b["from_node_id"]
                or a["polyline"] != b["polyline"][::-1]
                or any(a[k] != b[k] for k in a if k not in ignored)
            ):
                report(
                    "indoor_pair",
                    "Reverse paired endpoints/geometry and reconcile all shared physical/access attributes.",
                    "edges",
                    [a_id, b_id],
                )
    links = [(a["room_id"], a["node_id"]) for a in state["access"].values()]
    if len(set(links)) != len(links):
        report(
            "indoor_duplicate_access",
            "Use one explicit access link per room/door pair.",
            "access",
            [],
        )
    for identity in state["rooms"]:
        if not any(a["room_id"] == identity and a["is_open"] for a in state["access"].values()):
            report(
                "indoor_unlinked_room",
                "Search label has no open mapped door: indoor routing remains unavailable. Map an explicit access link or acknowledge this unfinished destination.",
                "rooms",
                [identity],
                "warning",
            )
    adjacency = defaultdict(set)
    for e in state["edges"].values():
        if e["is_open"]:
            adjacency[e["from_node_id"]].add(e["to_node_id"])
            adjacency[e["to_node_id"]].add(e["from_node_id"])
    remaining = set(state["nodes"])
    components = []
    while remaining:
        component, todo = set(), [min(remaining)]
        while todo:
            n = todo.pop()
            if n not in component:
                component.add(n)
                todo.extend(adjacency[n] - component)
        components.append(component)
        remaining -= component
    if len(components) > 1:
        report(
            "indoor_components",
            f"{len(components)} separate same-floor components. Add intentional paths; crossings/snap coordinates alone never connect.",
            "nodes",
            [min(c) for c in components[:100]],
            "warning",
        )
    # Bound quadratic geometry diagnostics; reaching the cap blocks whole-draft completeness.
    nodes = list(state["nodes"].items())
    pairs = 0
    for i, (a_id, a) in enumerate(nodes):
        for b_id, b in nodes[i + 1 :]:
            if math.hypot(a["x_px"] - b["x_px"], a["y_px"] - b["y_px"]) < 2:
                report(
                    "indoor_near_duplicate",
                    "Nodes within 2 reference pixels remain separate; merge/split deliberately after review.",
                    "nodes",
                    [a_id, b_id],
                    "warning",
                )
                pairs += 1
                if pairs >= 100:
                    break
        if pairs >= 100:
            break
    if state["rooms"] or state["nodes"]:
        report(
            "indoor_3c_unavailable",
            "Same-floor catalog/topology only: no cross-floor or indoor/outdoor route is available before 3C.",
            "floors",
            [str(floor.id)],
            "warning",
        )
        if frame.metres_per_pixel is None:
            report(
                "indoor_unknown_scale",
                "Explicit directions-only topology: metric length/ETA is unavailable; do not treat pixels as metres.",
                "floors",
                [str(floor.id)],
                "warning",
            )
    return findings


def validation(db, revision, floor):
    findings = inspect(db, revision, floor, rows(db, revision, floor))
    return {
        "revision_version": revision.edit_version,
        "errors": sum(f["severity"] == "error" for f in findings),
        "warnings": sum(f["severity"] == "warning" for f in findings),
        "diagnostics": findings[:500],
        "truncated": len(findings) > 500
        or sum(f["code"] == "indoor_near_duplicate" for f in findings) >= 100,
    }


def proposal(db, revision, floor, payload):
    if revision.status != "draft":
        raise DomainError(
            "conflict", "Return review/frozen content to draft before indoor edits.", 409
        )
    if payload.layer_id != floor.layer_id:
        raise DomainError(
            "conflict",
            "Selected plan changed. Explicitly retrace/reconcile against its new reference image; retained pixels cannot be silently rebound.",
            409,
        )
    frame, layer = prerequisite(db, revision, floor, payload.mode)
    before = rows(db, revision, floor)
    combined = json.loads(json.dumps(before))
    for change in payload.changes:
        existing = db.get(MODELS[change.entity], (revision.id, change.id))
        if change.entity == "rooms" and not existing and db.get(Place, (revision.id, change.id)):
            raise DomainError(
                "conflict",
                "Identity already belongs to the outdoor catalog; choose a new indoor place ID.",
                409,
            )
        if existing and existing.floor_id != floor.id:
            raise DomainError(
                "conflict", "Stable identity belongs to another floor; no implicit relocation.", 409
            )
        if change.data:
            combined[change.entity][str(change.id)] = change.data.model_dump(mode="json")
        else:
            combined[change.entity].pop(str(change.id), None)
    problems = [
        d
        for d in inspect(db, revision, floor, combined, mode=payload.mode)
        if d["severity"] == "error"
    ]
    if problems:
        raise DomainError("invalid_input", f"{problems[0]['code']}: {problems[0]['message']}", 422)
    return frame, layer, before, combined


def preview(db, revision, floor, payload):
    frame, _, _, combined = proposal(db, revision, floor, payload)
    result = output(db, revision, floor)
    result.update(combined)
    result["metrics"] = {
        identity: {
            "distance_m": pixel_length(e["polyline"]) * frame.metres_per_pixel
            if frame.metres_per_pixel
            else None,
            "distance_status": "calibrated" if frame.metres_per_pixel else "unknown",
        }
        for identity, e in combined["edges"].items()
    }
    return result


def apply_patch(db, revision, floor, payload, actor, request_id):
    frame, layer, before, _ = proposal(db, revision, floor, payload)
    # No silent cascades: final references must be valid before any ordered writes.
    # Reinsert changed links after their endpoints: rewiring and deletion can be
    # one atomic patch without intermediate FK failures or silent cascades.
    for change in payload.changes:
        if change.entity in {"edges", "access"}:
            old = db.get(MODELS[change.entity], (revision.id, change.id))
            if old:
                db.delete(old)
                db.flush()

    for entity in ("access", "edges", "nodes", "rooms"):
        for change in payload.changes:
            if change.entity == entity and not change.data:
                item = db.get(MODELS[entity], (revision.id, change.id))
                if item:
                    if entity == "rooms":
                        for model in (PlaceAlias, DepartmentPlace):
                            db.execute(
                                delete(model).where(
                                    model.dataset_revision_id == revision.id,
                                    model.place_id == change.id,
                                )
                            )
                    db.delete(item)
                    db.flush()
                    if entity == "rooms":
                        db.delete(db.get(Place, (revision.id, change.id)))
                        db.flush()
    for entity in ("rooms", "nodes", "edges", "access"):
        for change in payload.changes:
            if change.entity != entity or not change.data:
                continue
            values = change.data.model_dump()
            item = db.get(MODELS[entity], (revision.id, change.id)) or MODELS[entity](
                id=change.id,
                dataset_revision_id=revision.id,
                campus_id=revision.campus_id,
                floor_id=floor.id,
                frame_id=frame.id,
                source_id=layer.source_id,
            )
            if entity == "rooms":
                place = db.get(Place, (revision.id, change.id))
                if not place:
                    place = Place(
                        id=change.id,
                        dataset_revision_id=revision.id,
                        campus_id=revision.campus_id,
                        code="I-" + change.id.hex,
                        building_id=floor.building_id,
                        point=None,
                    )
                for k in ("name", "kind", "description", "aliases"):
                    setattr(place, k, values.pop(k))
                place.visibility = values["visibility"]
                place.search_text = normalize(
                    " ".join([values["code"], place.name, place.kind, *place.aliases])
                )
                db.add(place)
                db.flush()
                for model in (PlaceAlias, DepartmentPlace):
                    db.execute(
                        delete(model).where(
                            model.dataset_revision_id == revision.id, model.place_id == place.id
                        )
                    )
                for alias in place.aliases:
                    db.add(
                        PlaceAlias(
                            id=uuid4(),
                            dataset_revision_id=revision.id,
                            campus_id=revision.campus_id,
                            place_id=place.id,
                            value=alias,
                            normalized=normalize(alias),
                            language="en",
                        )
                    )
                for department_id in values.pop("department_ids"):
                    db.add(
                        DepartmentPlace(
                            id=uuid4(),
                            dataset_revision_id=revision.id,
                            campus_id=revision.campus_id,
                            place_id=place.id,
                            department_id=department_id,
                        )
                    )
            if entity == "edges":
                item.distance_m = (
                    pixel_length(values["polyline"]) * frame.metres_per_pixel
                    if frame.metres_per_pixel
                    else None
                )
                item.distance_status = "calibrated" if frame.metres_per_pixel else "unknown"
            for k, v in values.items():
                setattr(item, k, v)
            item.verified_by = actor.id if item.verified_on else None
            db.add(item)
            db.flush()
    revision.edit_version += 1
    revision.checksum = None
    audit(
        db,
        "indoor.patch",
        request_id,
        actor_id=actor.id,
        campus_id=revision.campus_id,
        revision_id=revision.id,
        resource_id=floor.id,
        before=before,
        after={
            "floor_id": str(floor.id),
            "mode": payload.mode,
            "changes": payload.model_dump(mode="json")["changes"],
        },
    )
    db.flush()
    return output(db, revision, floor)
