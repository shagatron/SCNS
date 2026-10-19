"""Private staging jobs and transactional revision-CAS floor/layer/calibration writes."""

import base64
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.models import Building, Campus, Frame, Node
from app.models.connections import ConnectorStop, FloorRouting
from app.models.floorplans import Floor, FloorplanJob, MapLayer
from app.models.indoor import IndoorAccess, IndoorEdge, IndoorNode, Room
from app.models.publication import SourceAsset
from app.schemas.floorplans import CalibrationInput
from app.services.admin_auth import audit
from app.services.publication import canonical, checksum

BYTE_LIMIT = 10 * 1024**2
STORAGE_LIMIT = 256 * 1024**2


def editable(revision):
    if revision.status != "draft":
        raise DomainError(
            "conflict",
            "This revision is review-locked/frozen; return it to draft before editing.",
            409,
        )


def row(db, model, revision, identity):
    value = db.get(model, (revision.id, identity))
    if value is None or value.campus_id != revision.campus_id:
        raise DomainError("location_not_found", "Record not found in this campus/revision.", 404)
    return value


def changed(db, revision, actor, action, resource, request_id, before=None, after=None):
    revision.edit_version += 1
    revision.checksum = None
    audit(
        db,
        action,
        request_id,
        actor_id=actor.id,
        campus_id=revision.campus_id,
        revision_id=revision.id,
        resource_id=resource,
        before=before,
        after=after,
    )
    db.flush()
    return {"edit_version": revision.edit_version}


def size_used(db, campus_id):
    total = 0
    for model, fields in (
        (FloorplanJob, (FloorplanJob.original, FloorplanJob.png)),
        (MapLayer, (MapLayer.png,)),
        (SourceAsset, (SourceAsset.original,)),
    ):
        for field in fields:
            total += (
                db.scalar(
                    select(func.coalesce(func.sum(func.octet_length(field)), 0)).where(
                        model.campus_id == campus_id
                    )
                )
                or 0
            )
    return total


def quota(db, campus_id, extra):
    if size_used(db, campus_id) + extra > STORAGE_LIMIT:
        raise DomainError(
            "storage_limit",
            "Campus floorplan/source storage exceeds 256MiB including retained jobs/releases. Use smaller permitted plans; no existing data was removed.",
            413,
        )


def dependencies(db, revision, floor):
    layers = list(
        db.scalars(
            select(MapLayer.id).where(
                MapLayer.dataset_revision_id == revision.id, MapLayer.floor_id == floor.id
            )
        ).all()
    )
    pending = list(
        db.scalars(
            select(FloorplanJob.id).where(
                FloorplanJob.revision_id == revision.id,
                FloorplanJob.floor_id == floor.id,
                FloorplanJob.state.in_(["uploaded", "processing", "ready"]),
            )
        ).all()
    )
    nodes = (
        db.scalar(
            select(func.count())
            .select_from(Node)
            .where(Node.dataset_revision_id == revision.id, Node.frame_id == floor.frame_id)
        )
        if floor.frame_id
        else 0
    )
    indoor_count = sum(
        db.scalar(
            select(func.count())
            .select_from(m)
            .where(m.dataset_revision_id == revision.id, m.floor_id == floor.id)
        )
        for m in (IndoorNode, Room, ConnectorStop, FloorRouting)
    )
    return {
        "indoor_records": indoor_count,
        "layer_ids": sorted(str(x) for x in layers),
        "pending_job_ids": sorted(str(x) for x in pending),
        "graph_nodes": nodes,
    }


def floor_data(db, revision, floor):
    frame = db.get(Frame, (revision.id, floor.frame_id)) if floor.frame_id else None
    layer = db.get(MapLayer, (revision.id, floor.layer_id)) if floor.layer_id else None
    source = db.get(SourceAsset, (revision.id, layer.source_id)) if layer else None
    return {
        "id": str(floor.id),
        "building_id": str(floor.building_id),
        "code": floor.code,
        "label": floor.label,
        "ordering": floor.ordering,
        "elevation_m": floor.elevation_m,
        "visibility": floor.visibility,
        "frame_id": str(floor.frame_id) if frame else None,
        "layer_id": str(floor.layer_id) if layer else None,
        "frame": {
            "width_px": frame.width_px,
            "height_px": frame.height_px,
            "metres_per_pixel": frame.metres_per_pixel,
            "calibration": frame.calibration,
            "origin": "top_left",
            "axes": "x_right_y_down",
            "units": "pixels",
        }
        if frame
        else None,
        "layer": {
            "id": str(layer.id),
            "source_id": str(layer.source_id),
            "page": layer.page,
            "checksum": layer.checksum,
            "display_width_px": layer.display_width_px,
            "display_height_px": layer.display_height_px,
            "processing": layer.processing,
            "approved": bool(source.approved_by),
            "uploader_id": str(source.uploader_id),
            "rights": source.rights,
            "attribution": source.attribution,
        }
        if layer
        else None,
        "dependencies": dependencies(db, revision, floor),
    }


