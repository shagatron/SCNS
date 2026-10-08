"""Versioned, audited restrictions over current public physical features."""

from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from app.core.errors import DomainError
from app.models.closures import Closure, ClosureAction, ClosureOverlay
from app.services.admin_auth import audit
from app.services.publication import checksum

LIMIT = 2000


def version(db, campus):
    return db.scalar(select(ClosureOverlay.version).where(ClosureOverlay.campus_id == campus)) or 0


def records(db, campus):
    values = db.scalars(
        select(Closure)
        .where(Closure.campus_id == campus)
        .order_by(Closure.created_at, Closure.id)
        .limit(LIMIT + 1)
    ).all()
    if len(values) > LIMIT:
        raise DomainError(
            "service_unavailable",
            "Operational history exceeds the supported 2,000-record budget; contact the operator.",
            503,
        )
    return values


def target(data, kind, identity):
    identity = str(identity)
    if kind in {"outdoor_edge", "outdoor_path"}:
        rows = (
            ([data["edges"][identity]] if identity in data.get("edges", {}) else [])
            if kind == "outdoor_edge"
            else [e for e in data.get("edges", {}).values() if e["physical_path_id"] == identity]
        )
        if not rows:
            return None
        bindings = [
            {
                "id": e["id"],
                "physical_path_id": e["physical_path_id"],
                "geometry": e["geometry"],
                "from": e["from_node_id"],
                "to": e["to_node_id"],
            }
            for e in rows
        ]
        labels = sorted(
            {
                f"{data['nodes'][e['from_node_id']]['label']} → {data['nodes'][e['to_node_id']]['label']}"
                for e in rows
            }
        )
        label = " / ".join(labels)
    elif kind == "indoor_edge":
        e = data.get("indoor_edges", {}).get(identity)
        if not e:
            return None
        f = data["floors"][e["floor_id"]]
        if f.get("navigation_mode") not in {"metric", "directions_only"}:
            return None
        bindings = [
            dict(
                edge=e["id"],
                polyline=e["polyline"],
                frame=f["frame_id"],
                layer=f["layer_id"],
                plan=data["floorplans"][f["layer_id"]]["checksum"],
                from_node=e["from_node_id"],
                to_node=e["to_node_id"],
            )
        ]
        label = f"{f['label']} · {data['indoor_nodes'][e['from_node_id']]['label']} → {data['indoor_nodes'][e['to_node_id']]['label']}"
    elif kind == "connector":
        c = data.get("connectors", {}).get(identity)
        if not c:
            return None
        stops = [
            s for s in data.get("connector_stops", {}).values() if s["connector_id"] == identity
        ]
        paths = [
            p
            for layer in ("connector_paths", "entrance_transitions")
            for p in data.get(layer, {}).values()
            if p["connector_id"] == identity
        ]
        if not stops or not paths:
            return None
        bindings = [{"kind": c["kind"], "building": c["building_id"]}]
        for s in sorted(stops, key=lambda s: s["id"]):
            f = data["floors"][s["floor_id"]]
            bindings.append(
                dict(
                    stop=s["id"],
                    node={
                        k: data["indoor_nodes"][s["node_id"]].get(k)
                        for k in ("id", "floor_id", "frame_id", "x_px", "y_px")
                    },
                    frame=f["frame_id"],
                    layer=f["layer_id"],
                    plan=data["floorplans"][f["layer_id"]]["checksum"],
                )
            )
        bindings.extend(
            {
                k: p.get(k)
                for k in (
                    "id",
                    "physical_path_id",
                    "from_stop_id",
                    "to_stop_id",
                    "stop_id",
                    "anchor_id",
                    "direction",
                )
            }
            for p in sorted(paths, key=lambda p: p["id"])
        )
        label = f"{c['kind']} · {c['label']}"
    else:
        return None
    return {
        "kind": kind,
        "id": identity,
        "label": label[:300],
        "checksum": checksum(sorted(bindings, key=checksum)),
    }


