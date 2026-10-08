"""Competing committed operators cannot overwrite overlay versions or duplicate retries."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.models.admin import User
from app.models.closures import Closure, ClosureAction, ClosureOverlay
from app.schemas.closures import ClosureCreate
from app.services import closures
from app.services.catalog import active_release
from app.services.mixed_routes import release_projection
from app.services.publication import campus_lock
from tests.integration.test_publication_concurrency import committed_review as review_fixture

pytestmark = pytest.mark.integration


@pytest.fixture
def owned(database_engine, bundle):
    generator = review_fixture.__wrapped__(database_engine, bundle)
    engine, campus, _, _, _, actor_id, _, _ = next(generator)
    with Session(engine) as db:
        target = closures.targets(release_projection(db, active_release(db, campus)))[0]
        payload = ClosureCreate(
            key=str(uuid4()),
            target_kind=target["kind"],
            target_id=target["id"],
            reason="Synthetic committed concurrency restriction",
            starts_at=datetime.now(UTC),
        )
    try:
        yield engine, campus, actor_id, payload
    finally:
        with Session(engine) as db, db.begin():
            db.execute(text("SET LOCAL session_replication_role='replica'"))
            for model in (ClosureAction, Closure, ClosureOverlay):
                db.execute(delete(model).where(model.campus_id == campus))
        try:
            next(generator)
        except StopIteration:
            pass


def test_only_one_operator_claims_overlay_version(owned):
    engine, campus, actor_id, payload = owned
    barrier = Barrier(2, timeout=15)

    def change(number):
        try:
            with Session(engine) as db, db.begin():
                barrier.wait()
                campus_lock(db, campus)
                closures.mutate(
                    db,
                    campus,
                    db.get(User, actor_id),
                    payload.model_copy(
                        update={
                            "key": str(uuid4()),
                            "reason": f"Synthetic competing incident {number}",
                        }
                    ),
                    '"0"',
                    "closure-race",
                )
            return "committed"
        except DomainError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(change, [1, 2])) == ["committed", "conflict"]
    with Session(engine) as db:
        assert closures.version(db, campus) == 1 and len(closures.records(db, campus)) == 1


def test_ambiguous_create_retries_use_one_audited_incident(owned):
    engine, campus, actor_id, payload = owned
    barrier = Barrier(2, timeout=15)

    def change(_):
        with Session(engine) as db, db.begin():
            barrier.wait()
            campus_lock(db, campus)
            return closures.mutate(
                db, campus, db.get(User, actor_id), payload, '"0"', "closure-retry"
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(change, [1, 2]))
    assert results[0] == results[1]
    with Session(engine) as db:
        assert closures.version(db, campus) == 1 and len(closures.records(db, campus)) == 1
        assert (
            len(db.scalars(select(ClosureAction).where(ClosureAction.campus_id == campus)).all())
            == 1
        )


def test_repeatable_read_snapshot_and_fresh_worker_read_are_coherent(owned):
    engine, campus, actor_id, payload = owned
    with (
        Session(engine.execution_options(isolation_level="REPEATABLE READ")) as reader,
        reader.begin(),
    ):
        assert closures.version(reader, campus) == 0 and closures.records(reader, campus) == []
        with Session(engine) as writer, writer.begin():
            campus_lock(writer, campus)
            closures.mutate(
                writer, campus, writer.get(User, actor_id), payload, '"0"', "fresh-worker"
            )
        assert closures.version(reader, campus) == 0 and closures.records(reader, campus) == []
    with Session(engine) as next_request:
        assert closures.version(next_request, campus) == 1
        assert len(closures.records(next_request, campus)) == 1