def listing(db, revision):
    floors = db.scalars(
        select(Floor)
        .where(Floor.dataset_revision_id == revision.id)
        .order_by(Floor.building_id, Floor.ordering, Floor.code)
        .limit(501)
    ).all()
    return {
        "campus_name": db.get(Campus, revision.campus_id).name,
        "is_demo": db.get(Campus, revision.campus_id).is_demo,
        "edit_version": revision.edit_version,
        "status": revision.status,
        "buildings": [
            {"id": str(b.id), "code": b.code, "name": b.name, "visibility": b.visibility}
            for b in db.scalars(
                select(Building)
                .where(Building.dataset_revision_id == revision.id)
                .order_by(Building.code)
                .limit(1000)
            )
        ],
        "floors": [floor_data(db, revision, f) for f in floors[:500]],
        "truncated": len(floors) > 500,
    }


def save_floor(db, revision, payload, actor, request_id, identity=None):
    editable(revision)
    if (
        not identity
        and db.scalar(
            select(func.count()).select_from(Floor).where(Floor.dataset_revision_id == revision.id)
        )
        >= 500
    ):
        raise DomainError("dataset_limit", "This slice supports at most 500 floors per draft.", 422)
    row(db, Building, revision, payload.building_id)
    floor = (
        row(db, Floor, revision, identity)
        if identity
        else Floor(
            id=payload.id or uuid4(),
            campus_id=revision.campus_id,
            dataset_revision_id=revision.id,
            frame_id=None,
            layer_id=None,
        )
    )
    before = floor_data(db, revision, floor) if identity else None
    if identity and floor.building_id != payload.building_id:
        raise DomainError(
            "conflict",
            "Moving a floor between buildings is unsupported; create a distinct floor and explicitly handle its plans.",
            409,
        )
    if identity and payload.id not in (None, identity):
        raise DomainError("invalid_input", "Stable floor IDs cannot be changed.")
    if (
        identity
        and payload.visibility != "public"
        and any(
            db.scalar(
                select(model.id)
                .where(
                    model.dataset_revision_id == revision.id,
                    model.floor_id == floor.id,
                    model.visibility == "public",
                )
                .limit(1)
            )
            for model in (Room, IndoorNode, IndoorEdge, IndoorAccess)
        )
    ):
        raise DomainError(
            "conflict",
            "Restrict public indoor records explicitly before restricting their floor.",
            409,
        )
    for field, value in payload.model_dump(exclude={"id"}).items():
        setattr(floor, field, value)
    db.add(floor)
    db.flush()
    return {
        "id": str(floor.id),
        **changed(
            db,
            revision,
            actor,
            "floor.update" if identity else "floor.create",
            floor.id,
            request_id,
            before=before,
            after=floor_data(db, revision, floor),
        ),
    }


def delete_floor(db, revision, identity, payload, actor, request_id):
    editable(revision)
    floor = row(db, Floor, revision, identity)
    deps = dependencies(db, revision, floor)
    if deps["graph_nodes"] or deps["indoor_records"] or deps["pending_job_ids"]:
        raise DomainError(
            "conflict",
            "Floor has dependent graph nodes or staged jobs. Explicitly cancel staged jobs; graph dependencies require a later verified workflow.",
            409,
        )
    if sorted(str(x) for x in payload.remove_layer_ids) != deps["layer_ids"]:
        raise DomainError(
            "conflict",
            "Confirm the exact dependent layer IDs before deleting this floor and its draft plans.",
            409,
        )
    before = floor_data(db, revision, floor)
    frame_id = floor.frame_id
    floor.layer_id = None
    floor.frame_id = None
    db.flush()
    sources = []
    for layer in db.scalars(
        select(MapLayer).where(
            MapLayer.dataset_revision_id == revision.id, MapLayer.floor_id == floor.id
        )
    ):
        sources.append(layer.source_id)
        db.delete(layer)
    db.flush()
    for identity in sources:
        source = db.get(SourceAsset, (revision.id, identity))
        if source and not db.scalar(
            select(MapLayer.id)
            .where(MapLayer.dataset_revision_id == revision.id, MapLayer.source_id == identity)
            .limit(1)
        ):
            db.delete(source)
    db.delete(floor)
    db.flush()
    if frame_id:
        db.delete(row(db, Frame, revision, frame_id))
    return changed(
        db,
        revision,
        actor,
        "floor.delete",
        floor.id,
        request_id,
        before=before,
        after={"removed_layer_ids": deps["layer_ids"]},
    )


