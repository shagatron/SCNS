import json
from uuid import UUID, uuid4

from sqlalchemy import delete, func, insert, literal, select, text, update
from sqlalchemy.orm import Session

from app.cli.dataset import geometry
from app.core.errors import DomainError
from app.models import (
    ActiveRelease,
    Anchor,
    Building,
    Edge,
    Frame,
    Node,
    Place,
    Release,
    Revision,
)
from app.models.admin import AuditEvent, Department, DepartmentPlace, PlaceAlias
from app.models.connections import (
    Connector,
    ConnectorPath,
    ConnectorStop,
    EntranceTransition,
    FloorRouting,
)
from app.models.floorplans import Floor, MapLayer
from app.models.imports import ImportBinding
from app.models.indoor import IndoorAccess, IndoorEdge, IndoorNode, Room
from app.models.publication import SourceAsset
from app.schemas.admin import CatalogRecord, CatalogWrite, DraftOut
from app.services.admin_auth import audit
from app.services.catalog import normalize

MODELS = {
    "buildings": Building,
    "places": Place,
    "departments": Department,
    "aliases": PlaceAlias,
    "anchors": Anchor,
}


def draft_output(revision):
    return DraftOut(
        id=revision.id,
        campus_id=revision.campus_id,
        version=revision.version,
        edit_version=revision.edit_version,
        status=revision.status,
        created_at=revision.created_at,
    )


def get_draft(db: Session, campus_id: UUID, revision_id: UUID):
    revision = db.scalar(
        select(Revision)
        .where(Revision.id == revision_id, Revision.campus_id == campus_id)
        .execution_options(populate_existing=True)
    )
    if not revision or revision.status != "draft":
        raise DomainError("location_not_found", "Editable draft not found in this campus.", 404)
    return revision


def create_draft(
    db: Session, campus_id: UUID, actor_id: UUID, request_id: str, key: str | None = None
):
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": str(campus_id)})
    if key:
        prior = db.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "draft.create",
                AuditEvent.actor_id == actor_id,
                AuditEvent.campus_id == campus_id,
                AuditEvent.after["idempotency_key"].astext == key,
            )
        )
        if prior:
            revision = db.get(Revision, prior.revision_id)
            if not revision or revision.status != "draft":
                raise DomainError("conflict", "This retry belongs to a non-editable draft.", 409)
            return draft_output(revision)
    active = db.get(ActiveRelease, (campus_id, "public"))
    release = db.get(Release, active.release_id) if active else None
    parent = release.dataset_revision_id if release else None
    revision = Revision(
        id=uuid4(),
        campus_id=campus_id,
        status="draft",
        checksum=None,
        parent_id=parent,
        version=(
            db.scalar(select(func.max(Revision.version)).where(Revision.campus_id == campus_id))
            or 0
        )
        + 1,
    )
    db.add(revision)
    db.flush()
    if parent:
        used = db.scalar(
            select(func.coalesce(func.sum(func.octet_length(SourceAsset.original)), 0)).where(
                SourceAsset.campus_id == campus_id
            )
        )
        copying = db.scalar(
            select(func.coalesce(func.sum(func.octet_length(SourceAsset.original)), 0)).where(
                SourceAsset.dataset_revision_id == parent
            )
        )
        if used + copying > 100 * 1024 * 1024:
            raise DomainError(
                "storage_limit",
                "Cloning these originals exceeds the campus 100MiB source quota. Retain releases and use a smaller source dataset.",
                413,
            )
        from app.services.floorplans import quota

        copying_png = db.scalar(
            select(func.coalesce(func.sum(func.octet_length(MapLayer.png)), 0)).where(
                MapLayer.dataset_revision_id == parent
            )
        )
        quota(db, campus_id, copying + copying_png)
        for model in (
            Frame,
            Building,
            Place,
            Node,
            Edge,
            Anchor,
            Department,
            PlaceAlias,
            DepartmentPlace,
            ImportBinding,
            SourceAsset,
            Floor,
            MapLayer,
            Room,
            IndoorNode,
            IndoorEdge,
            IndoorAccess,
            FloorRouting,
            Connector,
            ConnectorStop,
            ConnectorPath,
            EntranceTransition,
        ):
            if model is Room:
                db.execute(
                    text(
                        "UPDATE floors f SET layer_id = p.layer_id FROM floors p WHERE f.dataset_revision_id = :new AND p.dataset_revision_id = :parent AND f.id = p.id"
                    ),
                    {"new": revision.id, "parent": parent},
                )
            table = model.__table__
            db.execute(
                insert(table).from_select(
                    [c.name for c in table.columns],
                    select(
                        *[
                            literal(revision.id)
                            if c.name == "dataset_revision_id"
                            else literal(None)
                            if model is Floor and c.name == "layer_id"
                            else c
                            for c in table.columns
                        ]
                    ).where(table.c.dataset_revision_id == parent),
                )
            )

    audit(
        db,
        "draft.create",
        request_id,
        actor_id=actor_id,
        campus_id=campus_id,
        revision_id=revision.id,
        resource_id=revision.id,
        after={
            "parent_id": str(parent) if parent else None,
            "version": revision.version,
            **({"idempotency_key": key} if key else {}),
        },
    )
    return draft_output(revision)


