"""Synthetic fixture campuses isolate browser publication from navigation regressions."""

from uuid import UUID, uuid4, uuid5

from sqlalchemy import select

from app.models import (
    ActiveRelease,
    Anchor,
    Building,
    Campus,
    Edge,
    Frame,
    Node,
    Place,
    Release,
    Revision,
)
from app.models.admin import Department, DepartmentPlace, PlaceAlias
from app.services.publication import checksum, snapshot


def create_fixture(db, parent, bundle, viewport, purpose="publication"):
    campus_id, revision_id = uuid4(), uuid4()
    db.add(
        Campus(
            id=campus_id,
            code=f"{'PUB' if purpose == 'publication' else purpose.upper().replace(' ', '_')}_{viewport}",
            name=f"Synthetic {purpose} fixture {viewport}",
            timezone=bundle.campus.timezone,
            is_demo=True,
            center=db.get(Campus, bundle.campus.id).center,
            boundary=db.get(Campus, bundle.campus.id).boundary,
        )
    )
    db.flush()
    revision = Revision(id=revision_id, campus_id=campus_id, version=1, status="draft")
    db.add(revision)
    db.flush()
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
    ):
        for row in db.scalars(select(model).where(model.dataset_revision_id == parent)):
            values = {}
            for col in model.__table__.columns:
                value = getattr(row, col.name)
                if col.name == "campus_id":
                    value = campus_id
                elif col.name == "dataset_revision_id":
                    value = revision_id
                elif isinstance(value, UUID):
                    value = uuid5(campus_id, str(value))
                values[col.name] = value
            db.add(model(**values))
        db.flush()
    revision.checksum = checksum(snapshot(db, revision))
    revision.status = "frozen"
    db.flush()
    release = Release(
        id=uuid4(), campus_id=campus_id, dataset_revision_id=revision_id, checksum=revision.checksum
    )
    db.add(release)
    db.flush()
    db.add(ActiveRelease(campus_id=campus_id, audience="public", release_id=release.id))
    return campus_id
