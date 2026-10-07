"""Review and release actions are separate from editable catalog APIs."""

from uuid import UUID

from fastapi import APIRouter, Request, Response
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.api.v1.admin import DB, Version
from app.core.errors import DomainError
from app.models import ActiveRelease, Release, Revision
from app.models.publication import ReleaseArtifact, ReviewSubmission, SourceAsset
from app.schemas.publication import (
    DecisionInput,
    PublishInput,
    RollbackInput,
    SourceInput,
    SubmitInput,
    ValidateInput,
)
from app.services import publication as service
from app.services.admin_auth import audit, authorize
from app.services.imports import strict_json

router = APIRouter(prefix="/api/v1/admin/campuses/{campus_id}", tags=["admin-publication"])


def submission(db, revision, identity):
    obj = db.scalar(
        select(ReviewSubmission).where(
            ReviewSubmission.id == identity,
            ReviewSubmission.revision_id == revision.id,
            ReviewSubmission.campus_id == revision.campus_id,
        )
    )
    if obj is None:
        raise DomainError("location_not_found", "Submission not found in this revision.", 404)
    return obj


@router.get("/drafts/{revision_id}/review")
def review(campus_id: UUID, revision_id: UUID, request: Request, db: DB):
    authorize(db, request, campus_id, "draft_read")
    return service.packet(db, service.locked_revision(db, campus_id, revision_id, read=True))


@router.post(
    "/drafts/{revision_id}/sources",
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": SourceInput.model_json_schema()}},
        }
    },
)
async def register_source(
    campus_id: UUID, revision_id: UUID, request: Request, db: DB, if_match: Version = None
):
    await run_in_threadpool(authorize, db, request, campus_id, "catalog_edit")
    # Bound before decoding, unlike generic JSON request binding. Originals stay private BYTEA.
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > 5 * 1024 * 1024:
            raise DomainError("upload_too_large", "Source registration exceeds 5MiB.", 413)
        raw.extend(chunk)
    try:
        payload = SourceInput.model_validate(strict_json(raw.decode("utf-8")))
    except (ValueError, UnicodeError, RecursionError):
        raise DomainError(
            "invalid_input",
            "Use the documented publication source JSON/GeoJSON registration template.",
        ) from None

    def save():
        service.campus_lock(db, campus_id)
        current_actor = authorize(db, request, campus_id, "catalog_edit")
        revision = service.locked_revision(db, campus_id, revision_id, if_match)
        return service.add_source(db, revision, payload, current_actor, request.state.request_id)

    return await run_in_threadpool(save)


@router.delete("/drafts/{revision_id}/sources/{source_id}")
def remove_source(
    campus_id: UUID,
    revision_id: UUID,
    source_id: UUID,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    actor = authorize(db, request, campus_id, "catalog_edit")
    revision = service.locked_revision(db, campus_id, revision_id, if_match)
    source = db.get(SourceAsset, (revision.id, source_id))
    if not source or revision.status != "draft":
        raise DomainError("conflict", "Source must belong to an editable draft.", 409)
    db.delete(source)
    revision.edit_version += 1
    revision.checksum = None
    audit(
        db,
        "source.remove",
        request.state.request_id,
        actor_id=actor.id,
        campus_id=campus_id,
        revision_id=revision.id,
        resource_id=source_id,
        before={"title": source.title},
    )
    return {"edit_version": revision.edit_version}


@router.get("/drafts/{revision_id}/sources/{source_id}/original")
def original(campus_id: UUID, revision_id: UUID, source_id: UUID, request: Request, db: DB):
    authorize(db, request, campus_id, "draft_read")
    revision = service.locked_revision(db, campus_id, revision_id, read=True)
    source = db.get(SourceAsset, (revision.id, source_id))
    if not source or source.original is None:
        raise DomainError("location_not_found", "Private original not found.", 404)
    return Response(
        source.original,
        media_type=source.media_type or "application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{source.original_filename or "private-original.json"}"'
        },
    )


