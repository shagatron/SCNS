"""Campus-scoped operational inventory against the immutable public projection."""

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.config import get_settings
from app.core.errors import DomainError
from app.models import Campus
from app.models.qr import QRMarker
from app.schemas.qr import MarkerResolution
from app.services.admin_auth import audit
from app.services.catalog import active_release
from app.services.mixed_routes import release_projection
from app.services.publication import checksum


def target(data, kind, identity):
    node = data.get("nodes" if kind == "outdoor" else "indoor_nodes", {}).get(str(identity))
    if not node:
        return None
    result = {"node": node, "kind": kind}
    if kind == "indoor":
        floor = data.get("floors", {}).get(node["floor_id"])
        if not floor or floor["navigation_mode"] not in {"metric", "directions_only"}:
            return None
        result["floor"] = floor
        result["frame"] = data["frames"][floor["frame_id"]]
        result["plan_checksum"] = data["floorplans"][floor["layer_id"]]["checksum"]
    return result


def target_hash(value):
    node = value["node"]
    # Label changes do not imply physical movement; coordinate/frame/plan/scale changes do.
    position = {
        k: node.get(k) for k in ("id", "frame_id", "floor_id", "point", "x_px", "y_px", "kind")
    }
    if value["kind"] == "indoor":
        position.update(plan=value["plan_checksum"], frame=value["frame"])
    return checksum(position)


def record(row):
    return {
        c.name: str(getattr(row, c.name))
        if isinstance(getattr(row, c.name), UUID)
        else getattr(row, c.name).isoformat()
        if isinstance(getattr(row, c.name), datetime)
        else getattr(row, c.name)
        for c in row.__table__.columns
    }


