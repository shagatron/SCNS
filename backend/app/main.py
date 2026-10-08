import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.api.v1.admin import router as admin_router
from app.api.v1.connections import router as connections_router
from app.api.v1.floorplans import router as floorplans_router
from app.api.v1.graph import router as graph_router
from app.api.v1.imports import router as imports_router
from app.api.v1.indoor import router as indoor_router
from app.api.v1.public import router
from app.api.v1.publication import router as publication_router
from app.api.v1.qr import public_router as qr_public_router
from app.api.v1.qr import router as qr_router
from app.core.config import get_settings
from app.core.errors import DomainError

app = FastAPI(
    title="Smart Campus Navigation",
    version="0.1.0",
    description="Outdoor navigation and Campus-scoped draft administration and staged imports.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().allowed_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=[
        "Content-Type",
        "X-CSRF-Token",
        "If-Match",
        "Idempotency-Key",
        "X-Import-Options",
        "X-Floorplan-Metadata",
    ],
    allow_credentials=True,
    expose_headers=["ETag", "X-Request-ID"],
)


@app.middleware("http")
async def request_id(request: Request, call_next):
    request.state.request_id = str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path.endswith("/routes") or request.url.path.startswith("/api/v1/admin"):
        response.headers["Cache-Control"] = "no-store"
    return response


def error_response(request: Request, code: str, message: str, status: int):
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": getattr(request.state, "request_id", "unavailable"),
            }
        },
    )


@app.exception_handler(DomainError)
async def domain_error(request: Request, exc: DomainError):
    return error_response(request, exc.code, exc.message, exc.status)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Do not echo raw request bodies or precise coordinates into errors/logs.
    return error_response(
        request,
        "invalid_input",
        "Check the request fields, IDs, ranges, and supported options.",
        422,
    )


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    if request.url.path.startswith("/api/v1/admin"):
        if isinstance(exc, IntegrityError):
            return error_response(
                request,
                "conflict",
                "A code or link is duplicated, or another record still references this item. Reconcile references and try again.",
                409,
            )
        if getattr(getattr(exc, "orig", None), "sqlstate", None) in {"40001", "40P01"}:
            return error_response(
                request,
                "conflict",
                "A concurrent change occurred. Reload the draft and reconcile your changes.",
                409,
            )
    logging.getLogger("scns").error(
        "Database failure request_id=%s type=%s", request.state.request_id, type(exc).__name__
    )
    return error_response(
        request,
        "service_unavailable",
        "Campus data is temporarily unavailable. Try again shortly.",
        503,
    )


app.include_router(router)
app.include_router(admin_router)
app.include_router(imports_router)
app.include_router(graph_router)

app.include_router(publication_router)
app.include_router(floorplans_router)


app.include_router(indoor_router)
app.include_router(connections_router)

app.include_router(qr_router)
app.include_router(qr_public_router)
