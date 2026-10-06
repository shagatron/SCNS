import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.public import router
from app.core.config import get_settings
from app.core.errors import DomainError

app = FastAPI(
    title="Smart Campus Navigation",
    version="0.1.0",
    description="Milestones 0–1. Synthetic outdoor navigation; public read-only API.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def request_id(request: Request, call_next):
    request.state.request_id = str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path.endswith("/routes"):
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
