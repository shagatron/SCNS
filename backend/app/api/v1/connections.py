from uuid import UUID

from fastapi import APIRouter, Request

from app.api.v1.admin import DB, Version
from app.schemas.connections import ConnectionsPatch
from app.services import connections
from app.services.admin_auth import authorize
from app.services.publication import campus_lock, locked_revision

router = APIRouter(
    prefix="/api/v1/admin/campuses/{campus_id}/drafts/{revision_id}/connections",
    tags=["admin-connections"],
)


def scope(db, request, campus, revision, version=None, write=False):
    if write:
        campus_lock(db, campus)
    actor = authorize(db, request, campus, "catalog_edit" if write else "draft_read")
    rev = locked_revision(db, campus, revision, version, read=not write)
    return actor, rev


@router.get("")
def read(campus_id: UUID, revision_id: UUID, request: Request, db: DB):
    _, revision = scope(db, request, campus_id, revision_id)
    return connections.output(db, revision)


@router.patch("")
def edit(
    campus_id: UUID,
    revision_id: UUID,
    payload: ConnectionsPatch,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    actor, revision = scope(db, request, campus_id, revision_id, if_match, True)
    return connections.apply_patch(db, revision, payload, actor, request.state.request_id)


@router.post("/preview")
def preview(
    campus_id: UUID,
    revision_id: UUID,
    payload: ConnectionsPatch,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    _, revision = scope(db, request, campus_id, revision_id, if_match, True)
    _, state, findings = connections.proposal(db, revision, payload)
    return {"revision_version": revision.edit_version, "records": state, "diagnostics": findings}


@router.get("/validation")
def validate(campus_id: UUID, revision_id: UUID, request: Request, db: DB):
    _, revision = scope(db, request, campus_id, revision_id)
    return connections.validation(db, revision)
