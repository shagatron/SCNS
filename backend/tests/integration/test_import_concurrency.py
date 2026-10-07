"""Actual competing import transactions, not sequential HTTP requests."""

import secrets
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.cli.dataset import geometry
from app.core.errors import DomainError
from app.models import Campus, Revision
from app.models.admin import AuditEvent, Department, User
from app.models.imports import ImportBinding, ImportJob
from app.services.admin_auth import HASHER
from app.services.imports import apply_job

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("same_job", [False, True])
def test_concurrent_apply_is_atomic_and_replays_once(database_engine, bundle, same_job):
    engine = database_engine.execution_options(isolation_level="READ COMMITTED")
    campus_id, revision_id, user_id = uuid4(), uuid4(), uuid4()
    jobs = [uuid4(), uuid4()]
    with Session(engine) as db, db.begin():
        db.add(
            Campus(
                id=campus_id,
                code="import-race-" + str(campus_id)[:8],
                name="Synthetic race",
                timezone="UTC",
                is_demo=True,
                center=geometry(bundle.campus.center),
                boundary=geometry(bundle.campus.boundary),
            )
        )
        db.add(
            User(
                id=user_id,
                username="race-" + str(user_id),
                display_name="Isolated import race",
                password_hash=HASHER.hash(secrets.token_urlsafe(32)),
            )
        )
        db.flush()
        db.add(Revision(id=revision_id, campus_id=campus_id, version=1, status="draft"))
        db.flush()
        for index, identity in enumerate(jobs):
            record_id = uuid4()
            data = {
                "code": f"RACE_{index}",
                "name": f"Race {index}",
                "description": "",
                "place_ids": [],
            }
            db.add(
                ImportJob(
                    id=identity,
                    campus_id=campus_id,
                    revision_id=revision_id,
                    uploader_id=user_id,
                    submission_key=str(identity),
                    checksum="0" * 64,
                    storage_key=identity.hex + ".upload",
                    filename="synthetic.json",
                    byte_size=1,
                    options={},
                    state="validated",
                    attempts=1,
                    preview_version=1,
                    preview={
                        "counts": {"add": 1},
                        "rows": [
                            {
                                "row": 1,
                                "entity": "departments",
                                "external_id": f"race-{index}",
                                "id": str(record_id),
                                "action": "add",
                                "errors": [],
                                "data": data,
                                "before": None,
                                "after": data,
                            }
                        ],
                    },
                    history=[],
                )
            )
    barrier = Barrier(2, timeout=10)

    def apply(identity):
        try:
            with Session(engine) as db, db.begin():
                barrier.wait()
                job = db.scalar(select(ImportJob).where(ImportJob.id == identity).with_for_update())
                apply_job(db, job, user_id, "concurrent-import-test", '"1"')
            return "committed"
        except DomainError as exc:
            assert exc.status == 409
            return "conflict"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(apply, [jobs[0], jobs[0] if same_job else jobs[1]]))
        assert sorted(result) == (
            ["committed", "committed"] if same_job else ["committed", "conflict"]
        )
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
            events = db.scalars(
                select(AuditEvent).where(
                    AuditEvent.campus_id == campus_id, AuditEvent.action == "import.apply"
                )
            ).all()
            assert len(events) == 1
    finally:
        # Fixture enforces *_test. The local test DB owner is privileged; bypass the
        # immutable-audit trigger only to remove THIS isolated race's temporary rows.
        with Session(engine) as db, db.begin():
            db.execute(text("SET LOCAL session_replication_role = 'replica'"))
            db.execute(delete(AuditEvent).where(AuditEvent.campus_id == campus_id))
            db.execute(delete(ImportBinding).where(ImportBinding.campus_id == campus_id))
            db.execute(delete(Department).where(Department.campus_id == campus_id))
            db.execute(delete(ImportJob).where(ImportJob.campus_id == campus_id))
            db.execute(delete(Revision).where(Revision.id == revision_id))
            db.execute(delete(Campus).where(Campus.id == campus_id))
            db.execute(delete(User).where(User.id == user_id))