def claim_version(db: Session, revision: Revision, header: str | None):
    if header is None:
        raise DomainError(
            "precondition_required", "Send the current draft version in If-Match.", 428
        )
    import re

    if not re.fullmatch(r'"[1-9][0-9]{0,9}"', header):
        raise DomainError(
            "invalid_input", 'If-Match must contain the quoted draft version, for example "1".'
        )
    expected = int(header.strip('"'))
    version = db.scalar(
        update(Revision)
        .where(
            Revision.id == revision.id,
            Revision.status == "draft",
            Revision.edit_version == expected,
        )
        .values(edit_version=Revision.edit_version + 1, checksum=None)
        .returning(Revision.edit_version)
        .execution_options(synchronize_session=False)
    )
    if version is None:
        raise DomainError(
            "conflict",
            "This draft changed since you loaded it. Reload and reconcile your edits.",
            409,
        )
    db.refresh(revision)
    return version


def record(db: Session, entity: str, row) -> CatalogRecord:
    if entity == "buildings":
        data = dict(
            code=row.code,
            name=row.name,
            visibility=row.visibility,
            footprint=json.loads(db.scalar(select(func.ST_AsGeoJSON(row.footprint)))),
        )
    elif entity == "places":
        data = dict(
            code=row.code,
            name=row.name,
            kind=row.kind,
            description=row.description,
            building_id=row.building_id,
            visibility=row.visibility,
            point=json.loads(db.scalar(select(func.ST_AsGeoJSON(row.point))))
            if row.point is not None
            else None,
        )
    elif entity == "departments":
        data = dict(
            code=row.code,
            name=row.name,
            description=row.description,
            place_ids=list(
                db.scalars(
                    select(DepartmentPlace.place_id)
                    .where(
                        DepartmentPlace.dataset_revision_id == row.dataset_revision_id,
                        DepartmentPlace.department_id == row.id,
                    )
                    .order_by(DepartmentPlace.place_id)
                )
            ),
        )
    elif entity == "aliases":
        data = dict(place_id=row.place_id, value=row.value, language=row.language)
    else:
        data = dict(
            place_id=row.place_id,
            node_id=row.node_id,
            accessibility_status=row.accessibility_status,
            accessibility_evidence=row.accessibility_evidence,
            is_open=row.is_open,
        )
    return CatalogRecord(id=row.id, item={"entity": entity, "data": data})


def referenced(db, model, revision_id, resource_id):
    row = db.get(model, (revision_id, resource_id))
    if row is None:
        raise DomainError("invalid_input", "A referenced record is not in this draft.")
    return row


def sync_aliases(db, revision_id, place_id):
    place = referenced(db, Place, revision_id, place_id)
    place.aliases = list(
        db.scalars(
            select(PlaceAlias.value)
            .where(PlaceAlias.dataset_revision_id == revision_id, PlaceAlias.place_id == place_id)
            .order_by(PlaceAlias.value)
        )
    )
    room = db.get(Room, (revision_id, place_id))
    place.search_text = normalize(
        " ".join([room.code if room else place.code, place.name, place.kind, *place.aliases])
    )


