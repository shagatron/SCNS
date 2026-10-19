"""Separate committed transactions, owned synthetic campus, durable leases and CAS."""

import hashlib
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Lock
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.cli.dataset import geometry
from app.core.errors import DomainError
from app.models import Building, Campus, Frame, Revision
from app.models.admin import AuditEvent, User
from app.models.floorplans import Floor, FloorplanJob, MapLayer
from app.models.publication import SourceAsset
from app.schemas.floorplans import ApplyInput, FloorInput, UploadInput
from app.services import floorplans as service
from app.services.admin_auth import HASHER
from app.services.publication import campus_lock, locked_revision

pytestmark = pytest.mark.integration
RAW = (
    Path(__file__).resolve().parents[3] / "data/demo/floorplans/synthetic-ground.png"
).read_bytes()


@pytest.fixture
def owned(database_engine, bundle):
    engine = database_engine.execution_options(isolation_level="READ COMMITTED")
    campus, revision, user, building, floor = (uuid4() for _ in range(5))
    actor = SimpleNamespace(id=user)
    with Session(engine) as db, db.begin():
        db.add(
            Campus(
                id=campus,
                code="floor-worker-" + campus.hex[:8],
                name="Synthetic floor worker only",
                timezone="UTC",
                is_demo=True,
                center=geometry(bundle.campus.center),
                boundary=geometry(bundle.campus.boundary),
            )
        )
        db.add(
            User(
                id=user,
                username="floor-worker-" + user.hex,
                display_name="Temporary test user",
                password_hash=HASHER.hash(secrets.token_urlsafe(24)),
            )
        )
        db.flush()
        db.add(Revision(id=revision, campus_id=campus, version=1, status="draft"))
        db.flush()
        db.add(
            Building(
                id=building,
                dataset_revision_id=revision,
                campus_id=campus,
                code="SYN",
                name="Synthetic building",
                footprint=geometry(bundle.buildings[0].footprint),
                visibility="public",
            )
        )
        db.flush()
        db.add(
            Floor(
                id=floor,
                dataset_revision_id=revision,
                campus_id=campus,
                building_id=building,
                code="G",
                label="Synthetic ground",
                ordering=0,
                elevation_m=None,
                visibility="public",
            )
        )
        db.flush()
    values = SimpleNamespace(
        engine=engine, campus=campus, revision=revision, actor=actor, building=building, floor=floor
    )
    try:
        yield values
    finally:
        # Only this fixture's owned synthetic records; database_engine suffix guard is mandatory.
        with Session(engine) as db, db.begin():
            db.execute(text("SET LOCAL session_replication_role = 'replica'"))
            for model in (
                AuditEvent,
                FloorplanJob,
                MapLayer,
                Floor,
                SourceAsset,
                Frame,
                Building,
                Revision,
                Campus,
            ):
                if model is Campus:
                    condition = Campus.id == campus
                else:
                    condition = model.campus_id == campus
                db.execute(delete(model).where(condition))
            db.execute(delete(User).where(User.id == user))


def upload(owned, raw=RAW, key=None):
    opts = UploadInput(
        floor_id=owned.floor,
        key=key or str(uuid4()),
        filename="synthetic-ground.png" if raw == RAW else "malformed.pdf",
        title="Synthetic test",
        rights="synthetic",
        provenance="Invented test bytes only",
        attribution="Synthetic demonstration",
        redactions=[],
    )
    with Session(owned.engine) as db, db.begin():
        campus_lock(db, owned.campus)
        revision = locked_revision(db, owned.campus, owned.revision, '"1"')
        return service.upload(db, revision, opts, raw, owned.actor, "test-upload")["id"]


def test_stale_worker_recovery_attempt_budget_and_original_immutability(owned):
    identity = upload(owned)
    with Session(owned.engine) as db, db.begin():
        job = db.get(FloorplanJob, identity)
        job.state = "processing"
        job.attempts = 1
        job.updated_at = datetime.now(UTC) - timedelta(seconds=130)
        job.lease = uuid4()
    assert service.once(owned.engine)
    with Session(owned.engine) as db, db.begin():
        job = db.get(FloorplanJob, identity)
        assert job.state == "ready" and job.attempts == 2 and job.original == RAW
        assert hashlib.sha256(job.original).hexdigest() == job.original_checksum
        assert (
            db.get(Revision, owned.revision).edit_version == 1
            and db.get(Floor, (owned.revision, owned.floor)).layer_id is None
        )
        job.state = "processing"
        job.attempts = 3
        job.updated_at = datetime.now(UTC) - timedelta(seconds=130)
    assert service.once(owned.engine)
    with Session(owned.engine) as db:
        job = db.get(FloorplanJob, identity)
        assert job.state == "failed" and job.attempts == 3 and "exhausted" in job.failure
    assert not service.once(owned.engine)