def targets(data):
    choices = []
    paths = {}
    for i, edge in data.get("edges", {}).items():
        paths.setdefault(edge["physical_path_id"], {})[i] = edge
    identities = [
        ("outdoor_edge", list(data.get("edges", {}))),
        ("outdoor_path", sorted({e["physical_path_id"] for e in data.get("edges", {}).values()})),
        ("indoor_edge", list(data.get("indoor_edges", {}))),
        ("connector", list(data.get("connectors", {}))),
    ]
    for kind, ids in identities:
        for identity in ids:
            value = target(
                {**data, "edges": paths[identity]} if kind == "outdoor_path" else data,
                kind,
                identity,
            )
            if value:
                choices.append(value)
    return sorted(choices, key=lambda c: (c["kind"], c["label"], c["id"]))


def record(obj):
    return {
        c.name: getattr(obj, c.name).isoformat()
        if isinstance(getattr(obj, c.name), datetime)
        else str(getattr(obj, c.name))
        if c.name in {"id", "campus_id", "target_id", "created_by"}
        else getattr(obj, c.name)
        for c in obj.__table__.columns
    }


def require_version(db, campus, header):
    if header is None:
        raise DomainError(
            "precondition_required", "Send the quoted overlay version in If-Match.", 428
        )
    if header != f'"{version(db, campus)}"':
        raise DomainError(
            "conflict",
            "Restrictions changed. Compare latest overlay and retain your input before retrying.",
            409,
        )


def bump(db, campus):
    obj = db.get(ClosureOverlay, campus, populate_existing=True)
    if obj is None:
        obj = ClosureOverlay(campus_id=campus, version=0)
        db.add(obj)
    obj.version += 1
    db.flush()
    return obj.version


def retry(db, campus, actor, payload, action, identity):
    fingerprint = checksum(
        dict(action=action, id=str(identity), payload=payload.model_dump(mode="json"))
    )
    prior = db.scalar(
        select(ClosureAction).where(
            ClosureAction.campus_id == campus,
            ClosureAction.actor_id == actor.id,
            ClosureAction.key == payload.key,
        )
    )
    if prior and prior.fingerprint != fingerprint:
        raise DomainError("conflict", "Retry key belongs to a different operation.", 409)
    return fingerprint, prior.result if prior else None


