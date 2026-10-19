"""Independent committed transactions: one writer wins; failures preserve all data."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.models import Place, Revision
from app.models.admin import AuditEvent, DepartmentPlace, PlaceAlias, RoleAssignment, User
from app.models.floorplans import Floor, FloorplanJob, MapLayer
from app.models.indoor import IndoorAccess, IndoorEdge, IndoorNode, Room
from app.models.publication import SourceAsset
from app.schemas.floorplans import ApplyInput, CalibrationInput
from app.schemas.indoor import IndoorPatch
from app.services import floorplans, indoor
from app.services.publication import campus_lock, locked_revision
from tests.integration.test_floorplan_worker import owned as owned_fixture
from tests.integration.test_floorplan_worker import upload
from tests.unit.test_floorplan_contract import measure

pytestmark = pytest.mark.integration


@pytest.fixture
def prepared(database_engine, bundle):
    generator = owned_fixture.__wrapped__(database_engine, bundle)
    owned = next(generator)
    reviewer = uuid4()
    try:
        job_id = UUID(upload(owned))
        assert floorplans.once(owned.engine)
        with Session(owned.engine) as db, db.begin():
            db.add(
                User(
                    id=reviewer,
                    username="indoor-reviewer-" + reviewer.hex,
                    display_name="Synthetic reviewer",
                    password_hash="No login service-only fixture",
                )
            )
            db.flush()
            db.add(
                RoleAssignment(user_id=reviewer, campus_id=owned.campus, role="reviewer_publisher")
            )
            db.add(RoleAssignment(user_id=owned.actor.id, campus_id=owned.campus, role="editor"))
            db.flush()
            campus_lock(db, owned.campus)
            rev = locked_revision(db, owned.campus, owned.revision, '"1"')
            job = db.get(FloorplanJob, job_id)
            floorplans.apply_job(db, rev, job, ApplyInput(), owned.actor, "indoor-fixture")
            floor = db.get(Floor, (owned.revision, owned.floor))
            layer = db.get(MapLayer, (rev.id, floor.layer_id))
            source = db.get(SourceAsset, (rev.id, layer.source_id))
            source.approved_by = reviewer
            source.approved_at = datetime.now(UTC)
            db.flush()
            floorplans.calibrate(
                db,
                rev,
                floor,
                CalibrationInput.model_validate(measure()),
                owned.actor,
                "calibrate-fixture",
            )
            floorplans.approve_calibration(
                db, rev, floor, SimpleNamespace(id=reviewer), "review-fixture"
            )
            owned.version = rev.edit_version
            owned.layer = layer.id
        yield owned
    finally:
        with Session(owned.engine) as db, db.begin():
            db.execute(text("SET LOCAL session_replication_role=replica"))
            for model in (
                IndoorAccess,
                IndoorEdge,
                IndoorNode,
                Room,
                PlaceAlias,
                DepartmentPlace,
                Place,
            ):
                db.execute(delete(model).where(model.campus_id == owned.campus))
            db.execute(delete(RoleAssignment).where(RoleAssignment.campus_id == owned.campus))
            db.execute(delete(User).where(User.id == reviewer))
        try:
            next(generator)
        except StopIteration:
            pass


def payload(owned, label):
    data = json.loads(
        (Path(__file__).resolve().parents[3] / "data/demo/indoor/synthetic-ground.json").read_text()
    )["records"]
    next(iter(data["rooms"].values()))["name"] = label
    return IndoorPatch.model_validate(
        {
            "layer_id": str(owned.layer),
            "changes": [
                {"entity": e, "id": id, "data": item}
                for e, items in data.items()
                for id, item in items.items()
            ],
        }
    )


def test_actual_concurrent_floor_edits_have_one_winner_and_no_duplicates(prepared):
    barrier = Barrier(2)

    def write(label):
        try:
            with Session(prepared.engine) as db, db.begin():
                barrier.wait(timeout=10)
                campus_lock(db, prepared.campus)
                rev = locked_revision(
                    db, prepared.campus, prepared.revision, f'"{prepared.version}"'
                )
                floor = db.get(Floor, (rev.id, prepared.floor))
                indoor.apply_patch(db, rev, floor, payload(prepared, label), prepared.actor, label)
            return "saved"
        except DomainError as e:
            return e.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ["first writer", "second writer"]))
    assert sorted(results) == ["conflict", "saved"]
    with Session(prepared.engine) as db:
        assert db.get(Revision, prepared.revision).edit_version == prepared.version + 1
        assert (
            db.scalar(
                select(func.count()).select_from(Room).where(Room.campus_id == prepared.campus)
            )
            == 3
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.campus_id == prepared.campus, AuditEvent.action == "indoor.patch")
            )
            == 1
        )


def test_failure_after_graph_mutation_rolls_back_version_catalog_geometry_audit(
    prepared, monkeypatch
):
    def fail(*args, **kwargs):
        raise RuntimeError("simulated append-only audit persistence failure")

    monkeypatch.setattr(indoor, "audit", fail)
    with pytest.raises(RuntimeError), Session(prepared.engine) as db, db.begin():
        campus_lock(db, prepared.campus)
        rev = locked_revision(db, prepared.campus, prepared.revision, f'"{prepared.version}"')
        floor = db.get(Floor, (rev.id, prepared.floor))
        indoor.apply_patch(
            db, rev, floor, payload(prepared, "must roll back"), prepared.actor, "failure"
        )
    with Session(prepared.engine) as db:
        assert db.get(Revision, prepared.revision).edit_version == prepared.version
        for model in (Room, IndoorNode, IndoorEdge, IndoorAccess, Place):
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.campus_id == prepared.campus)
                )
                == 0
            )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.campus_id == prepared.campus, AuditEvent.action == "indoor.patch")
            )
            == 0
        )
