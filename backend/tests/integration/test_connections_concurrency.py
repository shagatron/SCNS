"""Real committed connection CAS and audit rollback; only owned disposable records."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.models import Revision
from app.models.connections import FloorRouting
from app.schemas.connections import ConnectionsPatch
from app.services import connections
from app.services.publication import campus_lock, locked_revision
from tests.integration.test_indoor_concurrency import prepared as prepared_fixture

pytestmark = pytest.mark.integration


@pytest.fixture
def owned(database_engine, bundle):
    generator = prepared_fixture.__wrapped__(database_engine, bundle)
    context = next(generator)
    try:
        yield context
    finally:
        with Session(context.engine) as db, db.begin():
            db.execute(delete(FloorRouting).where(FloorRouting.campus_id == context.campus))
        try:
            next(generator)
        except StopIteration:
            pass


def payload(owned, mode="metric"):
    return ConnectionsPatch.model_validate(
        {
            "changes": [
                {
                    "entity": "policies",
                    "id": str(owned.floor),
                    "data": {
                        "floor_id": str(owned.floor),
                        "layer_id": str(owned.layer),
                        "enabled": False,
                        "mode": mode,
                    },
                }
            ]
        }
    )


def test_committed_connection_writers_share_global_version(owned):
    with Session(owned.engine) as db:
        before = db.get(Revision, owned.revision).edit_version
    barrier = Barrier(2)

    def write(mode):
        try:
            with Session(owned.engine) as db, db.begin():
                barrier.wait(timeout=15)
                campus_lock(db, owned.campus)
                revision = locked_revision(db, owned.campus, owned.revision, f'"{before}"')
                connections.apply_patch(
                    db, revision, payload(owned, mode), owned.actor, "connection-race"
                )
            return "committed"
        except DomainError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ("metric", "directions_only")))
    assert sorted(results) == ["committed", "conflict"]
    with Session(owned.engine) as db:
        assert db.get(Revision, owned.revision).edit_version == before + 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(FloorRouting)
                .where(FloorRouting.campus_id == owned.campus)
            )
            == 1
        )


def test_committed_connection_audit_failure_rolls_back(owned, monkeypatch):
    with Session(owned.engine) as db:
        before = db.get(Revision, owned.revision).edit_version

    def fail(*args, **kwargs):
        raise RuntimeError("Injected post-write audit failure")

    monkeypatch.setattr(connections, "audit", fail)
    with pytest.raises(RuntimeError, match="Injected"):
        with Session(owned.engine) as db, db.begin():
            campus_lock(db, owned.campus)
            revision = locked_revision(db, owned.campus, owned.revision, f'"{before}"')
            connections.apply_patch(
                db, revision, payload(owned), owned.actor, "connection-rollback"
            )
    with Session(owned.engine) as db:
        assert db.get(Revision, owned.revision).edit_version == before
        assert (
            db.scalar(
                select(func.count())
                .select_from(FloorRouting)
                .where(FloorRouting.campus_id == owned.campus)
            )
            == 0
        )