def signature(raw):
    if raw.startswith(b"%PDF-"):
        return "application/pdf"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    raise DomainError(
        "invalid_input",
        "Actual file signature must be PDF, PNG or JPEG; SVG/CAD/URLs are unsupported.",
    )


def job_output(job):
    return {
        "id": str(job.id),
        "floor_id": str(job.floor_id),
        "filename": job.filename,
        "state": job.state,
        "attempts": job.attempts,
        "options": job.options,
        "original_checksum": job.original_checksum,
        "media_type": job.media_type,
        "metadata": job.metadata_,
        "failure": job.failure,
        "layer_id": str(job.layer_id) if job.layer_id else None,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }


def job_row(db, revision, identity, *, lock=False):
    query = select(FloorplanJob).where(
        FloorplanJob.id == identity,
        FloorplanJob.revision_id == revision.id,
        FloorplanJob.campus_id == revision.campus_id,
    )
    if lock:
        query = query.with_for_update()
    job = db.scalar(query.execution_options(populate_existing=True))
    if job is None:
        raise DomainError(
            "location_not_found", "Floorplan job not found in this campus/revision.", 404
        )
    return job


def upload(db, revision, payload, raw, actor, request_id):
    editable(revision)
    row(db, Floor, revision, payload.floor_id)
    if not raw or len(raw) > BYTE_LIMIT:
        raise DomainError("upload_too_large", "Supply a nonempty plan at most 10MiB.", 413)
    media = signature(raw)
    opts = payload.model_dump(mode="json")
    sha = hashlib.sha256(raw).hexdigest()
    fingerprint = checksum({"sha256": sha, "options": opts, "revision": str(revision.id)})
    existing = db.scalar(
        select(FloorplanJob).where(
            FloorplanJob.campus_id == revision.campus_id,
            FloorplanJob.uploader_id == actor.id,
            FloorplanJob.key == payload.key,
        )
    )
    if existing:
        if existing.fingerprint != fingerprint:
            raise DomainError(
                "conflict",
                "Upload key was already used for different content/options. Use an explicit new batch key.",
                409,
            )
        return job_output(existing)
    if payload.rights == "synthetic" and not db.get(Campus, revision.campus_id).is_demo:
        raise DomainError(
            "invalid_input", "Synthetic rights require an explicitly synthetic campus."
        )
    quota(db, revision.campus_id, len(raw))
    job = FloorplanJob(
        id=uuid4(),
        campus_id=revision.campus_id,
        revision_id=revision.id,
        floor_id=payload.floor_id,
        uploader_id=actor.id,
        key=payload.key,
        fingerprint=fingerprint,
        filename=payload.filename,
        media_type=media,
        original=raw,
        original_checksum=sha,
        options=opts,
        state="uploaded",
        attempts=0,
    )
    db.add(job)
    db.flush()
    audit(
        db,
        "floorplan.upload",
        request_id,
        actor_id=actor.id,
        campus_id=revision.campus_id,
        revision_id=revision.id,
        resource_id=job.id,
        after={"original_checksum": sha, "page": payload.page, "rights": payload.rights},
    )
    return job_output(job)


