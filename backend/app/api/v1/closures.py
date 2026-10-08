from uuid import UUID

from fastapi import APIRouter, Request, Response

from app.api.v1.admin import DB, Version
from app.api.v1.public import DB as PublicDB
from app.schemas.closures import ClosureCreate, ClosureDecision, ClosureRebind, ClosureStatus
from app.services import closures
from app.services.admin_auth import authorize
from app.services.catalog import active_release
from app.services.mixed_routes import release_projection
from app.services.publication import campus_lock

router = APIRouter(prefix="/api/v1/admin/campuses/{campus_id}/closures", tags=["admin-closures"])
public_router = APIRouter(prefix="/api/v1/campuses/{campus_id}", tags=["closures"])


@router.get("")
def listing(campus_id: UUID, request: Request, db: DB):
    authorize(db, request, campus_id, "closure_read")
    release = active_release(db, campus_id)
    data = release_projection(db, release)
    choices = closures.targets(data)
    return {
        "release_id": str(release.id),
        "closure_overlay_version": closures.version(db, campus_id),
        "items": [closures.record(o) for o in closures.records(db, campus_id)],
        "targets": choices[:5000],
        "targets_truncated": len(choices) > 5000,
    }


def write(db, request, campus):
    campus_lock(db, campus)
    return authorize(db, request, campus, "closure_manage")


@router.post("", status_code=201)
def create(
    campus_id: UUID, payload: ClosureCreate, request: Request, db: DB, if_match: Version = None
):
    actor = write(db, request, campus_id)
    return closures.mutate(db, campus_id, actor, payload, if_match, request.state.request_id)


@router.post("/{closure_id}/reopen")
def reopen(
    campus_id: UUID,
    closure_id: UUID,
    payload: ClosureDecision,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    actor = write(db, request, campus_id)
    return closures.mutate(
        db, campus_id, actor, payload, if_match, request.state.request_id, "reopen", closure_id
    )


@router.post("/{closure_id}/rebind")
def rebind(
    campus_id: UUID,
    closure_id: UUID,
    payload: ClosureRebind,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    actor = write(db, request, campus_id)
    return closures.mutate(
        db, campus_id, actor, payload, if_match, request.state.request_id, "rebind", closure_id
    )


@public_router.get("/closures", response_model=ClosureStatus)
def status(campus_id: UUID, db: PublicDB, response: Response):
    response.headers["Cache-Control"] = "no-store"
    release = active_release(db, campus_id)
    return closures.public_status(db, campus_id, release, release_projection(db, release))
