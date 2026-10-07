"""Committed worker leases and retention on the isolated test database."""

import hashlib
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.cli import imports as worker
from app.cli.dataset import geometry
from app.core.config import get_settings
from app.models import Campus, Revision
from app.models.admin import AuditEvent, Department, User
from app.models.imports import ImportJob
from app.schemas.imports import ImportOptions
from app.services.admin_auth import HASHER
from app.services.imports import storage_dir

pytestmark = pytest.mark.integration


def test_worker_recovers_stale_lease_bounds_attempts_cancels_and_cleans_orphans(
    database_engine, bundle, tmp_path, monkeypatch
):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    engine = database_engine.execution_options(isolation_level="READ COMMITTED")
    monkeypatch.setattr(worker, "engine", engine)
    campus_id, revision_id, user_id, job_id = uuid4(), uuid4(), uuid4(), uuid4()
    code = "lease-" + str(campus_id)[:8]
    metadata = {
        "schema_version": "import-v1",
        "campus_code": code,
        "timezone": "UTC",
        "units": "WGS84_degrees_and_metres",
    }
    raw = json.dumps(
        {
            **metadata,
            "records": [
                {
                    "entity": "departments",
                    "external_id": "worker-dept",
                    "data": {"code": "WORKER_D", "name": "Synthetic worker candidate"},
                }
            ],
        }
    ).encode()
    options = ImportOptions(
        **metadata,
        format="json",
        source_rights="Synthetic test only",
        provenance="Isolated worker test",
    ).model_dump(mode="json")
    key = job_id.hex + ".upload"
    folder = storage_dir()
    source = folder / key
    with os.fdopen(os.open(source, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(raw)
    with Session(engine) as db, db.begin():
        db.add(
            Campus(
                id=campus_id,
                code=code,
                name="Synthetic worker test",
                timezone="UTC",
                is_demo=True,
                center=geometry(bundle.campus.center),
                boundary=geometry(bundle.campus.boundary),
            )
        )
        db.add(
            User(
                id=user_id,
                username="worker-" + str(user_id),
                display_name="Worker test",
                password_hash=HASHER.hash(secrets.token_urlsafe(32)),
            )
        )
        db.flush()
        db.add(Revision(id=revision_id, campus_id=campus_id, version=1, status="draft"))
        db.flush()
        db.add(
            ImportJob(
                id=job_id,
                campus_id=campus_id,
                revision_id=revision_id,
                uploader_id=user_id,
                submission_key=str(job_id),
                checksum=hashlib.sha256(raw).hexdigest(),
                storage_key=key,
                filename="synthetic.json",
                byte_size=len(raw),
                options=options,
                state="parsing",
                attempts=1,
                history=[],
                updated_at=datetime.now(UTC) - timedelta(seconds=200),
            )
        )
    try:
        assert worker.once()
        with Session(engine) as db, db.begin():
            job = db.get(ImportJob, job_id)
            assert job.state == "preview_ready" and job.attempts == 2
            assert job.preview["counts"]["add"] == 1
            assert (
                db.scalar(
                    select(Department.id).where(Department.dataset_revision_id == revision_id)
                )
                is None
            )
            job.state = "parsing"
            job.attempts = 3
            job.updated_at = datetime.now(UTC) - timedelta(seconds=200)
        assert worker.once()
        with Session(engine) as db, db.begin():
            job = db.get(ImportJob, job_id)
            assert job.state == "failed" and job.attempts == 3 and "exhausted" in job.failure
            job.state = "cancelled"
            job.updated_at = datetime.now(UTC) - timedelta(days=31)
        assert not worker.once()
        orphan = folder / (uuid4().hex + ".upload")
        orphan.write_bytes(b"orphan")
        old = (datetime.now(UTC) - timedelta(days=31)).timestamp()
        os.utime(orphan, (old, old))
        fresh = folder / (uuid4().hex + ".upload")
        fresh.write_bytes(b"fresh orphan")
        worker.cleanup(30)
        assert not source.exists() and not orphan.exists() and fresh.exists()
        with Session(engine) as db:
            job = db.get(ImportJob, job_id)
            assert job.state == "cancelled" and job.preview["counts"]["add"] == 1 and job.history
    finally:
        with Session(engine) as db, db.begin():
            db.execute(text("SET LOCAL session_replication_role = 'replica'"))
            db.execute(delete(AuditEvent).where(AuditEvent.campus_id == campus_id))
            db.execute(delete(ImportJob).where(ImportJob.campus_id == campus_id))
            db.execute(delete(Revision).where(Revision.id == revision_id))
            db.execute(delete(Campus).where(Campus.id == campus_id))
            db.execute(delete(User).where(User.id == user_id))
        get_settings.cache_clear()
