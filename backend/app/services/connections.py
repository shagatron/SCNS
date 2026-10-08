"""Draft-wide explicit connector editing; every batch and its audit are atomic."""

from copy import deepcopy
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.errors import DomainError
from app.models import Anchor, Building, Campus, Node, Place
from app.models.connections import (
    Connector,
    ConnectorPath,
    ConnectorStop,
    EntranceTransition,
    FloorRouting,
)
from app.models.floorplans import Floor
from app.models.indoor import IndoorNode
from app.schemas.connections import (
    ConnectorFields,
    ConnectorPathFields,
    ConnectorStopFields,
    EntranceTransitionFields,
    FloorRoutingFields,
)
from app.services.admin_auth import audit
from app.services.indoor import prerequisite

MODELS = {
    "policies": FloorRouting,
    "connectors": Connector,
    "stops": ConnectorStop,
    "paths": ConnectorPath,
    "transitions": EntranceTransition,
}
FIELDS = {
    "policies": FloorRoutingFields,
    "connectors": ConnectorFields,
    "stops": ConnectorStopFields,
    "paths": ConnectorPathFields,
    "transitions": EntranceTransitionFields,
}
LIMIT = 2000


def rows(db, revision):
    result = {}
    for entity, model in MODELS.items():
        items = db.scalars(
            select(model)
            .where(model.dataset_revision_id == revision.id)
            .order_by(model.id)
            .limit(LIMIT + 1)
        ).all()
        if len(items) > LIMIT:
            raise DomainError(
                "dataset_limit", "Connector editor supports 2,000 records per layer.", 422
            )
        result[entity] = {}
        for row in items:
            values = {k: getattr(row, k) for k in FIELDS[entity].model_fields if hasattr(row, k)}
            if entity in {"policies", "stops"}:
                values["layer_id"] = db.get(Floor, (revision.id, row.floor_id)).layer_id
            result[entity][str(row.id)] = FIELDS[entity](**values).model_dump(mode="json")
    return result


def context(db, revision):
    def objects(model):
        values = db.scalars(
            select(model).where(model.dataset_revision_id == revision.id).limit(15001)
        ).all()
        if len(values) > 15000:
            raise DomainError(
                "dataset_limit", "Connector context exceeds 15,000 records per layer.", 422
            )
        return {str(r.id): r for r in values}

    return {
        "floors": objects(Floor),
        "nodes": objects(IndoorNode),
        "buildings": objects(Building),
        "anchors": objects(Anchor),
        "places": objects(Place),
        "outdoor_nodes": objects(Node),
    }