def control(db, revision, job, command, actor, request_id):
    editable(revision)
    if command == "cancel" and job.state not in {"applied", "cancelled"}:
        job.state = "cancelled"
        job.lease = None
    elif command == "retry" and job.state == "failed" and job.attempts < 3:
        row(db, Floor, revision, job.floor_id)
        job.state = "uploaded"
        job.failure = None
        job.lease = None
    else:
        raise DomainError(
            "conflict",
            "Only failed jobs below three attempts may retry; applied jobs cannot cancel.",
            409,
        )
    job.updated_at = datetime.now(UTC)
    audit(
        db,
        f"floorplan.{command}",
        request_id,
        actor_id=actor.id,
        campus_id=revision.campus_id,
        revision_id=revision.id,
        resource_id=job.id,
        after={"state": job.state, "attempts": job.attempts},
    )
    db.flush()
    return job_output(job)


def decode(raw, options):
    """Child gets no DB/session/proxy environment, no inherited FDs; fail closed."""
    with tempfile.TemporaryFile() as output:
        process = subprocess.run(
            [sys.executable, "-m", "app.cli.render_floorplan"],
            input=canonical({"bytes": base64.b64encode(raw).decode(), "options": options}),
            stdout=output,
            stderr=subprocess.DEVNULL,
            timeout=30,
            env={"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"},
            close_fds=True,
        )
        output.seek(0)
        value = output.read(24 * 1024**2 + 1)
        if process.returncode or len(value) > 24 * 1024**2:
            raise ValueError("Isolated decoder refused input or exceeded limits.")
        result = json.loads(value)
        return base64.b64decode(result["png"], validate=True), result["metadata"]


def process_owned(db, job):
    """Transactional test helper; real worker decodes outside DB transactions."""
    png, metadata = decode(job.original, job.options)
    quota(db, job.campus_id, len(png))
    job.png = png
    job.metadata_ = metadata
    job.state = "ready"
    job.failure = None
    job.lease = None
    job.updated_at = datetime.now(UTC)
    db.flush()


