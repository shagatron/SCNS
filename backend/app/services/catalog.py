import json
import re
import unicodedata
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.models import ActiveRelease, Anchor, Building, Node, Place, Release, Revision
from app.models.floorplans import Floor
from app.models.indoor import Room
from app.models.publication import ReleaseArtifact
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
    from app.services.closures import version as overlay_version

    artifact = session.get(ReleaseArtifact, release.id)
    return ReleaseOut(
        id=release.id,
        campus_id=release.campus_id,
        dataset_revision_id=release.dataset_revision_id,
        checksum=release.checksum,
        published_at=release.published_at,
        version=version,
        closure_overlay_version=overlay_version(session, campus_id),
        publication_order=release.publication_order,
        artifact_checksum=artifact.checksum if artifact else None,
        artifact_url=f"/api/v1/campuses/{campus_id}/artifacts/{release.id}/{artifact.checksum}.json"
        if artifact
        else None,
    )


def public_places(revision: UUID):
    eligible_rooms = (
        select(Room.id)
        .join(
            Floor,
            (Floor.dataset_revision_id == Room.dataset_revision_id) & (Floor.id == Room.floor_id),
        )
        .join(
            Building,
            (Building.dataset_revision_id == Floor.dataset_revision_id)
            & (Building.id == Floor.building_id),
        )
        .where(
            Building.visibility == "public",
            Room.dataset_revision_id == revision,
            Room.visibility == "public",
            Floor.visibility == "public",
        )
    )
    return select(Place).where(
        Place.dataset_revision_id == revision,
        Place.visibility == "public",
        or_(Place.point.is_not(None), Place.id.in_(eligible_rooms)),
    )


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
    rooms = {
        r.id: r
        for r in session.scalars(
            select(Room).where(Room.dataset_revision_id == revision, Room.id.in_(ids))
        )
    }
    floors = {
        f.id: f for f in session.scalars(select(Floor).where(Floor.dataset_revision_id == revision))
    }
    artifact = session.scalar(
        select(ReleaseArtifact)
        .join(Release, Release.id == ReleaseArtifact.release_id)
        .where(Release.dataset_revision_id == revision)
    )
    projected = artifact.content.get("places", {}) if artifact else {}
    return [
        PlaceOut(
            id=p.id,
            campus_id=p.campus_id,
            code=rooms[p.id].code if p.id in rooms else p.code,
            name=p.name,
            kind=p.kind,
            description=p.description,
            aliases=p.aliases,
            building_name=buildings.get(p.building_id),
            point=json.loads(points[p.id]) if points[p.id] else None,
            routable=projected.get(str(p.id), {}).get("routable", False)
            if p.id in rooms
            else p.id in anchored,
            floor_id=rooms[p.id].floor_id if p.id in rooms else None,
            floor_label=floors[rooms[p.id].floor_id].label if p.id in rooms else None,
            frame_id=rooms[p.id].frame_id if p.id in rooms else None,
            room_code=rooms[p.id].code if p.id in rooms else None,
            local_point={"x_px": rooms[p.id].x_px, "y_px": rooms[p.id].y_px}
            if p.id in rooms
            else None,
            navigation_mode=projected.get(str(p.id), {}).get(
                "navigation_mode", "indoor_catalog_only"
            )
            if p.id in rooms
            else "outdoor",
        )
        for p in places
    ]
