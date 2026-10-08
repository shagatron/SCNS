"""Independent committed transactions for inventory CAS and idempotent creation."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.models.admin import User
from app.models.qr import QRMarker
from app.schemas.qr import MarkerCreate, MarkerInput
from app.services import qr
from app.services.publication import campus_lock
from tests.integration.test_publication_concurrency import committed_review as review_fixture

pytestmark = pytest.mark.integration


@pytest.fixture
def owned(database_engine, bundle):
    generator = review_fixture.__wrapped__(database_engine, bundle)
    value = next(generator)
    engine, campus, _, _, _, actor_id, _, _ = value
    with Session(engine) as db, db.begin():
        actor = db.get(User, actor_id)
        target = qr.listing(db, campus)["targets"][0]
        payload = MarkerCreate(
            label="Synthetic concurrency sign",
            node_kind=target["kind"],
            node_id=target["id"],
            intended_position="Simulated node installation only.",
            key=str(uuid4()),
        )
        campus_lock(db, campus)
        marker = qr.create(db, campus, actor, payload, "qr-owned")
        marker_id = marker["id"]
    try:
        yield engine, campus, actor_id, marker_id, payload
    finally:
        # Owned synthetic fixture only in *_test; application DELETE remains forbidden.
        with Session(engine) as db, db.begin():
            db.execute(text("SET LOCAL session_replication_role='replica'"))
            db.execute(delete(QRMarker).where(QRMarker.campus_id == campus))
        try:
            next(generator)
        except StopIteration:
            pass


def test_only_one_committed_qr_writer_can_claim_marker_version(owned):
    engine, campus, actor_id, marker_id, payload = owned
    barrier = Barrier(2, timeout=15)

    def edit(label):
        try:
            with Session(engine) as db, db.begin():
                barrier.wait()
                campus_lock(db, campus)
                obj = qr.row(db, campus, marker_id, '"1"')
                qr.edit(
                    db,
                    obj,
                    db.get(User, actor_id),
                    MarkerInput(**{**payload.model_dump(exclude={"key"}), "label": label}),
                    "qr-race",
                )
            return "committed"
        except DomainError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(edit, ["First operator", "Second operator"])) == [
            "committed",
            "conflict",
        ]
    with Session(engine) as db:
        assert db.get(QRMarker, marker_id).version == 2


def test_competing_retries_create_one_marker(owned):
    engine, campus, actor_id, _, payload = owned
    retried = payload.model_copy(update={"key": str(uuid4())})
    barrier = Barrier(2, timeout=15)

    def create(_):
        with Session(engine) as db, db.begin():
            barrier.wait()
            campus_lock(db, campus)
            return qr.create(db, campus, db.get(User, actor_id), retried, "qr-retry")["id"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(create, range(2)))
    assert ids[0] == ids[1]
    with Session(engine) as db:
        assert (
            db.scalar(
                select(func.count()).select_from(QRMarker).where(QRMarker.campus_id == campus)
            )
            == 2
        )