def once(engine):
    with Session(engine.execution_options(isolation_level="READ COMMITTED")) as db, db.begin():
        job = db.scalar(
            select(FloorplanJob)
            .where(
                or_(
                    FloorplanJob.state == "uploaded",
                    (FloorplanJob.state == "processing")
                    & (FloorplanJob.updated_at < datetime.now(UTC) - timedelta(seconds=120)),
                )
            )
            .order_by(FloorplanJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return False
        if job.attempts >= 3:
            job.state = "failed"
            job.failure = "Three worker attempts exhausted. Inspect/correct the source and create a new batch."
            job.lease = None
            job.updated_at = datetime.now(UTC)
            return True
        job.state = "processing"
        job.attempts += 1
        job.lease = uuid4()
        job.updated_at = datetime.now(UTC)
        identity, lease, campus_id, raw, options = (
            job.id,
            job.lease,
            job.campus_id,
            job.original,
            job.options,
        )
    try:
        png, metadata = decode(raw, options)
        failure = None
    except (ValueError, subprocess.TimeoutExpired, KeyError, OSError):
        png = metadata = None
        failure = "Processing failed safely. Check unencrypted PDF/PNG/JPEG, page selection, dimensions/redactions and processing limits. Retry only after a transient failure; corrected options need a new batch."
    from app.services.publication import campus_lock

    with Session(engine.execution_options(isolation_level="READ COMMITTED")) as db, db.begin():
        campus_lock(db, campus_id)
        job = db.scalar(select(FloorplanJob).where(FloorplanJob.id == identity).with_for_update())
        if job.state != "processing" or job.lease != lease:
            return True  # A cancelled/recovered lease never applies a late decoder result.
        if not failure:
            try:
                quota(db, campus_id, len(png))
            except DomainError as exc:
                failure = exc.message
        job.state = "failed" if failure else "ready"
        job.failure = failure
        job.png = None if failure else png
        job.metadata_ = None if failure else metadata
        job.lease = None
        job.updated_at = datetime.now(UTC)
        audit(
            db,
            "floorplan.process",
            f"floor-worker-{lease}",
            actor_id=None,
            campus_id=campus_id,
            revision_id=job.revision_id,
            resource_id=identity,
            after={
                "state": job.state,
                "attempt": job.attempts,
                "uploader_id": str(job.uploader_id),
            },
        )
    return True


def apply_job(db, revision, job, payload, actor, request_id):
    editable(revision)
    if job.state == "applied":
        # Exact retry remains safe; replacing the floor afterward makes this stale.
        floor = row(db, Floor, revision, job.floor_id)
        if floor.layer_id != job.layer_id or job.apply_options != payload.model_dump(mode="json"):
            raise DomainError("conflict", "This applied batch is no longer the selected plan.", 409)
        return {"layer_id": str(job.layer_id), "edit_version": revision.edit_version, "retry": True}
    if job.state != "ready" or not job.png or not job.metadata_:
        raise DomainError("conflict", "Wait for a ready sanitized preview before applying.", 409)
    floor = row(db, Floor, revision, job.floor_id)
    if floor.layer_id != payload.replace_layer_id:
        raise DomainError(
            "conflict",
            "Selected floor plan changed. Explicitly reconcile/confirm the current layer before replacement.",
            409,
        )
    if any(dependencies(db, revision, floor)[k] for k in ("graph_nodes", "indoor_records")):
        raise DomainError(
            "conflict",
            "Plan replacement has dependent graph geometry; a verified transform/retrace is required in a later slice.",
            409,
        )
    if floor.layer_id and not payload.reset_calibration:
        raise DomainError(
            "conflict",
            "Replacing a plan must explicitly reset calibration; old pixel coordinates/scales cannot be reused.",
            409,
        )
    quota(db, revision.campus_id, len(job.original) + len(job.png))
    # Existing source quota also applies to cloned/published private originals.
    used = db.scalar(
        select(func.coalesce(func.sum(func.octet_length(SourceAsset.original)), 0)).where(
            SourceAsset.campus_id == revision.campus_id
        )
    )
    if used + len(job.original) > 100 * 1024**2:
        raise DomainError(
            "storage_limit", "Applying this original exceeds the 100MiB campus source quota.", 413
        )
    before = floor_data(db, revision, floor)
    meta = job.metadata_
    source_id, layer_id = uuid4(), uuid4()
    frame = (
        row(db, Frame, revision, floor.frame_id)
        if floor.frame_id
        else Frame(
            id=uuid4(),
            dataset_revision_id=revision.id,
            campus_id=revision.campus_id,
            code=f"floor-{floor.id}",
            kind="indoor",
        )
    )
    frame.width_px = meta["width_px"]
    frame.height_px = meta["height_px"]
    frame.metres_per_pixel = None
    frame.calibration = None
    db.add(frame)
    db.flush()
    source = SourceAsset(
        id=source_id,
        dataset_revision_id=revision.id,
        campus_id=revision.campus_id,
        title=job.options["title"],
        rights=job.options["rights"],
        provenance=job.options["provenance"],
        attribution=job.options["attribution"],
        uploader_id=job.uploader_id,
        approved_by=None,
        original_filename=job.filename,
        media_type=job.media_type,
        original=job.original,
        original_checksum=job.original_checksum,
        derivative={
            "kind": "floorplan",
            "layer_id": str(layer_id),
            "checksum": hashlib.sha256(job.png).hexdigest(),
            "width_px": meta["width_px"],
            "height_px": meta["height_px"],
            "display_width_px": meta["display_width_px"],
            "display_height_px": meta["display_height_px"],
            "page": meta["page"],
        },
    )
    db.add(source)
    db.flush()
    layer = MapLayer(
        id=layer_id,
        dataset_revision_id=revision.id,
        campus_id=revision.campus_id,
        floor_id=floor.id,
        frame_id=frame.id,
        source_id=source_id,
        page=meta["page"],
        width_px=meta["width_px"],
        height_px=meta["height_px"],
        display_width_px=meta["display_width_px"],
        display_height_px=meta["display_height_px"],
        checksum=source.derivative["checksum"],
        png=job.png,
        processing=meta,
    )
    db.add(layer)
    db.flush()
    floor.layer_id = layer.id
    floor.frame_id = frame.id
    job.apply_options = payload.model_dump(mode="json")
    job.state = "applied"
    job.layer_id = layer.id
    job.updated_at = datetime.now(UTC)
    return {
        "layer_id": str(layer.id),
        **changed(
            db,
            revision,
            actor,
            "floorplan.apply",
            layer.id,
            request_id,
            before=before,
            after={
                "floor_id": str(floor.id),
                "job_id": str(job.id),
                "original_checksum": job.original_checksum,
                "display_checksum": layer.checksum,
                "page": layer.page,
                "calibration_reset": True,
            },
        ),
    }


def calibration(payload: CalibrationInput, width, height, actor_id, is_demo, timezone="UTC"):
    if payload.plan_quality != "uniform":
        raise DomainError(
            "invalid_input",
            "Distorted/perspective/stretched plans need a fitted transform, unsupported in 3A; use a rectified permitted plan.",
        )
    if payload.measured_on > datetime.now(UTC).astimezone(ZoneInfo(timezone)).date():
        raise DomainError("invalid_input", "Measurement date cannot be in the future.")
    segments = [payload.primary, *payload.checks]
    for segment in segments:
        if any(p.x > width or p.y > height for p in (segment.start, segment.end)):
            raise DomainError(
                "invalid_input", "Calibration control points must be inside the reference image."
            )

    def vector(segment):
        return segment.end.x - segment.start.x, segment.end.y - segment.start.y

    vx, vy = vector(payload.primary)
    length = math.hypot(vx, vy)
    if length < 10 or payload.uncertainty_m >= payload.primary.distance_m * 0.1:
        raise DomainError(
            "invalid_input",
            "Use a nondegenerate line at least 10px long and uncertainty below 10% of its measured distance.",
        )
    scale = payload.primary.distance_m / length
    errors = []
    independent = False
    for check in payload.checks:
        cx, cy = vector(check)
        check_length = math.hypot(cx, cy)
        if check_length < 10:
            raise DomainError("invalid_input", "Check measurements must span at least 10 pixels.")
        independent |= abs(vx * cy - vy * cx) / (length * check_length) >= 0.2
        error = abs(check_length * scale - check.distance_m)
        if error > max(0.02 * check.distance_m, payload.uncertainty_m):
            raise DomainError(
                "invalid_input",
                "Independent check differs by more than 2%/stated uncertainty. Verify measurements or rectify the plan; do not average inconsistent scales.",
            )
        errors.append(error)
    if not independent:
        raise DomainError(
            "invalid_input",
            "Supply at least one independent nonparallel check line to assess uniform scale.",
        )
    return {
        **payload.model_dump(mode="json"),
        "metres_per_pixel": scale,
        "origin": "top_left",
        "axes": "x_right_y_down",
        "units": "pixels",
        "measured_by": str(actor_id),
        "quality": "synthetic_calibrated" if is_demo else "measured_uniform",
        "maximum_check_error_m": max(errors),
        "relative_tolerance": 0.02,
        "reviewer": None,
    }


def calibrate(db, revision, floor, payload, actor, request_id):
    editable(revision)
    if not floor.layer_id:
        raise DomainError("conflict", "Apply a plan before measuring its reference pixels.", 409)
    if any(dependencies(db, revision, floor)[k] for k in ("graph_nodes", "indoor_records")):
        raise DomainError(
            "conflict",
            "Dependent indoor geometry needs verified metric recalculation, unsupported in 3A.",
            409,
        )
    frame = row(db, Frame, revision, floor.frame_id)
    before = frame.calibration
    value = calibration(
        payload,
        frame.width_px,
        frame.height_px,
        actor.id,
        db.get(Campus, revision.campus_id).is_demo,
        db.get(Campus, revision.campus_id).timezone,
    )
    value["layer_checksum"] = row(db, MapLayer, revision, floor.layer_id).checksum
    frame.calibration = value
    frame.metres_per_pixel = value["metres_per_pixel"]
    return changed(
        db, revision, actor, "floor.calibrate", floor.id, request_id, before=before, after=value
    )


def approve_calibration(db, revision, floor, actor, request_id):
    editable(revision)
    if not floor.frame_id:
        raise DomainError("conflict", "No selected calibrated plan.", 409)
    frame = row(db, Frame, revision, floor.frame_id)
    value = frame.calibration
    if not value or value.get("reviewer"):
        raise DomainError("conflict", "Only a new unreviewed calibration can be approved.", 409)
    if value["measured_by"] == str(actor.id):
        raise DomainError(
            "separation_of_duties",
            "The measurement author cannot approve its own calibration.",
            403,
        )
    if value["layer_checksum"] != row(db, MapLayer, revision, floor.layer_id).checksum:
        raise DomainError("conflict", "Plan changed; recalibrate its exact selected pixels.", 409)
    frame.calibration = {
        **value,
        "reviewer": str(actor.id),
        "reviewed_on": datetime.now(UTC).isoformat(),
    }
    return changed(
        db,
        revision,
        actor,
        "floor.calibration_approve",
        floor.id,
        request_id,
        before=value,
        after=frame.calibration,
    )