def row(db, campus, identity, header=None):
    obj = db.scalar(
        select(QRMarker)
        .where(QRMarker.campus_id == campus, QRMarker.id == identity)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not obj:
        raise DomainError("location_not_found", "Marker not found in this campus.", 404)
    if header is not None and header != f'"{obj.version}"':
        raise DomainError(
            "conflict",
            "Marker changed. Compare latest inventory and retain your inputs before retrying.",
            409,
        )
    return obj


def require_version(header):
    import re

    if not header:
        raise DomainError(
            "precondition_required", "Send the quoted current marker version in If-Match.", 428
        )
    if not re.fullmatch(r'"[1-9][0-9]{0,9}"', header):
        raise DomainError("invalid_input", "If-Match needs a quoted positive marker version.")


def current(db, campus):
    release = active_release(db, campus)
    return release, release_projection(db, release)


def set_target(db, obj, payload):
    release, data = current(db, obj.campus_id)
    selected = target(data, payload.node_kind, payload.node_id)
    if not selected:
        raise DomainError(
            "invalid_input",
            "Choose a current published public outdoor node or reviewed routable floor node.",
        )
    obj.release_id, obj.target_checksum = release.id, target_hash(selected)
    obj.label, obj.node_kind, obj.node_id = payload.label, payload.node_kind, payload.node_id
    obj.intended_position = payload.intended_position
    obj.installation, obj.state = {}, "planned"


def change(db, obj, actor, request_id, action, before):
    obj.version += 1
    audit(
        db,
        action,
        request_id,
        actor_id=actor.id,
        campus_id=obj.campus_id,
        resource_id=obj.id,
        before=before,
        after=record(obj),
    )
    db.flush()
    return record(obj)


def create(db, campus, actor, payload, request_id):
    existing = db.scalar(
        select(QRMarker).where(
            QRMarker.campus_id == campus,
            QRMarker.created_by == actor.id,
            QRMarker.key == payload.key,
        )
    )
    if existing:
        expected = payload.model_dump(mode="json", exclude={"key"})
        if any(record(existing)[k] != v for k, v in expected.items()):
            raise DomainError("conflict", "Creation key belongs to different marker content.", 409)
        return record(existing)
    if db.scalar(select(QRMarker.id).where(QRMarker.campus_id == campus).offset(2000).limit(1)):
        raise DomainError("dataset_limit", "This inventory supports at most 2000 markers.", 422)
    obj = QRMarker(campus_id=campus, created_by=actor.id, key=payload.key, version=1)
    set_target(db, obj, payload)
    db.add(obj)
    db.flush()
    audit(
        db,
        "qr.create",
        request_id,
        actor_id=actor.id,
        campus_id=campus,
        resource_id=obj.id,
        after=record(obj),
    )
    return record(obj)


def edit(db, obj, actor, payload, request_id):
    before = record(obj)
    set_target(db, obj, payload)
    return change(db, obj, actor, request_id, "qr.reassign", before)


def verify(db, obj, actor, payload, request_id):
    if obj.state not in {"planned", "needs_verification"}:
        raise DomainError(
            "conflict",
            "Reassign/replan before verification; active/revoked/retired markers cannot silently reactivate.",
            409,
        )
    today = datetime.now(ZoneInfo(db.get(Campus, obj.campus_id).timezone)).date()
    if not payload.installed_on <= payload.verified_on <= today:
        raise DomainError(
            "invalid_input",
            "Installation/verification dates must be ordered and not in the future.",
        )
    release, data = current(db, obj.campus_id)
    selected = target(data, obj.node_kind, obj.node_id)
    if not selected:
        raise DomainError("invalid_input", "Target is no longer eligible; explicitly reassign it.")
    before = record(obj)
    obj.release_id, obj.target_checksum = release.id, target_hash(selected)
    obj.installation = {**payload.model_dump(mode="json"), "verified_by": str(actor.id)}
    obj.state = "active"
    return change(db, obj, actor, request_id, "qr.activate", before)


def revoke(db, obj, actor, payload, request_id):
    before = record(obj)
    obj.state = "revoked"
    obj.installation = {**obj.installation, "revocation_reason": payload.reason}
    return change(db, obj, actor, request_id, "qr.revoke", before)


def resolve(db, identity):
    # Shared row lock serializes revocation/reassignment against route calculation.
    obj = db.scalar(select(QRMarker).where(QRMarker.id == identity).with_for_update(read=True))
    if not obj:
        raise DomainError(
            "location_not_found", "This marker is unknown. Choose a manual start.", 404
        )
    release, data = current(db, obj.campus_id)
    selected = target(data, obj.node_kind, obj.node_id)
    state = obj.state
    if state == "active":
        state = (
            "retired"
            if not selected
            else "needs_verification"
            if target_hash(selected) != obj.target_checksum
            else "active"
        )
    messages = {
        "planned": "This sign is not installed and verified. Choose a manual start.",
        "revoked": "This QR marker has been revoked. Choose a manual start.",
        "retired": "This QR marker is retired because its public location is unavailable. Choose a manual start.",
        "needs_verification": "The marker location changed and requires installation re-verification. Choose a manual start.",
        "active": "Confirm you are physically at this labelled marker now. Scanning does not continuously track your position.",
    }
    values = {}
    if state == "active":
        values = {
            "label": obj.label,
            "node_id": obj.node_id,
            "node_kind": obj.node_kind,
            "node_label": selected["node"]["label"],
            "floor_id": selected.get("floor", {}).get("id"),
            "floor_label": selected.get("floor", {}).get("label"),
            "building_name": data.get("buildings", {})
            .get(selected.get("floor", {}).get("building_id"), {})
            .get("name"),
            "verified_on": obj.installation["verified_on"],
        }
    return MarkerResolution(
        id=obj.id,
        campus_id=obj.campus_id,
        campus_name=data["campus"]["name"],
        version=obj.version,
        state=state,
        release_id=release.id,
        is_demo=data["campus"]["is_demo"],
        message=messages[state],
        **values,
    )


def reconcile(db, release, data, actor, request_id):
    """Same transaction as publication/rollback; never resurrect a revoked/retired marker."""
    for obj in db.scalars(
        select(QRMarker).where(QRMarker.campus_id == release.campus_id).with_for_update()
    ):
        selected = target(data, obj.node_kind, obj.node_id)
        before = record(obj)
        if obj.state == "active":
            if not selected:
                obj.state = "retired"
            elif target_hash(selected) != obj.target_checksum:
                obj.state = "needs_verification"
        # Retain previous installed geometry/checksum; re-verification is deliberate.
        obj.release_id = release.id
        change(db, obj, actor, request_id, "qr.release_revalidate", before)


def listing(db, campus):
    release, data = current(db, campus)
    targets = []
    for kind, layer in [("outdoor", "nodes"), ("indoor", "indoor_nodes")]:
        for identity in sorted(data.get(layer, {})):
            selected = target(data, kind, identity)
            if selected:
                targets.append(
                    {
                        "id": identity,
                        "kind": kind,
                        "label": selected["node"]["label"],
                        "floor_label": selected.get("floor", {}).get("label"),
                        "building_name": data.get("buildings", {})
                        .get(selected.get("floor", {}).get("building_id"), {})
                        .get("name"),
                    }
                )
    items = [
        record(o)
        for o in db.scalars(
            select(QRMarker)
            .where(QRMarker.campus_id == campus)
            .order_by(QRMarker.created_at, QRMarker.id)
            .limit(2000)
        )
    ]
    return {
        "release_id": str(release.id),
        "items": items,
        "targets": targets[:5000],
        "targets_truncated": len(targets) > 5000,
        "canonical_origin": get_settings().public_app_url,
    }