def inspect(db, revision, state):
    ctx = context(db, revision)
    findings = []
    today = datetime.now(ZoneInfo(db.get(Campus, revision.campus_id).timezone)).date()

    def report(code, message, entity, ids, severity="error"):
        findings.append(dict(code=code, message=message, entity=entity, ids=ids, severity=severity))

    def error(message, entity, identity):
        report("connection_integrity", message, entity, [identity])

    for entity, values in state.items():
        if len(values) > LIMIT:
            error("Layer exceeds 2,000 records; use smaller reviewed batches.", entity, "")
        for identity, row in values.items():
            verified = date.fromisoformat(row["verified_on"]) if row.get("verified_on") else None
            if verified and (verified > today or len(row["evidence"].strip()) < 10):
                error(
                    "Verification needs substantive evidence and a non-future campus-local date.",
                    entity,
                    identity,
                )
            if not verified or (today - verified).days > 365:
                report(
                    "connection_unverified",
                    "Unknown/stale verification: survey before relying on this connection.",
                    entity,
                    [identity],
                    "warning",
                )
            if row.get("accessibility_status") == "verified_step_free" and not verified:
                error(
                    "Verified step-free requires dated evidence; plans cannot establish accessibility.",
                    entity,
                    identity,
                )
            if entity in {"policies", "stops"}:
                floor = ctx["floors"].get(row["floor_id"])
                if not floor or str(floor.layer_id) != row["layer_id"]:
                    error(
                        "Floor/selected plan changed. Explicitly reconcile against the current plan.",
                        entity,
                        identity,
                    )
                    continue
                if entity == "policies" and identity != row["floor_id"]:
                    error(
                        "A floor capability's stable ID must equal its floor ID.", entity, identity
                    )
                if row["visibility"] == "public" and floor.visibility != "public":
                    error(
                        "Public connection cannot reference a restricted floor.", entity, identity
                    )
                try:
                    prerequisite(
                        db, revision, floor, row.get("mode") if row.get("enabled") else None
                    )
                except DomainError as exc:
                    error(exc.message, entity, identity)
                if entity == "policies" and row["enabled"] and not verified:
                    error(
                        "Enabling routing requires dated topology evidence; otherwise retain display-only.",
                        entity,
                        identity,
                    )
            if entity == "connectors":
                building = ctx["buildings"].get(row["building_id"])
                if not building or (
                    row["visibility"] == "public" and building.visibility != "public"
                ):
                    error(
                        "Connector needs a same-revision building with compatible visibility.",
                        entity,
                        identity,
                    )
                stops = [s for s in state["stops"].values() if s["connector_id"] == identity]
                if len(stops) < (1 if row["kind"] == "entrance" else 2):
                    report(
                        "connector_incomplete",
                        "Map explicit served-floor stops and directed links; this group is incomplete.",
                        entity,
                        [identity],
                        "warning",
                    )
                if row["operational_status"] != "available":
                    report(
                        "connector_unavailable",
                        "Unknown/unavailable connector is excluded from all public routes.",
                        entity,
                        [identity],
                        "warning",
                    )
            if entity == "stops":
                connector = state["connectors"].get(row["connector_id"])
                node = ctx["nodes"].get(row["node_id"])
                floor = ctx["floors"].get(row["floor_id"])
                if (
                    not connector
                    or not node
                    or not floor
                    or str(node.floor_id) != row["floor_id"]
                    or str(floor.building_id) != connector["building_id"]
                ):
                    error(
                        "Stop must link its connector's building to an explicit node on its own floor.",
                        entity,
                        identity,
                    )
                    continue
                if connector["kind"] == "entrance" and node.kind != "entrance":
                    error("Entrance stops require an indoor entrance-kind node.", entity, identity)
                if row["visibility"] == "public" and (
                    connector["visibility"] != "public" or node.visibility != "public"
                ):
                    error(
                        "Public stop cannot expose a restricted connector/node.", entity, identity
                    )
                if not any(
                    row["connector_id"] == r["connector_id"]
                    and identity in (r.get("from_stop_id"), r.get("to_stop_id"), r.get("stop_id"))
                    for e in ("paths", "transitions")
                    for r in state[e].values()
                ):
                    report(
                        "connector_stop_unlinked",
                        "Stop has no explicit connector path/entrance transition.",
                        entity,
                        [identity],
                        "warning",
                    )
            if entity in {"paths", "transitions"}:
                connector = state["connectors"].get(row["connector_id"])
                stop_ids = (
                    [row["from_stop_id"], row["to_stop_id"]]
                    if entity == "paths"
                    else [row["stop_id"]]
                )
                stops = [state["stops"].get(i) for i in stop_ids]
                if not connector or any(
                    not s or s["connector_id"] != row["connector_id"] for s in stops
                ):
                    error(
                        "Missing stop/group reference: explicitly remove/rewire dependent links in the same batch.",
                        entity,
                        identity,
                    )
                    continue
                if row["visibility"] == "public" and (
                    connector["visibility"] != "public"
                    or any(s["visibility"] != "public" for s in stops)
                ):
                    error(
                        "Public traversal cannot expose restricted stops or groups.",
                        entity,
                        identity,
                    )
                if entity == "paths":
                    if (
                        connector["kind"] == "entrance"
                        or stops[0]["floor_id"] == stops[1]["floor_id"]
                    ):
                        error(
                            "Vertical paths require distinct floors and stairs/lift/ramp group; never subtract their pixels.",
                            entity,
                            identity,
                        )
                    if (
                        connector["kind"] == "stairs"
                        and row["accessibility_status"] == "verified_step_free"
                    ):
                        error("Stairs cannot claim verified step-free.", entity, identity)
                else:
                    anchor = ctx["anchors"].get(row["anchor_id"])
                    place = ctx["places"].get(str(anchor.place_id)) if anchor else None
                    node = ctx["outdoor_nodes"].get(str(anchor.node_id)) if anchor else None
                    if (
                        connector["kind"] != "entrance"
                        or not place
                        or not node
                        or place.point is None
                        or node.point is None
                        or str(place.building_id) != connector["building_id"]
                    ):
                        error(
                            "Transition must bind an explicit outdoor building entrance anchor to its entrance stop.",
                            entity,
                            identity,
                        )
                    elif row["visibility"] == "public" and (
                        place.visibility != "public" or node.visibility != "public"
                    ):
                        error(
                            "Public transition cannot expose a restricted outdoor entrance.",
                            entity,
                            identity,
                        )
                if row["distance_m"] is None:
                    report(
                        "connection_unknown_distance",
                        "No metric distance supplied: shortest-distance routing excludes this traversal; directions-only needs an explicit user choice.",
                        entity,
                        [identity],
                        "warning",
                    )
                if row["baseline_traversal_s"] is None or (
                    connector["kind"] == "lift" and row["wait_estimate_s"] is None
                ):
                    report(
                        "connection_unknown_time",
                        "Traversal/lift wait is unknown; ETA and fastest routing cannot invent seconds.",
                        entity,
                        [identity],
                        "warning",
                    )
                if not row["verified_on"] or not connector["verified_on"]:
                    report(
                        "connection_not_routable",
                        "Traversal/group verification is missing; it remains excluded from public routing.",
                        entity,
                        [identity],
                        "warning",
                    )
    for entity, key_fields in (
        ("connectors", ("building_id", "code")),
        ("stops", ("connector_id", "node_id")),
    ):
        seen = {}
        for identity, row in state[entity].items():
            key = tuple(row[k] for k in key_fields)
            if key in seen:
                error("Duplicate stable code or connector/node association.", entity, identity)
            seen[key] = identity
    for entity in ("paths", "transitions"):
        groups = {}
        for identity, row in state[entity].items():
            groups.setdefault(row["physical_path_id"], []).append((identity, row))
        for pair in groups.values():
            invalid = len(pair) > 2
            if len(pair) == 2:
                a, b = pair[0][1], pair[1][1]
                exclude = {"from_stop_id", "to_stop_id"} if entity == "paths" else {"direction"}
                invalid |= {k: v for k, v in a.items() if k not in exclude} != {
                    k: v for k, v in b.items() if k not in exclude
                }
                invalid |= (
                    (a["from_stop_id"] != b["to_stop_id"] or a["to_stop_id"] != b["from_stop_id"])
                    if entity == "paths"
                    else a["direction"] == b["direction"]
                )
            if invalid:
                report(
                    "connection_direction_pair",
                    "Physical path must be one direction or a consistent reverse pair.",
                    entity,
                    [p[0] for p in pair],
                )
    return findings


