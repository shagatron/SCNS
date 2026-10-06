import argparse
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from geoalchemy2 import Geography
from pydantic import ValidationError
from sqlalchemy import cast, func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import engine
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
from app.schemas.dataset import Dataset
from app.services.catalog import normalize


def read_bundle(path: Path) -> Dataset:
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("Bundle exceeds the 10 MiB limit")
    return Dataset.model_validate_json(path.read_text())


def geometry(value):
    return func.ST_SetSRID(func.ST_GeomFromGeoJSON(value.model_dump_json()), 4326)


def seed_bundle(session: Session, bundle: Dataset) -> Release:
    """Explicit local demo import only. Never replaces an existing frozen revision."""
    if not get_settings().demo_enabled or not bundle.campus.is_demo or bundle.campus.code != "DEMO":
        raise ValueError(
            "Seeding requires DEMO_ENABLED=true and an explicitly labelled DEMO campus"
        )
    if bundle.campus.name != "Demo Campus":
        raise ValueError("Synthetic data must keep the Demo Campus name")
    checksum = hashlib.sha256(bundle.model_dump_json().encode()).hexdigest()
    # Serialize demo seeds for the same campus so repeated setup is safe.
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": str(bundle.campus.id)}
    )
    existing = session.scalar(
        select(Release)
        .join(Revision, Revision.id == Release.dataset_revision_id)
        .where(Revision.campus_id == bundle.campus.id, Revision.checksum == checksum)
    )
    if existing:
        return existing
    campus = session.get(Campus, bundle.campus.id)
    if campus and not campus.is_demo:
        raise ValueError("Cannot seed over a real campus")
    if not campus:
        data = bundle.campus.model_dump(exclude={"center", "boundary"})
        session.add(
            Campus(
                **data,
                center=geometry(bundle.campus.center),
                boundary=geometry(bundle.campus.boundary),
            )
        )
        session.flush()
    active = session.get(ActiveRelease, (bundle.campus.id, "public"))
    previous = session.get(Release, active.release_id) if active else None
    version = (
        session.scalar(
            select(func.max(Revision.version)).where(Revision.campus_id == bundle.campus.id)
        )
        or 0
    ) + 1
    revision = Revision(
        id=uuid4(),
        campus_id=bundle.campus.id,
        version=version,
        checksum=checksum,
        status="draft",
        parent_id=previous.dataset_revision_id if previous else None,
    )
    session.add(revision)
    session.flush()
    scope = {"campus_id": bundle.campus.id, "dataset_revision_id": revision.id}
    for f in bundle.frames:
        session.add(Frame(**scope, **f.model_dump()))
    for b in bundle.buildings:
        session.add(
            Building(
                **scope, **b.model_dump(exclude={"footprint"}), footprint=geometry(b.footprint)
            )
        )
    session.flush()
    for p in bundle.places:
        session.add(
            Place(
                **scope,
                **p.model_dump(exclude={"point"}),
                point=geometry(p.point),
                search_text=normalize(" ".join([p.code, p.name, p.kind, *p.aliases])),
            )
        )
    for n in bundle.nodes:
        session.add(Node(**scope, **n.model_dump(exclude={"point"}), point=geometry(n.point)))
    session.flush()
    for e in bundle.edges:
        shape = geometry(e.geometry)
        session.add(
            Edge(
                **scope,
                **e.model_dump(exclude={"geometry"}),
                geometry=shape,
                distance_m=func.ST_Length(cast(shape, Geography)),
                distance_status="measured",
            )
        )
    for a in bundle.anchors:
        session.add(Anchor(**scope, **a.model_dump()))
    session.flush()
    invalid = session.scalar(
        select(func.count())
        .select_from(Edge)
        .where(Edge.dataset_revision_id == revision.id, ~func.ST_IsValid(Edge.geometry))
    )
    if invalid:
        raise ValueError("Invalid spatial geometry")
    revision.status = "frozen"
    session.flush()
    release = Release(
        id=uuid4(), campus_id=bundle.campus.id, dataset_revision_id=revision.id, checksum=checksum
    )
    session.add(release)
    session.flush()
    if active:
        active.release_id = release.id
    else:
        session.add(
            ActiveRelease(campus_id=bundle.campus.id, audience="public", release_id=release.id)
        )
    session.flush()
    return release


def main():
    parser = argparse.ArgumentParser(
        description="Validate outdoor v1 bundles or explicitly seed local synthetic data."
    )
    parser.add_argument("command", choices=["validate", "seed-demo", "schema"])
    parser.add_argument("path", type=Path, nargs="?")
    args = parser.parse_args()
    try:
        if args.command == "schema":
            print(json.dumps(Dataset.model_json_schema(), indent=2))
            return
        if args.path is None:
            parser.error("A dataset JSON path is required")
        bundle = read_bundle(args.path)
        if args.command == "validate":
            print(
                f"Valid outdoor v1 bundle: {len(bundle.places)} places, {len(bundle.nodes)} nodes, {len(bundle.edges)} directed edges. No data imported."
            )
        else:
            with Session(engine) as session, session.begin():
                release = seed_bundle(session, bundle)
                print(f"Demo release {release.id}; checksum {release.checksum}")
    except (ValueError, ValidationError) as exc:
        parser.exit(2, f"Dataset validation failed: {exc}\n")


if __name__ == "__main__":
    main()
