"""Competing committed transactions, not shared-session concurrency simulations."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from geoalchemy2 import Geography
from sqlalchemy import cast, delete, func, select, text
from sqlalchemy.orm import Session

from app.cli.dataset import geometry
from app.core.errors import DomainError
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
from app.models.admin import (
    AuditEvent,
    Department,
    DepartmentPlace,
    PlaceAlias,
    RoleAssignment,
    User,
)
from app.models.imports import ImportBinding, ImportJob
from app.models.publication import (
    ReleaseAction,
    ReleaseArtifact,
    ReviewDecision,
    ReviewSubmission,
    SourceAsset,
    ValidationRun,
)
from app.schemas.publication import (
    DecisionInput,
    PublishInput,
    RollbackInput,
    RouteExpectation,
    SubmitInput,
    ValidateInput,
)
from app.services import publication as service
from app.services.admin_catalog import claim_version, create_draft
from tests.integration.test_publication import ack

pytestmark = pytest.mark.integration


@pytest.fixture
def committed_review(database_engine, bundle):
    engine = database_engine.execution_options(isolation_level="READ COMMITTED")
    campus, editor_id, reviewer_id, old_revision, old_release = [uuid4() for _ in range(5)]
    gate, lib = [next(p for p in bundle.places if p.code == code) for code in ("GATE", "LIB")]
    frame_id = bundle.frames[0].id
    n1, n2 = uuid4(), uuid4()
    with Session(engine) as db, db.begin():
        db.add(
            Campus(
                id=campus,
                code=f"race-{str(campus)[:12]}",
                name="Isolated synthetic review race",
                timezone="UTC",
                is_demo=True,
                center=geometry(bundle.campus.center),
                boundary=geometry(bundle.campus.boundary),
            )
        )
        for i, name in ((editor_id, "editor"), (reviewer_id, "reviewer")):
            db.add(
                User(
                    id=i,
                    username=f"race-{name}-{str(campus)[:12]}",
                    display_name=name,
                    password_hash="No login permitted for service-only fixture",
                    active=True,
                )
            )
        db.flush()
        db.add_all(
            [
                RoleAssignment(user_id=editor_id, campus_id=campus, role="editor"),
                RoleAssignment(user_id=reviewer_id, campus_id=campus, role="reviewer_publisher"),
            ]
        )
        db.add(
            Revision(
                id=old_revision, campus_id=campus, version=1, status="draft", checksum="1" * 64
            )
        )
        db.flush()
        scope = dict(dataset_revision_id=old_revision, campus_id=campus)
        db.add(Frame(**scope, id=frame_id, code="WGS84", kind="outdoor"))
        for place in (gate, lib):
            db.add(
                Place(
                    **scope,
                    id=place.id,
                    code=place.code,
                    name=place.name,
                    kind=place.kind,
                    description="Synthetic committed fixture",
                    aliases=[],
                    search_text=service.normalize(f"{place.code} {place.name} {place.kind}"),
                    visibility="public",
                    point=geometry(place.point),
                )
            )
        db.flush()
        evidence = f"Synthetic source {date.today()}; no physical verification"
        for identity, place in ((n1, gate), (n2, lib)):
            db.add(
                Node(
                    **scope,
                    id=identity,
                    label=place.name,
                    frame_id=frame_id,
                    point=geometry(place.point),
                    visibility="public",
                    evidence=evidence,
                )
            )
        db.flush()
        physical = uuid4()
        from app.schemas.api import LineString

        for start, end, points in (
            (n1, n2, [gate.point.coordinates, lib.point.coordinates]),
            (n2, n1, [lib.point.coordinates, gate.point.coordinates]),
        ):
            shape = geometry(LineString(coordinates=points))
            db.add(
                Edge(
                    **scope,
                    id=uuid4(),
                    physical_path_id=physical,
                    from_node_id=start,
                    to_node_id=end,
                    frame_id=frame_id,
                    kind="walkway",
                    geometry=shape,
                    distance_m=func.ST_Length(cast(shape, Geography)),
                    distance_status="estimated",
                    accessibility_status="verified_step_free",
                    visibility="public",
                    is_open=True,
                    evidence=evidence,
                )
            )
        for place, node in ((gate, n1), (lib, n2)):
            db.add(
                Anchor(
                    **scope,
                    id=uuid4(),
                    place_id=place.id,
                    node_id=node,
                    accessibility_status="verified_step_free",
                    accessibility_evidence=evidence,
                    is_open=True,
                )
            )
        db.add(
            SourceAsset(
                **scope,
                id=uuid4(),
                title="Synthetic generated fixture",
                rights="synthetic",
                provenance="Generated software test fixture; no survey",
                attribution="Synthetic software fixture",
                uploader_id=editor_id,
                approved_by=reviewer_id,
            )
        )
        db.flush()
        db.get(Revision, old_revision).status = "frozen"
        db.flush()
        db.add(
            Release(
                id=old_release,
                campus_id=campus,
                dataset_revision_id=old_revision,
                checksum="1" * 64,
            )
        )
        db.flush()
        db.add(ActiveRelease(campus_id=campus, audience="public", release_id=old_release))
        db.flush()
        draft = create_draft(db, campus, editor_id, "race-setup")
        revision = db.get(Revision, draft.id)
        expected = ValidateInput.model_validate(
            {
                "routes": [
                    {
                        "source": str(gate.id),
                        "target": str(lib.id),
                        "profile": p,
                        "expected_found": True,
                        "reason": "Synthetic direct stored-path acceptance expectation",
                    }
                    for p in ("shortest", "step_free")
                ]
            }
        )
        run = service.validate(db, revision, expected, db.get(User, editor_id), "race-setup")
        assert run.report["errors"] == 0
        reasons = ack({"report": run.report})
        submitted = service.submit(
            db,
            revision,
            SubmitInput(validation_id=run.id, acknowledgements=reasons),
            db.get(User, editor_id),
            "race-setup",
        )
        service.decision(
            db,
            revision,
            submitted,
            DecisionInput(
                decision="approve",
                notes="Independent synthetic exact-content acceptance",
                acknowledgements=reasons,
            ),
            db.get(User, reviewer_id),
            "race-setup",
        )
        revision_id, submission_id, version = revision.id, submitted.id, revision.edit_version
    try:
        yield (
            engine,
            campus,
            revision_id,
            submission_id,
            version,
            editor_id,
            reviewer_id,
            old_release,
        )
    finally:
        with Session(engine) as db, db.begin():
            # Only unique fixture campus, in disposable *_test DB; no application bypass.
            db.execute(text("SET LOCAL session_replication_role='replica'"))
            submissions = select(ReviewSubmission.id).where(ReviewSubmission.campus_id == campus)
            db.execute(delete(ReviewDecision).where(ReviewDecision.submission_id.in_(submissions)))
            for model in (
                AuditEvent,
                ReleaseAction,
                ReleaseArtifact,
                ReviewSubmission,
                ValidationRun,
                ActiveRelease,
                Release,
                SourceAsset,
                ImportJob,
                ImportBinding,
                DepartmentPlace,
                PlaceAlias,
                Department,
                Anchor,
                Edge,
                Node,
                Place,
                Building,
                Frame,
                Revision,
                RoleAssignment,
            ):
                db.execute(delete(model).where(model.campus_id == campus))
            db.execute(delete(Campus).where(Campus.id == campus))
            db.execute(delete(User).where(User.id.in_([editor_id, reviewer_id])))


@pytest.mark.parametrize("mode", ["duplicate", "competing", "edit"])
def test_committed_publication_races(committed_review, mode):
    engine, campus, revision_id, submission_id, version, editor, reviewer, old_release = (
        committed_review
    )
    barrier = Barrier(2, timeout=15)

    def worker(index):
        try:
            with Session(engine) as db, db.begin():
                barrier.wait()
                if mode == "edit" and index == 1:
                    revision = db.get(Revision, revision_id)
                    claim_version(db, revision, f'"{version}"')
                    return "edit"
                service.campus_lock(db, campus)
                user = db.get(User, reviewer)
                payload = PublishInput(
                    submission_id=submission_id,
                    expected_release_id=old_release,
                    key="race-publish-key" if mode == "duplicate" else f"race-publish-{index}",
                )
                retry = service.action_retry(db, campus, user, payload)
                if retry:
                    return "retry"
                revision = service.locked_revision(db, campus, revision_id, f'"{version}"')
                service.publish(
                    db,
                    revision,
                    db.get(ReviewSubmission, submission_id),
                    payload,
                    user,
                    "race-publish",
                )
            return "published"
        except DomainError as error:
            assert error.status == 409
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(pool.map(worker, [0, 1]))
    assert results == (["published", "retry"] if mode == "duplicate" else ["conflict", "published"])
    with Session(engine) as db:
        assert db.get(Revision, revision_id).status == "frozen"
        assert (
            db.scalar(
                select(func.count())
                .select_from(ReleaseArtifact)
                .where(ReleaseArtifact.campus_id == campus)
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.campus_id == campus, AuditEvent.action == "release.publish")
            )
            == 1
        )


def test_committed_rollback_race_and_failed_write(committed_review):
    engine, campus, revision_id, sid, version, editor, reviewer, old_release = committed_review
    with Session(engine) as db, db.begin():
        revision = service.locked_revision(db, campus, revision_id, f'"{version}"')
        user = db.get(User, reviewer)
        result = service.publish(
            db,
            revision,
            db.get(ReviewSubmission, sid),
            PublishInput(
                submission_id=sid, expected_release_id=old_release, key="publish-before-rollback"
            ),
            user,
            "race-setup",
        )
    barrier = Barrier(2, timeout=15)

    def roll(index):
        try:
            with Session(engine) as db, db.begin():
                barrier.wait()
                service.campus_lock(db, campus)
                service.rollback(
                    db,
                    campus,
                    RollbackInput(
                        target_release_id=old_release,
                        expected_release_id=result["release_id"],
                        key=f"competing-rollback-{index}",
                        reason="Explicit earlier synthetic release restoration",
                    ),
                    db.get(User, reviewer),
                    "race-rollback",
                )
            return "rolled"
        except DomainError as error:
            assert error.status == 409
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(roll, [0, 1])) == ["conflict", "rolled"]
    with Session(engine) as db:
        assert db.get(ActiveRelease, (campus, "public")).release_id == old_release
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.campus_id == campus, AuditEvent.action == "release.rollback")
            )
            == 1
        )


def test_committed_submit_edit_race_invalidates_prior_approval(committed_review):
    engine, campus, rid, sid, version, editor, reviewer, old = committed_review
    with Session(engine) as db, db.begin():
        revision = service.locked_revision(db, campus, rid, f'"{version}"')
        service.decision(
            db,
            revision,
            db.get(ReviewSubmission, sid),
            DecisionInput(
                decision="withdraw", notes="Return approved fixture to draft for a competing edit"
            ),
            db.get(User, editor),
            "race-return",
        )
        run = db.get(ValidationRun, db.get(ReviewSubmission, sid).validation_id)
        route_fields = set(RouteExpectation.model_fields)
        payload = ValidateInput.model_validate(
            {"routes": [{k: v for k, v in e.items() if k in route_fields} for e in run.evidence]}
        )
        fresh = service.validate(db, revision, payload, db.get(User, editor), "race-revalidate")
        version, run_id, reasons = revision.edit_version, fresh.id, ack({"report": fresh.report})
    barrier = Barrier(2, timeout=15)

    def compete(index):
        try:
            with Session(engine) as db, db.begin():
                barrier.wait()
                if index == 0:
                    revision = service.locked_revision(db, campus, rid, f'"{version}"')
                    service.submit(
                        db,
                        revision,
                        SubmitInput(validation_id=run_id, acknowledgements=reasons),
                        db.get(User, editor),
                        "race-submit",
                    )
                    result = "submitted"
                else:
                    revision = db.get(Revision, rid)
                    claim_version(db, revision, f'"{version}"')
                    node = db.scalar(select(Node).where(Node.dataset_revision_id == rid))
                    node.label = "Synthetic concurrent edited node"
                    service.audit(
                        db,
                        "graph.node.update",
                        "race-edit",
                        actor_id=editor,
                        campus_id=campus,
                        revision_id=rid,
                        resource_id=node.id,
                        after={"label": node.label},
                    )
                    result = "edited"
            return result
        except DomainError as error:
            assert error.status == 409
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(pool.map(compete, [0, 1]))
    assert results in (["conflict", "submitted"], ["conflict", "edited"])
    with Session(engine) as db:
        revision = db.get(Revision, rid)
        assert revision.edit_version == version + 1 and revision.status in {"draft", "review"}
        assert db.get(ReviewSubmission, sid).status == "withdrawn"
        assert db.get(ActiveRelease, (campus, "public")).release_id == old


def test_committed_publish_rollback_compete_for_same_active_pointer(committed_review):
    engine, campus, rid, sid, version, editor, reviewer, old = committed_review
    with Session(engine) as db, db.begin():
        revision = service.locked_revision(db, campus, rid, f'"{version}"')
        current = service.publish(
            db,
            revision,
            db.get(ReviewSubmission, sid),
            PublishInput(
                submission_id=sid, expected_release_id=old, key="initial-publish-cross-race"
            ),
            db.get(User, reviewer),
            "cross-race",
        )
        newer = create_draft(db, campus, editor, "cross-race")
        revision = db.get(Revision, newer.id)
        prior = db.get(ValidationRun, db.get(ReviewSubmission, sid).validation_id)
        payload = ValidateInput.model_validate(
            {
                "routes": [
                    {k: v for k, v in e.items() if k in RouteExpectation.model_fields}
                    for e in prior.evidence
                ]
            }
        )
        run = service.validate(db, revision, payload, db.get(User, editor), "cross-race")
        reasons = ack({"report": run.report})
        submitted = service.submit(
            db,
            revision,
            SubmitInput(validation_id=run.id, acknowledgements=reasons),
            db.get(User, editor),
            "cross-race",
        )
        service.decision(
            db,
            revision,
            submitted,
            DecisionInput(
                decision="approve",
                notes="Independent second fixture review before active-pointer race",
                acknowledgements=reasons,
            ),
            db.get(User, reviewer),
            "cross-race",
        )
        new_rid, new_sid, new_version = revision.id, submitted.id, revision.edit_version
    barrier = Barrier(2, timeout=15)

    def compete(index):
        try:
            with Session(engine) as db, db.begin():
                barrier.wait()
                service.campus_lock(db, campus)
                if index == 0:
                    revision = service.locked_revision(db, campus, new_rid, f'"{new_version}"')
                    service.publish(
                        db,
                        revision,
                        db.get(ReviewSubmission, new_sid),
                        PublishInput(
                            submission_id=new_sid,
                            expected_release_id=current["release_id"],
                            key="cross-race-publish",
                        ),
                        db.get(User, reviewer),
                        "cross-race",
                    )
                    result = "published"
                else:
                    service.rollback(
                        db,
                        campus,
                        RollbackInput(
                            target_release_id=old,
                            expected_release_id=current["release_id"],
                            key="cross-race-rollback",
                            reason="Return to earlier immutable synthetic fixture",
                        ),
                        db.get(User, reviewer),
                        "cross-race",
                    )
                    result = "rolled"
            return result
        except DomainError as error:
            assert error.status == 409
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(pool.map(compete, [0, 1]))
    assert results in (["conflict", "published"], ["conflict", "rolled"])
    with Session(engine) as db:
        revision = db.get(Revision, new_rid)
        assert revision.status == ("frozen" if "published" in results else "review")
        assert db.get(ActiveRelease, (campus, "public")).release_id != UUID(current["release_id"])


def test_rollback_orders_publications_not_draft_creation_versions(committed_review):
    engine, campus, older_draft, old_sid, old_version, editor, reviewer, old_release = (
        committed_review
    )
    with Session(engine) as db, db.begin():
        later_draft = create_draft(db, campus, editor, "out-of-order-fixture")
        revision = db.get(Revision, later_draft.id)
        prior = db.get(ValidationRun, db.get(ReviewSubmission, old_sid).validation_id)
        payload = ValidateInput.model_validate(
            {
                "routes": [
                    {k: v for k, v in e.items() if k in RouteExpectation.model_fields}
                    for e in prior.evidence
                ]
            }
        )
        run = service.validate(db, revision, payload, db.get(User, editor), "out-of-order-fixture")
        reasons = ack({"report": run.report})
        submitted = service.submit(
            db,
            revision,
            SubmitInput(validation_id=run.id, acknowledgements=reasons),
            db.get(User, editor),
            "out-of-order-fixture",
        )
        service.decision(
            db,
            revision,
            submitted,
            DecisionInput(
                decision="approve",
                notes="Independent review of later-created synthetic draft",
                acknowledgements=reasons,
            ),
            db.get(User, reviewer),
            "out-of-order-fixture",
        )
        first = service.publish(
            db,
            revision,
            submitted,
            PublishInput(
                submission_id=submitted.id,
                expected_release_id=old_release,
                key="publish-later-draft-first",
            ),
            db.get(User, reviewer),
            "out-of-order-fixture",
        )
        earlier = db.get(Revision, older_draft)
        second = service.publish(
            db,
            earlier,
            db.get(ReviewSubmission, old_sid),
            PublishInput(
                submission_id=old_sid,
                expected_release_id=first["release_id"],
                key="publish-earlier-draft-later",
            ),
            db.get(User, reviewer),
            "out-of-order-fixture",
        )
        assert earlier.version < revision.version
        assert (
            db.get(Release, second["release_id"]).publication_order
            > db.get(Release, first["release_id"]).publication_order
        )
        restored = service.rollback(
            db,
            campus,
            RollbackInput(
                target_release_id=first["release_id"],
                expected_release_id=second["release_id"],
                key="rollback-publication-order",
                reason="Earlier publication remains eligible despite higher draft version",
            ),
            db.get(User, reviewer),
            "out-of-order-fixture",
        )
        assert restored["release_id"] == first["release_id"]