def write_record(
    db: Session, revision: Revision, payload: CatalogWrite, resource_id=None, *, create_id=None
):
    entity, data = payload.entity, payload.data
    row = (
        referenced(db, MODELS[entity], revision.id, resource_id)
        if resource_id
        else MODELS[entity](
            id=create_id or uuid4(), campus_id=revision.campus_id, dataset_revision_id=revision.id
        )
    )
    if entity == "places" and resource_id and db.get(Room, (revision.id, resource_id)):
        raise DomainError(
            "conflict",
            "Edit this floor-local destination through the indoor editor; do not replace its local coordinates with geography.",
            409,
        )
    before = record(db, entity, row).model_dump(mode="json") if resource_id else None
    values = data.model_dump()
    if entity == "buildings":
        if not db.scalar(select(func.ST_IsValid(geometry(data.footprint)))):
            raise DomainError("invalid_input", "Building footprint is not a valid polygon.")
        if data.visibility == "restricted" and (
            db.scalar(
                select(Place.id)
                .where(
                    Place.dataset_revision_id == revision.id,
                    Place.building_id == row.id,
                    Place.visibility == "public",
                )
                .limit(1)
            )
            or db.scalar(
                select(Floor.id)
                .where(
                    Floor.dataset_revision_id == revision.id,
                    Floor.building_id == row.id,
                    Floor.visibility == "public",
                )
                .limit(1)
            )
        ):
            raise DomainError(
                "conflict",
                "Restrict or detach public places/floors before restricting their building.",
                409,
            )
        values["footprint"] = geometry(data.footprint)
    elif entity == "places":
        if data.building_id:
            building = referenced(db, Building, revision.id, data.building_id)
            if data.visibility == "public" and building.visibility != "public":
                raise DomainError(
                    "invalid_input", "A public place cannot belong to a restricted building."
                )
        if data.visibility == "public":
            restricted_nodes = select(Node.id).where(
                Node.dataset_revision_id == revision.id, Node.visibility != "public"
            )
            if db.scalar(
                select(Anchor.id)
                .where(
                    Anchor.dataset_revision_id == revision.id,
                    Anchor.place_id == row.id,
                    Anchor.node_id.in_(restricted_nodes),
                )
                .limit(1)
            ):
                raise DomainError(
                    "conflict",
                    "Remove restricted-node anchors before making this place public.",
                    409,
                )
        values["point"] = geometry(data.point)
        values["aliases"] = row.aliases or []
        values["search_text"] = normalize(
            " ".join([data.code, data.name, data.kind, *values["aliases"]])
        )
    elif entity == "departments":
        values.pop("place_ids")
        if len(set(data.place_ids)) != len(data.place_ids):
            raise DomainError("invalid_input", "Department place links must be unique.")
        for place_id in data.place_ids:
            referenced(db, Place, revision.id, place_id)
    elif entity in {"aliases", "anchors"}:
        place = referenced(db, Place, revision.id, data.place_id)
        if entity == "aliases":
            values["normalized"] = normalize(data.value)
            if not values["normalized"]:
                raise DomainError("invalid_input", "Alias must contain searchable text.")
        else:
            if (
                data.accessibility_status == "verified_step_free"
                and not data.accessibility_evidence.strip()
            ):
                raise DomainError(
                    "invalid_input",
                    "Step-free verification requires evidence notes, including source and verification date.",
                )
            node = referenced(db, Node, revision.id, data.node_id)
            if place.visibility == "public" and node.visibility != "public":
                raise DomainError(
                    "invalid_input", "A public anchor cannot expose a restricted node."
                )
    for key, value in values.items():
        setattr(row, key, value)
    db.add(row)
    db.flush()
    if entity == "departments" and (
        before is None
        or set(before["item"]["data"]["place_ids"]) != {str(value) for value in data.place_ids}
    ):
        db.execute(
            delete(DepartmentPlace).where(
                DepartmentPlace.dataset_revision_id == revision.id,
                DepartmentPlace.department_id == row.id,
            )
        )
        for place_id in data.place_ids:
            db.add(
                DepartmentPlace(
                    id=uuid4(),
                    campus_id=revision.campus_id,
                    dataset_revision_id=revision.id,
                    department_id=row.id,
                    place_id=place_id,
                )
            )
        db.flush()
    if entity == "aliases":
        old_place = UUID(before["item"]["data"]["place_id"]) if before else data.place_id
        for place_id in {old_place, data.place_id}:
            sync_aliases(db, revision.id, place_id)
        db.flush()
    return row, before, record(db, entity, row).model_dump(mode="json")


def remove_record(db, revision, entity, resource_id):
    row = referenced(db, MODELS[entity], revision.id, resource_id)
    before = record(db, entity, row).model_dump(mode="json")
    if entity == "departments":
        db.execute(
            delete(DepartmentPlace).where(
                DepartmentPlace.dataset_revision_id == revision.id,
                DepartmentPlace.department_id == row.id,
            )
        )
    db.delete(row)
    db.flush()  # Referenced buildings/places fail without implicit cascading.
    if entity == "aliases":
        sync_aliases(db, revision.id, row.place_id)
    return before
