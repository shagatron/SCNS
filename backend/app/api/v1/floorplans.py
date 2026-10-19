"""Campus-authorized private floor management and staged binary plans."""

from typing import Annotated, Literal
from urllib.parse import unquote
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, Response
from sqlalchemy import func, select
from starlette.concurrency import run_in_threadpool

from app.api.v1.admin import DB, Version
from app.core.errors import DomainError
from app.models.floorplans import Floor, FloorplanJob, MapLayer
from app.schemas.floorplans import (
    ApplyInput,
    CalibrationInput,
    DeleteFloor,
    FloorInput,
    PageInput,
    UploadInput,
)
from app.services import floorplans as service
from app.services.admin_auth import authorize
from app.services.imports import strict_json
from app.services.publication import campus_lock, locked_revision

router = APIRouter(
    prefix="/api/v1/admin/campuses/{campus_id}/drafts/{revision_id}", tags=["admin-floorplans"]
)


def write(db, request, campus, revision, header):
    campus_lock(db, campus)
    actor = authorize(db, request, campus, "catalog_edit")
    draft = locked_revision(db, campus, revision, header)
    service.editable(draft)
    return actor, draft


def read(db, request, campus, revision):
    authorize(db, request, campus, "draft_read")
    return locked_revision(db, campus, revision, read=True)


@router.get("/floors")
def floors(campus_id: UUID, revision_id: UUID, request: Request, db: DB):
    return service.listing(db, read(db, request, campus_id, revision_id))