def output(db, revision):
    state = rows(db, revision)
    ctx = context(db, revision)
    return {
        "revision_version": revision.edit_version,
        "status": revision.status,
        "campus": {"is_demo": db.get(Campus, revision.campus_id).is_demo},
        **state,
        "buildings": {
            k: {"name": r.name, "code": r.code, "visibility": r.visibility}
            for k, r in ctx["buildings"].items()
        },
        "floors": {
            k: {
                "label": r.label,
                "code": r.code,
                "building_id": str(r.building_id),
                "layer_id": str(r.layer_id) if r.layer_id else None,
                "frame_id": str(r.frame_id) if r.frame_id else None,
                "visibility": r.visibility,
            }
            for k, r in ctx["floors"].items()
        },
        "nodes": {
            k: {
                "label": r.label,
                "floor_id": str(r.floor_id),
                "kind": r.kind,
                "visibility": r.visibility,
            }
            for k, r in ctx["nodes"].items()
        },
        "anchors": {
            k: {
                "node_id": str(r.node_id),
                "place_id": str(r.place_id),
                "label": ctx["places"][str(r.place_id)].name,
                "building_id": str(ctx["places"][str(r.place_id)].building_id),
                "is_open": r.is_open,
                "accessibility_status": r.accessibility_status,
            }
            for k, r in ctx["anchors"].items()
        },
    }


def validation(db, revision):
    findings = inspect(db, revision, rows(db, revision))
    return {
        "revision_version": revision.edit_version,
        "errors": sum(f["severity"] == "error" for f in findings),
        "warnings": sum(f["severity"] == "warning" for f in findings),
        "diagnostics": findings[:500],
        "truncated": len(findings) > 500,
    }


def proposal(db, revision, payload):
    if revision.status != "draft":
        raise DomainError("conflict", "Connector edits require an editable draft.", 409)
    before = rows(db, revision)
    after = deepcopy(before)
    for change in payload.changes:
        if change.data is None:
            after[change.entity].pop(str(change.id), None)
        else:
            after[change.entity][str(change.id)] = change.data.model_dump(mode="json")
    findings = inspect(db, revision, after)
    errors = [f for f in findings if f["severity"] == "error"]
    if errors:
        first = errors[0]
        raise DomainError(
            "connection_validation",
            f"{first['code']} ({first['entity']}: {', '.join(first['ids'])}): {first['message']}",
            422,
        )
    if len(findings) > 500:
        raise DomainError(
            "dataset_limit", "More than 500 connection diagnostics; reduce the batch.", 422
        )
    return before, after, findings


