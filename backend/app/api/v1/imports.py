import base64
import binascii
import hashlib
import os
import re
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import DomainError
from app.db.session import get_admin_session
from app.models import Campus, Revision
from app.models.imports import ImportJob
from app.schemas.imports import ImportOptions
from app.services.admin_auth import authorize
from app.services.admin_catalog import get_draft
from app.services.imports import apply_job, error_csv, log, storage_dir, strict_json, transition

router = APIRouter(prefix="/api/v1/admin/campuses/{campus_id}", tags=["admin imports"])
DB = Annotated[Session, Depends(get_admin_session, scope="function")]


def output(job, offset=0, limit=100):
    preview = job.preview
    return {
        "id": str(job.id),
        "campus_id": str(job.campus_id),
        "revision_id": str(job.revision_id),
        "uploader_id": str(job.uploader_id),
        "applier_id": str(job.applier_id) if job.applier_id else None,
        "filename": job.filename,
        "byte_size": job.byte_size,
        "checksum": job.checksum,
        "options": job.options,
        "state": job.state,
        "attempts": job.attempts,
        "preview_version": job.preview_version,
        "failure": job.failure,
        "counts": preview["counts"] if preview else None,
        "rows": preview["rows"][offset : offset + limit] if preview else [],
        "total_rows": len(preview["rows"]) if preview else 0,
        "offset": offset,
        "history": job.history,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def get_job(db, campus, identity):
    job = db.scalar(
        select(ImportJob)
        .where(ImportJob.id == identity, ImportJob.campus_id == campus)
        .with_for_update()
    )
    if not job:
        raise DomainError("location_not_found", "Import job not found in this campus.", 404)
    return job


@router.post("/drafts/{revision_id}/imports", status_code=201)
async def upload(
    campus_id: UUID,
    revision_id: UUID,
    request: Request,
    db: DB,
    filename: Annotated[str, Query(min_length=1, max_length=160)],
    options: Annotated[str, Header(alias="X-Import-Options", max_length=14000)],
    submission_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=80)],
):
    actor = authorize(db, request, campus_id, "import_write")
    get_draft(db, campus_id, revision_id)
    try:
        decoded_options = base64.b64decode(options, validate=True).decode("utf-8")
        if len(decoded_options) > 10000:
            raise ValueError("Metadata limit exceeded")
        parsed = ImportOptions.model_validate(strict_json(decoded_options))
    except (ValueError, UnicodeError, binascii.Error, RecursionError):
        raise DomainError(
            "invalid_input",
            "Invalid import options. Use the documented import-v1 metadata and mapping.",
        ) from None
    campus = db.get(Campus, campus_id)
    if parsed.campus_code != campus.code or parsed.timezone != campus.timezone:
        raise DomainError(
            "invalid_input", "Campus code/timezone must match the destination campus."
        )
    if (
        not re.fullmatch(r"[A-Za-z0-9_. -]{1,160}", filename)
        or filename.startswith(".")
        or not filename.lower().endswith("." + parsed.format)
    ):
        raise DomainError(
            "invalid_input",
            "Use a plain filename with the selected .csv, .json or .geojson extension.",
        )
    if request.headers.get("content-type", "").split(";")[0] != "application/octet-stream":
        raise DomainError("invalid_input", "Send the file as application/octet-stream.")
    limit = get_settings().import_byte_limit
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > limit:
            raise DomainError(
                "upload_too_large", f"File exceeds the {limit} byte upload limit.", 413
            )
        raw.extend(chunk)
    try:
        decoded = bytes(raw).decode("utf-8-sig")
        if not decoded.strip() or "\x00" in decoded:
            raise ValueError("Empty/binary text")
        if parsed.format != "csv":
            strict_json(decoded)
    except (ValueError, UnicodeError, RecursionError):
        raise DomainError(
            "invalid_input",
            "File must be non-empty UTF-8 text with valid JSON for JSON/GeoJSON uploads.",
        ) from None
    checksum = hashlib.sha256(raw).hexdigest()
    # Serialize quota and idempotency checks across API workers before allocating private storage.
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": "scns-private-import-storage"}
    )
    existing = db.scalar(
        select(ImportJob).where(
            ImportJob.campus_id == campus_id,
            ImportJob.uploader_id == actor.id,
            ImportJob.submission_key == submission_key,
        )
    )
    if existing:
        if (
            existing.checksum != checksum
            or existing.options != parsed.model_dump(mode="json")
            or existing.revision_id != revision_id
        ):
            raise DomainError(
                "conflict", "Idempotency key was already used for a different submission.", 409
            )
        return output(existing)
    folder = storage_dir()
    if (
        sum(p.stat().st_size for p in folder.glob("*.upload")) + len(raw)
        > get_settings().import_storage_limit
    ):
        raise DomainError(
            "storage_limit",
            "Private import storage is full. Ask operations to run the documented retention cleanup.",
            413,
        )
    key = uuid4().hex + ".upload"
    path = folder / key
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as file:
            from app.core.portable import private_mode

            private_mode(file, path)
            file.write(raw)
        job = ImportJob(
            id=uuid4(),
            campus_id=campus_id,
            revision_id=revision_id,
            uploader_id=actor.id,
            submission_key=submission_key,
            checksum=checksum,
            storage_key=key,
            filename=filename,
            byte_size=len(raw),
            options=parsed.model_dump(mode="json"),
            history=[],
        )
        transition(job, "uploaded", actor.id)
        db.add(job)
        db.flush()
        log(
            db,
            job,
            "upload",
            actor.id,
            request.state.request_id,
            {
                "filename": filename,
                "byte_size": len(raw),
                "source_rights": parsed.source_rights,
                "provenance": parsed.provenance,
            },
        )
        return output(job)
    except Exception:
        path.unlink(missing_ok=True)
        raise