@router.post("/drafts/{revision_id}/sources/{source_id}/approve")
def approve_source(
    campus_id: UUID,
    revision_id: UUID,
    source_id: UUID,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    actor = authorize(db, request, campus_id, "source_approve")
    revision = service.locked_revision(db, campus_id, revision_id, if_match)
    source = db.get(SourceAsset, (revision.id, source_id))
    if not source or revision.status != "draft":
        raise DomainError("conflict", "Source approval requires an editable draft.", 409)
    if source.uploader_id == actor.id:
        raise DomainError(
            "separation_of_duties",
            "The source uploader cannot approve its own rights/derivative.",
            403,
        )
    if source.approved_by:
        raise DomainError("conflict", "Source is already approved.", 409)
    source.approved_by = actor.id
    revision.edit_version += 1
    revision.checksum = None
    audit(
        db,
        "source.approve",
        request.state.request_id,
        actor_id=actor.id,
        campus_id=campus_id,
        revision_id=revision.id,
        resource_id=source.id,
        after={
            "rights": source.rights,
            "derivative_checksum": service.checksum(source.derivative)
            if source.derivative
            else None,
        },
    )
    return {"edit_version": revision.edit_version}


@router.post("/drafts/{revision_id}/validations")
def validate(
    campus_id: UUID,
    revision_id: UUID,
    payload: ValidateInput,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    actor = authorize(db, request, campus_id, "review_submit")
    revision = service.locked_revision(db, campus_id, revision_id, if_match)
    run = service.validate(db, revision, payload, actor, request.state.request_id)
    return {
        "id": str(run.id),
        "edit_version": run.edit_version,
        "checksum": run.checksum,
        "report": run.report,
        "evidence": run.evidence,
    }


@router.post("/drafts/{revision_id}/submissions")
def submit(
    campus_id: UUID,
    revision_id: UUID,
    payload: SubmitInput,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    actor = authorize(db, request, campus_id, "review_submit")
    revision = service.locked_revision(db, campus_id, revision_id, if_match)
    obj = service.submit(db, revision, payload, actor, request.state.request_id)
    return {"id": str(obj.id), "status": obj.status, "edit_version": revision.edit_version}


@router.post("/drafts/{revision_id}/submissions/{submission_id}/decision")
def decide(
    campus_id: UUID,
    revision_id: UUID,
    submission_id: UUID,
    payload: DecisionInput,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    actor = authorize(
        db,
        request,
        campus_id,
        "review_submit" if payload.decision == "withdraw" else "review_decide",
    )
    revision = service.locked_revision(db, campus_id, revision_id, if_match)
    obj = submission(db, revision, submission_id)
    if payload.decision == "withdraw" and actor.id != obj.submitter_id:
        raise DomainError("access_denied", "Only the submitter can withdraw its review.", 403)
    service.decision(db, revision, obj, payload, actor, request.state.request_id)
    return {"status": obj.status, "edit_version": revision.edit_version}


@router.post("/drafts/{revision_id}/publish")
def publish(
    campus_id: UUID,
    revision_id: UUID,
    payload: PublishInput,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    actor = authorize(db, request, campus_id, "release_publish")
    service.campus_lock(db, campus_id)
    actor = authorize(db, request, campus_id, "release_publish")
    prior = service.action_retry(db, campus_id, actor, payload)
    if prior is not None:
        if prior.get("revision_id") != str(revision_id):
            raise DomainError("conflict", "Retry belongs to another revision.", 409)
        return prior
    revision = service.locked_revision(db, campus_id, revision_id, if_match)
    return service.publish(
        db,
        revision,
        submission(db, revision, payload.submission_id),
        payload,
        actor,
        request.state.request_id,
    )


@router.get("/releases")
def history(campus_id: UUID, request: Request, db: DB):
    authorize(db, request, campus_id, "draft_read")
    active = db.get(ActiveRelease, (campus_id, "public"))
    return {
        "active_release_id": str(active.release_id) if active else None,
        "releases": [
            {
                "id": str(r.id),
                "revision_id": str(r.dataset_revision_id),
                "version": version,
                "publication_order": r.publication_order,
                "checksum": r.checksum,
                "published_at": r.published_at,
                "artifact_checksum": a.checksum if a else None,
                "legacy_demo": a is None,
                "publisher_id": str(a.publisher_id) if a else None,
            }
            for r, version, a in db.execute(
                select(Release, Revision.version, ReleaseArtifact)
                .join(Revision, Revision.id == Release.dataset_revision_id)
                .outerjoin(ReleaseArtifact, ReleaseArtifact.release_id == Release.id)
                .where(Release.campus_id == campus_id)
                .order_by(Release.publication_order.desc())
                .limit(100)
            )
        ],
        "limit": 100,
        "closure_overlay_version": 0,
    }


@router.post("/rollback")
def rollback(campus_id: UUID, payload: RollbackInput, request: Request, db: DB):
    actor = authorize(db, request, campus_id, "release_publish")
    service.campus_lock(db, campus_id)
    actor = authorize(db, request, campus_id, "release_publish")
    prior = service.action_retry(db, campus_id, actor, payload)
    return (
        prior
        if prior is not None
        else service.rollback(db, campus_id, payload, actor, request.state.request_id)
    )
