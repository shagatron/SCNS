"""Competing real transactions must not silently overwrite a shared draft."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.cli.dataset import geometry
from app.core.errors import DomainError
from app.models import Campus, Revision
from app.models.admin import Department
from app.schemas.admin import DepartmentWrite
from app.services.admin_catalog import claim_version, get_draft, write_record

pytestmark = pytest.mark.integration


def test_only_one_concurrent_draft_writer_commits(database_engine, bundle):
    engine = database_engine.execution_options(isolation_level="READ COMMITTED")
    campus_id, revision_id = uuid4(), uuid4()
    with Session(engine) as db, db.begin():
        db.add(
            Campus(
                id=campus_id,
                code=f"race-{str(campus_id)[:12]}",
                name="Isolated concurrency test",
                timezone="UTC",
                is_demo=True,
                center=geometry(bundle.campus.center),
                boundary=geometry(bundle.campus.boundary),
            )
        )
        db.flush()
        db.add(Revision(id=revision_id, campus_id=campus_id, version=1, status="draft"))
    barrier = Barrier(2, timeout=10)

    def edit(code):
        try:
            with Session(engine) as db, db.begin():
                revision = get_draft(db, campus_id, revision_id)
                assert revision.edit_version == 1
                barrier.wait()
                claim_version(db, revision, '"1"')
                write_record(
                    db,
                    revision,
                    DepartmentWrite(entity="departments", data={"code": code, "name": code}),
                )
            return "committed"
        except DomainError as error:
            assert error.status == 409
            return "conflict"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(edit, ["writer-a", "writer-b"]))
        assert sorted(results) == ["committed", "conflict"]
        with Session(engine) as db:
            assert db.get(Revision, revision_id).edit_version == 2
            assert (
                len(
                    db.scalars(
                        select(Department).where(Department.dataset_revision_id == revision_id)
                    ).all()
                )
                == 1
            )
    finally:
        with Session(engine) as db, db.begin():
            db.execute(delete(Department).where(Department.dataset_revision_id == revision_id))
            db.execute(delete(Revision).where(Revision.id == revision_id))
            db.execute(delete(Campus).where(Campus.id == campus_id))
