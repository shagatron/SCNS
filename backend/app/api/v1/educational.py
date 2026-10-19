"""Unpublished, non-campus educational preview; no DB or approval workflow."""

from fastapi import APIRouter, Response

from app.services.educational_indoor import DemoData, DemoRequest, DemoRoute, describe, route

router = APIRouter(prefix="/api/v1/educational/indoor-school", tags=["educational preview"])


@router.get("", response_model=DemoData)
def layout(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return describe()


@router.post("/routes", response_model=DemoRoute)
def directions(request: DemoRequest, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return route(request)