@router.get("/imports")
def jobs(
    campus_id: UUID,
    request: Request,
    db: DB,
    offset: int = Query(default=0, ge=0, le=10000),
    limit: int = Query(default=25, ge=1, le=100),
):
    authorize(db, request, campus_id, "import_read")
    query = select(ImportJob).where(ImportJob.campus_id == campus_id)
    return {
        "items": [
            output(job, limit=0)
            for job in db.scalars(
                query.order_by(ImportJob.created_at.desc(), ImportJob.id)
                .offset(offset)
                .limit(limit)
            )
        ],
        "total": db.scalar(select(func.count()).select_from(query.subquery())),
        "offset": offset,
    }


@router.get("/imports/{job_id}")
def detail(
    campus_id: UUID,
    job_id: UUID,
    request: Request,
    db: DB,
    offset: int = Query(default=0, ge=0, le=10000),
    limit: int = Query(default=50, ge=1, le=100),
):
    authorize(db, request, campus_id, "import_read")
    # Reads need not acquire an exclusive job lock.
    job = db.scalar(
        select(ImportJob).where(ImportJob.id == job_id, ImportJob.campus_id == campus_id)
    )
    if not job:
        raise DomainError("location_not_found", "Import job not found in this campus.", 404)
    return output(job, offset, limit)


@router.get("/imports/{job_id}/errors.csv")
def errors(campus_id: UUID, job_id: UUID, request: Request, db: DB):
    authorize(db, request, campus_id, "import_read")
    job = get_job(db, campus_id, job_id)
    return Response(
        error_csv(job),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="import-{job.id}-diagnostics.csv"'},
    )


@router.put("/imports/{job_id}/mapping")
def mapping(campus_id: UUID, job_id: UUID, options: ImportOptions, request: Request, db: DB):
    actor = authorize(db, request, campus_id, "import_write")
    job = get_job(db, campus_id, job_id)
    if job.state not in {"preview_ready", "validated", "failed"}:
        raise DomainError("conflict", "Mapping can change only after processing completes.", 409)
    if (
        options.format != job.options["format"]
        or options.campus_code != job.options["campus_code"]
        or options.timezone != job.options["timezone"]
    ):
        raise DomainError(
            "invalid_input", "Mapping cannot change the file format or destination metadata."
        )
    get_draft(db, campus_id, job.revision_id)
    job.options = options.model_dump(mode="json")
    job.preview = None
    job.preview_version = None
    job.attempts = 0
    transition(job, "uploaded", actor.id)
    log(
        db,
        job,
        "mapping",
        actor.id,
        request.state.request_id,
        {"mapping": options.mapping, "policy": options.policy},
    )
    return output(job)


@router.post("/imports/{job_id}/{action}")
def action(
    campus_id: UUID,
    job_id: UUID,
    action: str,
    request: Request,
    db: DB,
    version: Annotated[str | None, Header(alias="If-Match")] = None,
):
    actor = authorize(db, request, campus_id, "import_write")
    job = get_job(db, campus_id, job_id)
    if action == "apply":
        apply_job(db, job, actor.id, request.state.request_id, version)
    elif action == "validate":
        if job.state not in {"preview_ready", "validated"} or not job.preview:
            raise DomainError("conflict", "Wait for a completed preview before validation.", 409)
        revision = get_draft(db, campus_id, job.revision_id)
        db.execute(select(Revision.id).where(Revision.id == revision.id).with_for_update(read=True))
        db.refresh(revision)
        if revision.edit_version != job.preview_version:
            raise DomainError(
                "conflict", "Draft changed. Refresh the preview before validation.", 409
            )
        if any(row["errors"] for row in job.preview["rows"]):
            raise DomainError(
                "import_validation_failed",
                "Resolve all invalid/conflicting rows before validation.",
                422,
            )
        transition(job, "validated", actor.id)
        log(db, job, "validate", actor.id, request.state.request_id)
    elif action in {"retry", "refresh"}:
        allowed = {"failed"} if action == "retry" else {"preview_ready", "validated"}
        if job.state not in allowed or (action == "retry" and job.attempts >= 3):
            raise DomainError(
                "conflict",
                "Retry unavailable (three attempts maximum); refresh is for a completed preview.",
                409,
            )
        get_draft(db, campus_id, job.revision_id)
        if action == "refresh":
            job.attempts = 0
        job.preview = None
        transition(job, "uploaded", actor.id)
        log(db, job, action, actor.id, request.state.request_id)
    elif action == "cancel":
        if job.state in {"committed", "cancelled"}:
            raise DomainError("conflict", "Completed or cancelled jobs cannot be cancelled.", 409)
        transition(job, "cancelled", actor.id)
        log(db, job, "cancel", actor.id, request.state.request_id)
    else:
        raise DomainError("location_not_found", "Unknown import action.", 404)
    db.flush()
    return output(job)


@router.get("/import-templates/{filename}")
def template(campus_id: UUID, filename: str, request: Request, db: DB):
    authorize(db, request, campus_id, "import_read")
    allowed = {
        "catalog-bundle.json",
        "options.json",
        "places.geojson",
        *[
            name + ".csv"
            for name in (
                "frames",
                "buildings",
                "places",
                "nodes",
                "edges",
                "departments",
                "department_places",
                "aliases",
                "anchors",
            )
        ],
    }
    if filename not in allowed:
        raise DomainError("location_not_found", "Unknown import template.", 404)
    path = Path(__file__).resolve().parents[4] / "data" / "templates" / "import-v1" / filename
    return FileResponse(path, filename=filename)