@router.post("/floors", status_code=201)
def create_floor(
    campus_id: UUID,
    revision_id: UUID,
    payload: FloorInput,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    actor, revision = write(db, request, campus_id, revision_id, if_match)
    return service.save_floor(db, revision, payload, actor, request.state.request_id)


@router.put("/floors/{floor_id}")
def update_floor(
    campus_id: UUID,
    revision_id: UUID,
    floor_id: UUID,
    payload: FloorInput,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    actor, revision = write(db, request, campus_id, revision_id, if_match)
    return service.save_floor(db, revision, payload, actor, request.state.request_id, floor_id)


@router.delete("/floors/{floor_id}")
def remove_floor(
    campus_id: UUID,
    revision_id: UUID,
    floor_id: UUID,
    payload: DeleteFloor,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    actor, revision = write(db, request, campus_id, revision_id, if_match)
    return service.delete_floor(db, revision, floor_id, payload, actor, request.state.request_id)


@router.post("/floors/{floor_id}/calibration")
def calibrate(
    campus_id: UUID,
    revision_id: UUID,
    floor_id: UUID,
    payload: CalibrationInput,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    actor, revision = write(db, request, campus_id, revision_id, if_match)
    return service.calibrate(
        db,
        revision,
        service.row(db, Floor, revision, floor_id),
        payload,
        actor,
        request.state.request_id,
    )


@router.get("/floorplan-jobs")
def jobs(
    campus_id: UUID,
    revision_id: UUID,
    request: Request,
    db: DB,
    offset: int = Query(0, ge=0, le=10000),
):
    revision = read(db, request, campus_id, revision_id)
    query = select(FloorplanJob).where(
        FloorplanJob.revision_id == revision.id, FloorplanJob.campus_id == campus_id
    )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    return {
        "items": [
            service.job_output(j)
            for j in db.scalars(
                query.order_by(FloorplanJob.created_at.desc(), FloorplanJob.id)
                .limit(50)
                .offset(offset)
            )
        ],
        "total": total,
        "offset": offset,
    }


@router.post(
    "/floorplan-jobs",
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            },
        }
    },
)
async def upload(
    campus_id: UUID,
    revision_id: UUID,
    request: Request,
    db: DB,
    metadata: Annotated[str, Header(alias="X-Floorplan-Metadata")],
    if_match: Version = None,
):
    await run_in_threadpool(authorize, db, request, campus_id, "catalog_edit")
    if (
        len(metadata) > 24000
        or request.headers.get("content-type", "").split(";")[0] != "application/octet-stream"
    ):
        raise DomainError(
            "invalid_input",
            "Send private binary content with bounded X-Floorplan-Metadata from the documented template.",
        )
    try:
        options = UploadInput.model_validate(strict_json(unquote(metadata, errors="strict")))
    except (ValueError, UnicodeError, RecursionError):
        raise DomainError(
            "invalid_input",
            "Check floorplan rights/provenance, filename, page, redactions and upload key.",
        ) from None
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > service.BYTE_LIMIT:
            raise DomainError(
                "upload_too_large", "Floorplan exceeds the 10MiB private upload limit.", 413
            )
        raw.extend(chunk)

    def save():
        actor, revision = write(db, request, campus_id, revision_id, if_match)
        return service.upload(db, revision, options, bytes(raw), actor, request.state.request_id)

    return await run_in_threadpool(save)


@router.get("/floorplan-jobs/{job_id}")
def job(campus_id: UUID, revision_id: UUID, job_id: UUID, request: Request, db: DB):
    return service.job_output(
        service.job_row(db, read(db, request, campus_id, revision_id), job_id)
    )


@router.get("/floorplan-jobs/{job_id}/{asset}", response_class=Response)
def job_asset(
    campus_id: UUID,
    revision_id: UUID,
    job_id: UUID,
    asset: Literal["original", "preview"],
    request: Request,
    db: DB,
):
    job = service.job_row(db, read(db, request, campus_id, revision_id), job_id)
    if asset == "original":
        return Response(
            job.original,
            media_type=job.media_type,
            headers={"Content-Disposition": f'attachment; filename="{job.filename}"'},
        )
    if job.png is None or job.state not in {"ready", "applied"}:
        raise DomainError("location_not_found", "No ready sanitized preview.", 404)
    return Response(job.png, media_type="image/png")


@router.post("/floorplan-jobs/{job_id}/control/{command}")
def control(
    campus_id: UUID,
    revision_id: UUID,
    job_id: UUID,
    command: Literal["retry", "cancel"],
    request: Request,
    db: DB,
    if_match: Version = None,
):
    actor, revision = write(db, request, campus_id, revision_id, if_match)
    return service.control(
        db,
        revision,
        service.job_row(db, revision, job_id, lock=True),
        command,
        actor,
        request.state.request_id,
    )


@router.post("/floorplan-jobs/{job_id}/apply")
def apply(
    campus_id: UUID,
    revision_id: UUID,
    job_id: UUID,
    payload: ApplyInput,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    actor, revision = write(db, request, campus_id, revision_id, if_match)
    return service.apply_job(
        db,
        revision,
        service.job_row(db, revision, job_id, lock=True),
        payload,
        actor,
        request.state.request_id,
    )


@router.get("/floorplan-layers/{layer_id}/preview", response_class=Response)
def layer_preview(campus_id: UUID, revision_id: UUID, layer_id: UUID, request: Request, db: DB):
    revision = read(db, request, campus_id, revision_id)
    layer = service.row(db, MapLayer, revision, layer_id)
    return Response(layer.png, media_type="image/png", headers={"ETag": f'"{layer.checksum}"'})


@router.post("/floors/{floor_id}/calibration/approve")
def approve_calibration(
    campus_id: UUID,
    revision_id: UUID,
    floor_id: UUID,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    campus_lock(db, campus_id)
    actor = authorize(db, request, campus_id, "source_approve")
    revision = locked_revision(db, campus_id, revision_id, if_match)
    return service.approve_calibration(
        db, revision, service.row(db, Floor, revision, floor_id), actor, request.state.request_id
    )


@router.post("/floorplan-jobs/{job_id}/pages", status_code=201)
def another_page(
    campus_id: UUID,
    revision_id: UUID,
    job_id: UUID,
    payload: PageInput,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    actor, revision = write(db, request, campus_id, revision_id, if_match)
    job = service.job_row(db, revision, job_id)
    options = UploadInput.model_validate({**job.options, **payload.model_dump(mode="json")})
    return service.upload(db, revision, options, job.original, actor, request.state.request_id)