def test_invalid_file_failure_and_cancelled_late_result_never_apply(owned, monkeypatch):
    bad = upload(owned, b"%PDF-broken")
    assert service.once(owned.engine)
    with Session(owned.engine) as db:
        assert db.get(FloorplanJob, bad).state == "failed"
    identity = upload(owned)
    decode = service.decode

    def cancel_after_decode(raw, opts):
        result = decode(raw, opts)
        with Session(owned.engine) as db, db.begin():
            job = db.get(FloorplanJob, identity)
            job.state = "cancelled"
            job.lease = None
        return result

    monkeypatch.setattr(service, "decode", cancel_after_decode)
    assert service.once(owned.engine)
    with Session(owned.engine) as db:
        job = db.get(FloorplanJob, identity)
        assert job.state == "cancelled" and job.png is None
        assert (
            db.scalar(
                select(func.count()).select_from(MapLayer).where(MapLayer.campus_id == owned.campus)
            )
            == 0
        )


def test_concurrent_workers_claim_one_job_without_duplicate_results(owned, monkeypatch):
    identity = upload(owned)
    decode = service.decode
    calls = []
    lock = Lock()
    barrier = Barrier(2)

    def counted(raw, options):
        with lock:
            calls.append(1)
        return decode(raw, options)

    monkeypatch.setattr(service, "decode", counted)

    def run():
        barrier.wait()
        return service.once(owned.engine)

    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(run) for _ in range(2)]
        results = [f.result(timeout=40) for f in futures]
    assert sorted(results) == [False, True] and len(calls) == 1
    with Session(owned.engine) as db:
        job = db.get(FloorplanJob, identity)
        assert job.state == "ready" and job.attempts == 1


def test_storage_failure_retains_private_original_and_consistent_job(owned, monkeypatch):
    identity = upload(owned)
    monkeypatch.setattr(service, "STORAGE_LIMIT", len(RAW))
    assert service.once(owned.engine)
    with Session(owned.engine) as db:
        job = db.get(FloorplanJob, identity)
        assert (
            job.state == "failed"
            and job.png is None
            and job.original == RAW
            and "storage" in job.failure
        )
        assert db.get(Revision, owned.revision).edit_version == 1


def test_real_competing_floor_edits_and_late_audit_rollback(owned, monkeypatch):
    barrier = Barrier(2)

    def writer(label):
        try:
            with Session(owned.engine) as db, db.begin():
                barrier.wait()
                campus_lock(db, owned.campus)
                revision = locked_revision(db, owned.campus, owned.revision, '"1"')
                payload = FloorInput(
                    building_id=owned.building,
                    code="G",
                    label=label,
                    ordering=0,
                    visibility="public",
                )
                service.save_floor(
                    db, revision, payload, owned.actor, "competing-edit", owned.floor
                )
            return 200
        except DomainError as exc:
            return exc.status

    with ThreadPoolExecutor(2) as pool:
        futures = [
            pool.submit(writer, label) for label in ("Synthetic winner A", "Synthetic winner B")
        ]
        assert sorted(f.result(timeout=20) for f in futures) == [200, 409]
    with Session(owned.engine) as db:
        before = db.get(Floor, (owned.revision, owned.floor)).label
        assert db.get(Revision, owned.revision).edit_version == 2

    def fail(*args, **kwargs):
        raise DomainError("injected", "Injected audit rollback", 422)

    monkeypatch.setattr(service, "audit", fail)
    with pytest.raises(DomainError), Session(owned.engine) as db, db.begin():
        revision = locked_revision(db, owned.campus, owned.revision, '"2"')
        service.save_floor(
            db,
            revision,
            FloorInput(building_id=owned.building, code="G", label="Must rollback", ordering=0),
            owned.actor,
            "injected",
            owned.floor,
        )
    with Session(owned.engine) as db:
        assert (
            db.get(Floor, (owned.revision, owned.floor)).label == before
            and db.get(Revision, owned.revision).edit_version == 2
        )


def test_competing_apply_one_layer_and_same_key_upload_idempotency(owned):
    barrier = Barrier(2)
    key = str(uuid4())

    def submit():
        barrier.wait()
        return upload(owned, key=key)

    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(submit) for _ in range(2)]
        identities = [f.result(timeout=20) for f in futures]
    assert identities[0] == identities[1]
    first = identities[0]
    second = upload(owned)
    assert service.once(owned.engine)
    assert service.once(owned.engine)
    barrier = Barrier(2)

    def apply(identity):
        try:
            with Session(owned.engine) as db, db.begin():
                barrier.wait()
                campus_lock(db, owned.campus)
                revision = locked_revision(db, owned.campus, owned.revision, '"1"')
                job = service.job_row(db, revision, identity, lock=True)
                service.apply_job(db, revision, job, ApplyInput(), owned.actor, "competing-apply")
            return 200
        except DomainError as exc:
            return exc.status

    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(apply, identity) for identity in (first, second)]
        assert sorted(f.result(timeout=20) for f in futures) == [200, 409]
    with Session(owned.engine) as db:
        assert (
            db.scalar(
                select(func.count()).select_from(MapLayer).where(MapLayer.campus_id == owned.campus)
            )
            == 1
        )
        assert sorted(
            db.scalars(select(FloorplanJob.state).where(FloorplanJob.campus_id == owned.campus))
        ) == ["applied", "ready"]
        assert db.get(Revision, owned.revision).edit_version == 2
