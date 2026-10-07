from uuid import UUID

from fastapi import APIRouter, Request

from app.api.v1.admin import DB, Version
from app.schemas.indoor import IndoorPatch
from app.services import indoor
from app.services.admin_auth import authorize
from app.services.publication import campus_lock, locked_revision

router = APIRouter(
    prefix="/api/v1/admin/campuses/{campus_id}/drafts/{revision_id}/floors/{floor_id}/indoor",
    tags=["admin-indoor"],
)


def scope(db, request, campus, revision, floor, version=None, write=False):
    if write:
        campus_lock(db, campus)
    actor = authorize(db, request, campus, "catalog_edit" if write else "draft_read")
    rev = locked_revision(db, campus, revision, version, read=not write)
    return actor, rev, indoor.floor_row(db, rev, floor)


@router.get("")
def read(campus_id: UUID, revision_id: UUID, floor_id: UUID, request: Request, db: DB):
    _, revision, floor = scope(db, request, campus_id, revision_id, floor_id)
    return indoor.output(db, revision, floor)


@router.patch("")
def edit(
    campus_id: UUID,
    revision_id: UUID,
    floor_id: UUID,
    payload: IndoorPatch,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    actor, revision, floor = scope(db, request, campus_id, revision_id, floor_id, if_match, True)
    return indoor.apply_patch(db, revision, floor, payload, actor, request.state.request_id)


@router.get("/validation")
def validate(campus_id: UUID, revision_id: UUID, floor_id: UUID, request: Request, db: DB):
    _, revision, floor = scope(db, request, campus_id, revision_id, floor_id)
    return indoor.validation(db, revision, floor)


@router.post("/preview")
def preview(
    campus_id: UUID,
    revision_id: UUID,
    floor_id: UUID,
    payload: IndoorPatch,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    _, revision, floor = scope(db, request, campus_id, revision_id, floor_id, if_match, True)
    return indoor.preview(db, revision, floor, payload)
