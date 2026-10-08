from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request, Response

from app.api.v1.admin import DB, Version
from app.schemas.qr import Installation, MarkerCreate, MarkerInput, MarkerResolution, Revoke
from app.services import qr, qr_signs
from app.services.admin_auth import authorize
from app.services.publication import campus_lock

router = APIRouter(prefix="/api/v1/admin/campuses/{campus_id}/qr-markers", tags=["admin-qr"])
public_router = APIRouter(prefix="/api/v1/qr", tags=["qr"])


@public_router.get("/{marker_id}", response_model=MarkerResolution)
def resolution(marker_id: UUID, db: DB, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return qr.resolve(db, marker_id)


def write(db, request, campus):
    campus_lock(db, campus)
    return authorize(db, request, campus, "qr_manage")


@router.get("")
def listing(campus_id: UUID, request: Request, db: DB, response: Response):
    authorize(db, request, campus_id, "qr_read")
    response.headers["Cache-Control"] = "no-store"
    return qr.listing(db, campus_id)


@router.post("", status_code=201)
def create(campus_id: UUID, payload: MarkerCreate, request: Request, db: DB):
    actor = write(db, request, campus_id)
    return qr.create(db, campus_id, actor, payload, request.state.request_id)


@router.put("/{marker_id}")
def edit(
    campus_id: UUID,
    marker_id: UUID,
    payload: MarkerInput,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    actor = write(db, request, campus_id)
    qr.require_version(if_match)
    return qr.edit(
        db, qr.row(db, campus_id, marker_id, if_match), actor, payload, request.state.request_id
    )


@router.post("/{marker_id}/activate")
def activate(
    campus_id: UUID,
    marker_id: UUID,
    payload: Installation,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    actor = write(db, request, campus_id)
    qr.require_version(if_match)
    return qr.verify(
        db, qr.row(db, campus_id, marker_id, if_match), actor, payload, request.state.request_id
    )


@router.post("/{marker_id}/revoke")
def revoke(
    campus_id: UUID,
    marker_id: UUID,
    payload: Revoke,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    actor = write(db, request, campus_id)
    qr.require_version(if_match)
    return qr.revoke(
        db, qr.row(db, campus_id, marker_id, if_match), actor, payload, request.state.request_id
    )


@router.get("/{marker_id}/sign.{format}")
def sign(
    campus_id: UUID, marker_id: UUID, format: Literal["svg", "png", "pdf"], request: Request, db: DB
):
    authorize(db, request, campus_id, "qr_read")
    obj = qr.row(db, campus_id, marker_id)
    return Response(
        qr_signs.render(obj, format),
        media_type={"svg": "image/svg+xml", "png": "image/png", "pdf": "application/pdf"}[format],
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="qr-{obj.id}.{format}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
