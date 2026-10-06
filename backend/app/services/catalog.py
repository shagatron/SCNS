import json
import re
import unicodedata
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.models import ActiveRelease, Anchor, Building, Node, Place, Release, Revision
from app.schemas.api import PlaceOut, ReleaseOut


def normalize(value: str) -> str:
    return re.sub(r"[^\w]+", " ", unicodedata.normalize("NFKC", value).casefold()).strip()


def geo(session: Session, column, model, revision: UUID) -> dict:
    return {
        row[0]: json.loads(row[1])
        for row in session.execute(
            select(model.id, func.ST_AsGeoJSON(column)).where(model.dataset_revision_id == revision)
        )
    }


def active_release(session: Session, campus_id: UUID) -> ReleaseOut:
    row = session.execute(
        select(Release, Revision.version)
        .join(ActiveRelease, ActiveRelease.release_id == Release.id)
        .join(Revision, Revision.id == Release.dataset_revision_id)
        .where(
            ActiveRelease.campus_id == campus_id,
            ActiveRelease.audience == "public",
            Revision.status == "frozen",
        )
    ).first()
    if row is None:
        raise DomainError("location_not_found", "No published campus data is available.", 404)
    release, version = row
    return ReleaseOut(
        id=release.id,
        campus_id=release.campus_id,
        dataset_revision_id=release.dataset_revision_id,
        checksum=release.checksum,
        published_at=release.published_at,
        version=version,
    )


def public_places(revision: UUID):
    return select(Place).where(Place.dataset_revision_id == revision, Place.visibility == "public")


def place_output(session: Session, places: list[Place], revision: UUID) -> list[PlaceOut]:
    if not places:
        return []
    ids = [p.id for p in places]
    points = dict(
        session.execute(
            select(Place.id, func.ST_AsGeoJSON(Place.point)).where(
                Place.dataset_revision_id == revision, Place.id.in_(ids)
            )
        ).all()
    )
    buildings = dict(
        session.execute(
            select(Building.id, Building.name).where(
                Building.dataset_revision_id == revision, Building.visibility == "public"
            )
        ).all()
    )
    anchored = set(
        session.scalars(
            select(Anchor.place_id)
            .join(
                Node,
                (Node.id == Anchor.node_id)
                & (Node.dataset_revision_id == Anchor.dataset_revision_id),
            )
            .where(
                Anchor.dataset_revision_id == revision,
                Anchor.place_id.in_(ids),
                Anchor.is_open,
                Node.visibility == "public",
            )
        )
    )
    return [
        PlaceOut(
            id=p.id,
            campus_id=p.campus_id,
            code=p.code,
            name=p.name,
            kind=p.kind,
            description=p.description,
            aliases=p.aliases,
            building_name=buildings.get(p.building_id),
            point=json.loads(points[p.id]),
            routable=p.id in anchored,
        )
        for p in places
    ]