def apply_patch(db, revision, payload, actor, request_id):
    before, _, _ = proposal(db, revision, payload)
    # Changed dependent links are explicitly reinserted after their updated stops.
    for change in payload.changes:
        if change.entity in {"paths", "transitions"}:
            old = db.get(MODELS[change.entity], (revision.id, change.id))
            if old:
                db.delete(old)
                db.flush()
    for entity in ("transitions", "paths", "stops", "policies", "connectors"):
        for change in payload.changes:
            if change.entity == entity and change.data is None:
                old = db.get(MODELS[entity], (revision.id, change.id))
                if old:
                    db.delete(old)
                    db.flush()
    for entity in ("connectors", "policies", "stops", "paths", "transitions"):
        for change in payload.changes:
            if change.entity != entity or change.data is None:
                continue
            values = change.data.model_dump()
            item = db.get(MODELS[entity], (revision.id, change.id)) or MODELS[entity](
                id=change.id, dataset_revision_id=revision.id, campus_id=revision.campus_id
            )
            if entity in {"policies", "stops"}:
                floor = db.get(Floor, (revision.id, values["floor_id"]))
                frame, layer = prerequisite(
                    db, revision, floor, values.get("mode") if values.get("enabled") else None
                )
                values.pop("layer_id")
                item.frame_id, item.source_id = frame.id, layer.source_id
            for k, v in values.items():
                setattr(item, k, v)
            item.verified_by = actor.id if item.verified_on else None
            db.add(item)
            db.flush()
    revision.edit_version += 1
    revision.checksum = None
    audit(
        db,
        "connections.patch",
        request_id,
        actor_id=actor.id,
        campus_id=revision.campus_id,
        revision_id=revision.id,
        resource_id=revision.id,
        before=before,
        after=payload.model_dump(mode="json"),
    )
    db.flush()
    return output(db, revision)


def route_evidence_requirements(full, evidence):
    """Publication covers enabled floors and both directions of new capability classes."""
    rooms = full.get("indoor_rooms", {})
    enabled = {
        row["floor_id"]
        for row in full.get("floor_routing", {}).values()
        if row["enabled"] and row["visibility"] == "public"
    }
    results = []

    def require(predicate, message, ids, positive=False):
        cases = [e for e in evidence if e.get("passed") and predicate(e)]
        if not {"shortest", "step_free"}.issubset({e["profile"] for e in cases}) or (
            positive
            and not any(
                e["profile"] == "shortest" and e.get("actual", {}).get("found") for e in cases
            )
        ):
            results.append(
                dict(
                    code="indoor_route_evidence",
                    message=message,
                    entity="routes",
                    ids=ids,
                    severity="error",
                )
            )

    for floor in sorted(enabled):
        public = {
            i for i, r in rooms.items() if r["floor_id"] == floor and r["visibility"] == "public"
        }
        if not public:
            results.append(
                dict(
                    code="routing_empty_floor",
                    message="Enabled public floor has no public destinations. Retain display-only or map explicit room access.",
                    entity="floors",
                    ids=[floor],
                    severity="error",
                )
            )
            continue
        require(
            lambda e, public=public: e["source"] in public or e["target"] in public,
            "Supply standard and step-free expected-route evidence involving each enabled floor (negative step-free evidence is allowed).",
            [floor],
            positive=True,
        )
        if len(public) > 1:
            require(
                lambda e, public=public: e["source"] in public and e["target"] in public,
                "Supply same-floor standard and step-free route evidence for this floor.",
                [floor],
                positive=True,
            )
    public_paths = [
        e
        for e in full.get("connector_paths", {}).values()
        if e["visibility"] == "public" and e["is_open"]
    ]
    pairs = set()
    for edge in public_paths:
        a = full["connector_stops"][edge["from_stop_id"]]["floor_id"]
        b = full["connector_stops"][edge["to_stop_id"]]["floor_id"]
        if a in enabled and b in enabled:
            pairs.add((a, b))
    for a, b in sorted(pairs):
        require(
            lambda e, a=a, b=b: (
                rooms.get(e["source"], {}).get("floor_id") == a
                and rooms.get(e["target"], {}).get("floor_id") == b
            ),
            "Supply standard and step-free expected cross-floor routes for every mapped direction.",
            [a, b],
        )
    if full.get("entrance_transitions") and enabled:
        for entering in (True, False):
            require(
                lambda e, entering=entering: (
                    (
                        e["source"] not in rooms
                        and rooms.get(e["target"], {}).get("floor_id") in enabled
                    )
                    if entering
                    else (
                        e["target"] not in rooms
                        and rooms.get(e["source"], {}).get("floor_id") in enabled
                    )
                ),
                "Supply standard and step-free indoor/outdoor evidence in both directions, including expected no-route for a one-way entrance.",
                sorted(enabled),
            )
    return results
