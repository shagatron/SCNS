"""Campus-scoped graph commands; no publication or public-pointer mutations."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request, Response
from sqlalchemy import select

from app.api.v1.admin import DB, Version
from app.models import Revision
from app.schemas.graph import GraphPatch
from app.services.admin_auth import authorize
from app.services.admin_catalog import claim_version, get_draft
from app.services.admin_graph import apply_patch, graph_output, route_test, validate_graph

router = APIRouter(
    prefix="/api/v1/admin/campuses/{campus_id}/drafts/{revision_id}/graph", tags=["admin-graph"]
)


def read_context(db, request, campus_id, revision_id):
    authorize(db, request, campus_id, "draft_read")
    db.execute(
        select(Revision.id)
        .where(Revision.id == revision_id, Revision.campus_id == campus_id)
        .with_for_update(read=True)
    )
    return get_draft(db, campus_id, revision_id)


@router.get("")
def read_graph(campus_id: UUID, revision_id: UUID, request: Request, response: Response, db: DB):
    revision = read_context(db, request, campus_id, revision_id)
    response.headers["ETag"] = f'"{revision.edit_version}"'
    return graph_output(db, revision)


@router.post("")
def save_graph(
    campus_id: UUID,
    revision_id: UUID,
    payload: GraphPatch,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    actor = authorize(db, request, campus_id, "catalog_edit")
    revision = get_draft(db, campus_id, revision_id)
    claim_version(db, revision, if_match)
    return apply_patch(db, revision, payload, actor.id, request.state.request_id)


@router.get("/validation")
def validation(campus_id: UUID, revision_id: UUID, request: Request, db: DB):
    return validate_graph(db, read_context(db, request, campus_id, revision_id))


@router.get("/route-test")
def test_route(
    campus_id: UUID,
    revision_id: UUID,
    request: Request,
    db: DB,
    source: UUID,
    target: UUID,
    profile: Literal["shortest", "step_free"] = "shortest",
):
    return route_test(
        db, read_context(db, request, campus_id, revision_id), source, target, profile
    )