def mutate(db, campus, actor, payload, header, request_id, action="create", identity=None):
    fingerprint, prior = retry(db, campus, actor, payload, action, identity)
    if prior:
        return prior
    require_version(db, campus, header)
    from app.services.catalog import active_release
    from app.services.mixed_routes import release_projection

    release = active_release(db, campus)
    data = release_projection(db, release)
    before = None
    if action == "create":
        if len(records(db, campus)) >= LIMIT:
            raise DomainError(
                "dataset_limit",
                "Operational history supports 2,000 entries; contact the operator.",
                422,
            )
        obj = Closure(
            id=uuid4(),
            campus_id=campus,
            created_by=actor.id,
            reason=payload.reason,
            starts_at=payload.starts_at,
            estimated_end_at=payload.estimated_end_at,
            state="closed",
        )
        db.add(obj)
    else:
        obj = db.scalar(
            select(Closure)
            .where(Closure.campus_id == campus, Closure.id == identity)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not obj:
            raise DomainError("location_not_found", "Restriction not found in this campus.", 404)
        before = record(obj)
        if obj.state == "reopened":
            raise DomainError(
                "conflict",
                "This restriction was already reopened; create a new restriction for a new incident.",
                409,
            )
    if action in {"create", "rebind"}:
        value = target(data, payload.target_kind, payload.target_id)
        if not value:
            raise DomainError(
                "invalid_input", "Choose a current published public path or connector.", 422
            )
        obj.target_kind, obj.target_id, obj.label, obj.target_checksum = (
            payload.target_kind,
            payload.target_id,
            value["label"],
            value["checksum"],
        )
        obj.state = "closed"
    if action == "reopen":
        obj.state, obj.reopened_at, obj.reopen_evidence = (
            "reopened",
            datetime.now(UTC),
            payload.evidence,
        )
    overlay_version = bump(db, campus)
    db.flush()
    result = {"id": str(obj.id), "closure_overlay_version": overlay_version, "state": obj.state}
    audit(
        db,
        f"closure.{action}",
        request_id,
        actor_id=actor.id,
        campus_id=campus,
        resource_id=obj.id,
        before=before,
        after={
            **record(obj),
            "closure_overlay_version": overlay_version,
            "decision_evidence": getattr(payload, "evidence", None),
        },
    )
    db.add(
        ClosureAction(
            campus_id=campus,
            actor_id=actor.id,
            key=payload.key,
            fingerprint=fingerprint,
            result=result,
        )
    )
    db.flush()
    return result


def reconcile(db, release, data, actor, request_id):
    changes = []
    for obj in records(db, release.campus_id):
        if obj.state != "closed":
            continue
        value = target(data, obj.target_kind, obj.target_id)
        if not value or value["checksum"] != obj.target_checksum:
            before = record(obj)
            obj.state = "unresolved"
            changes.append((obj, before))
    if changes:
        overlay_version = bump(db, release.campus_id)
        for obj, before in changes:
            audit(
                db,
                "closure.release_reconcile",
                request_id,
                actor_id=actor.id,
                campus_id=release.campus_id,
                resource_id=obj.id,
                before=before,
                after={
                    **record(obj),
                    "release_id": str(release.id),
                    "closure_overlay_version": overlay_version,
                },
            )
    return version(db, release.campus_id)


def public_status(db, campus, release, data, now=None):
    now = now or datetime.now(UTC)
    items, changes = [], []
    for obj in records(db, campus):
        if obj.state == "reopened":
            continue
        value = target(data, obj.target_kind, obj.target_id)
        unresolved = (
            obj.state == "unresolved" or not value or value["checksum"] != obj.target_checksum
        )
        if obj.starts_at > now:
            changes.append(obj.starts_at)
        items.append(
            dict(
                id=obj.id,
                target_kind=None if unresolved else obj.target_kind,
                target_id=None if unresolved else obj.target_id,
                label="Restriction needs operator target review" if unresolved else value["label"],
                reason="A retained restriction requires operator review."
                if unresolved
                else obj.reason,
                starts_at=obj.starts_at,
                estimated_end_at=obj.estimated_end_at,
                state="unresolved"
                if unresolved
                else "scheduled"
                if obj.starts_at > now
                else "active",
            )
        )
    return dict(
        release_id=release.id,
        closure_overlay_version=version(db, campus),
        checked_at=now,
        next_change_at=min(changes) if changes else None,
        unresolved_count=sum(i["state"] == "unresolved" for i in items),
        items=items,
    )


def apply(data, entries, window_end):
    result = deepcopy(data)
    for obj in entries:
        if obj.state == "reopened" or (window_end is not None and obj.starts_at > window_end):
            continue
        value = target(data, obj.target_kind, obj.target_id)
        if obj.state == "unresolved" or not value or value["checksum"] != obj.target_checksum:
            raise DomainError(
                "closure_unresolved",
                "An operational restriction needs target review. Routing is paused until the campus operator reconciles it; choose another campus or seek assistance.",
                503,
            )
        if obj.target_kind == "outdoor_edge":
            result["edges"][str(obj.target_id)]["is_open"] = False
        elif obj.target_kind == "outdoor_path":
            for edge in result["edges"].values():
                if edge["physical_path_id"] == str(obj.target_id):
                    edge["is_open"] = False
        elif obj.target_kind == "indoor_edge":
            result["indoor_edges"][str(obj.target_id)]["is_open"] = False
        else:
            result["connectors"][str(obj.target_id)]["operational_status"] = "unavailable"
    return result
