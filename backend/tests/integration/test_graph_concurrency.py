"""Independent committed graph transactions compete against the draft-wide CAS."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.cli.dataset import geometry
from app.core.errors import DomainError
from app.models import Campus, Frame, Node, Revision
from app.models.admin import AuditEvent
from app.schemas.graph import GraphPatch
from app.services.admin_catalog import claim_version, get_draft
from app.services.admin_graph import apply_patch

pytestmark = pytest.mark.integration


def test_graph_writers_commit_once_and_retry_requires_latest_version(database_engine, bundle):
    engine = database_engine.execution_options(isolation_level="READ COMMITTED")
    campus_id, revision_id, frame_id = (uuid4(), uuid4(), uuid4())
    with Session(engine) as db, db.begin():
        db.add(
            Campus(
                id=campus_id,
                code=f"graph-{str(campus_id)[:12]}",
                name="Isolated graph race",
                timezone="UTC",
                is_demo=True,
                center=geometry(bundle.campus.center),
                boundary=geometry(bundle.campus.boundary),
            )
        )
        db.flush()
        db.add(Revision(id=revision_id, campus_id=campus_id, version=1, status="draft"))
        db.flush()
        db.add(
            Frame(
                id=frame_id,
                campus_id=campus_id,
                dataset_revision_id=revision_id,
                code="WGS84",
                kind="outdoor",
            )
        )
    barrier = Barrier(2, timeout=10)

    def edit(label):
        try:
            with Session(engine) as db, db.begin():
                revision = get_draft(db, campus_id, revision_id)
                barrier.wait()
                claim_version(db, revision, '"1"')
                patch = GraphPatch.model_validate(
                    {
                        "changes": [
                            {
                                "entity": "nodes",
                                "id": str(uuid4()),
                                "data": {
                                    "frame_id": str(frame_id),
                                    "label": label,
                                    "point": {"type": "Point", "coordinates": [0.001, 0.001]},
                                },
                            }
                        ]
                    }
                )
                apply_patch(db, revision, patch, None, "graph-race")
            return "committed"
        except DomainError as error:
            assert error.status == 409
            return "conflict"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(edit, ["writer-a", "writer-b"])) == ["committed", "conflict"]
        with Session(engine) as db:
            assert db.get(Revision, revision_id).edit_version == 2
            assert (
                len(db.scalars(select(Node).where(Node.dataset_revision_id == revision_id)).all())
                == 1
            )
            assert (
                len(
                    db.scalars(
                        select(AuditEvent).where(AuditEvent.revision_id == revision_id)
                    ).all()
                )
                == 1
            )
    finally:
        with Session(engine) as db, db.begin():
            db.execute(text("SET LOCAL session_replication_role='replica'"))
            db.execute(delete(AuditEvent).where(AuditEvent.revision_id == revision_id))
            db.execute(text("SET LOCAL session_replication_role='origin'"))
            db.execute(delete(Node).where(Node.dataset_revision_id == revision_id))
            db.execute(delete(Frame).where(Frame.dataset_revision_id == revision_id))
            db.execute(delete(Revision).where(Revision.id == revision_id))
            db.execute(delete(Campus).where(Campus.id == campus_id))
