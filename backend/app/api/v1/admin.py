from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import DomainError
from app.db.session import get_admin_session
from app.models import ActiveRelease, Campus, Node, Revision
from app.models.admin import AuditEvent, RoleAssignment, User
from app.schemas.admin import (
    AuditOut,
    CatalogPage,
    CatalogWrite,
    DashboardOut,
    DraftOut,
    Entity,
    LoginInput,
    MutationOut,
    NodeOption,
    RoleInput,
    SessionOut,
    UserInput,
    UserOut,
)
from app.schemas.api import ErrorOut
from app.services.admin_auth import (
    COOKIE,
    COOKIE_PATH,
    HASHER,
    audit,
    authenticated,
    authorize,
    login,
    permissions,
    session_output,
)
from app.services.admin_catalog import (
    MODELS,
    claim_version,
    create_draft,
    draft_output,
    get_draft,
    record,
    remove_record,
    write_record,
)
from app.services.catalog import active_release

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    responses={code: {"model": ErrorOut} for code in (401, 403, 404, 409, 422, 428, 429)},
)
DB = Annotated[Session, Depends(get_admin_session, scope="function")]
Version = Annotated[str | None, Header(alias="If-Match")]


@router.post("/login", response_model=SessionOut)
def sign_in(payload: LoginInput, request: Request, response: Response, db: DB):
    result, code = login(db, request, payload.username, payload.password.get_secret_value())
    if code:
        # Return normally so rate-limit counters and failed-login audit commit.
        return JSONResponse(
            status_code=429 if code == "rate_limited" else 401,
            headers={"Retry-After": str(get_settings().login_window_seconds)}
            if code == "rate_limited"
            else {},
            content={
                "error": {
                    "code": code,
                    "message": "Too many sign-in attempts. Try again later."
                    if code == "rate_limited"
                    else "Incorrect username or password.",
                    "request_id": request.state.request_id,
                }
            },
        )
    user, session, token = result
    response.set_cookie(
        COOKIE,
        token,
        max_age=get_settings().session_ttl_seconds,
        httponly=True,
        secure=get_settings().session_cookie_secure,
        samesite="strict",
        path=COOKIE_PATH,
    )
    return session_output(db, user, session, token)


@router.get("/session", response_model=SessionOut)
def current_session(request: Request, db: DB):
    return session_output(db, *authenticated(db, request))


@router.post("/logout", status_code=204)
def sign_out(request: Request, response: Response, db: DB):
    user, session, _ = authenticated(db, request)
    session.revoked_at = datetime.now(UTC)
    audit(db, "auth.logout", request.state.request_id, actor_id=user.id, resource_id=session.id)
    response.delete_cookie(
        COOKIE,
        path=COOKIE_PATH,
        httponly=True,
        samesite="strict",
        secure=get_settings().session_cookie_secure,
    )


@router.get("/campuses/{campus_id}/dashboard", response_model=DashboardOut)
def dashboard(campus_id: UUID, request: Request, db: DB):
    user = authorize(db, request, campus_id, "dashboard")
    allowed = permissions(db, user.id, campus_id)
    campus = db.get(Campus, campus_id)
    query = select(Revision).where(
        Revision.campus_id == campus_id, Revision.status.in_(["draft", "review"])
    )
    drafts = (
        db.scalars(query.order_by(Revision.version.desc()).limit(100)).all()
        if "draft_read" in allowed
        else []
    )
    return DashboardOut(
        campus_id=campus_id,
        campus_name=campus.name,
        campus_code=campus.code,
        timezone=campus.timezone,
        is_demo=campus.is_demo,
        permissions=sorted(allowed),
        release=active_release(db, campus_id)
        if db.get(ActiveRelease, (campus_id, "public"))
        else None,
        drafts=[draft_output(r) for r in drafts],
        drafts_total=db.scalar(select(func.count()).select_from(query.subquery()))
        if "draft_read" in allowed
        else 0,
        limitations=[
            "Draft catalog edits do not change the published map.",
            "Staged imports apply only to drafts. Outdoor graph editing is draft-only. Review and publication require independent approval of exact validated content.",
            "Operational closure tools are a later milestone.",
        ],
    )


@router.post("/campuses/{campus_id}/drafts", response_model=DraftOut, status_code=201)
def new_draft(
    campus_id: UUID,
    request: Request,
    db: DB,
    idempotency_key: Annotated[
        str | None, Header(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    ] = None,
):
    user = authorize(db, request, campus_id, "draft_create")
    return create_draft(db, campus_id, user.id, request.state.request_id, idempotency_key)


@router.get(
    "/campuses/{campus_id}/drafts/{revision_id}/catalog/{entity}", response_model=CatalogPage
)
def catalog(
    campus_id: UUID,
    revision_id: UUID,
    entity: Entity,
    request: Request,
    db: DB,
    response: Response,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
    resource_id: UUID | None = Query(None),
):
    authorize(db, request, campus_id, "draft_read")
    # Hold a shared revision lock so rows and their version form one coherent read.
    db.execute(
        select(Revision.id)
        .where(Revision.id == revision_id, Revision.campus_id == campus_id)
        .with_for_update(read=True)
    )
    revision = get_draft(db, campus_id, revision_id)
    model = MODELS[entity]
    query = select(model).where(model.dataset_revision_id == revision.id)
    if entity == "places":
        query = query.where(model.point.is_not(None))
    if resource_id:
        query = query.where(model.id == resource_id)
    rows = db.scalars(query.order_by(model.id).limit(limit).offset(offset)).all()
    response.headers["ETag"] = f'"{revision.edit_version}"'
    return CatalogPage(
        revision_version=revision.edit_version,
        items=[record(db, entity, row) for row in rows],
        total=db.scalar(select(func.count()).select_from(query.subquery())),
        offset=offset,
        limit=limit,
    )


@router.get("/campuses/{campus_id}/drafts/{revision_id}/nodes", response_model=list[NodeOption])
def nodes(
    campus_id: UUID,
    revision_id: UUID,
    request: Request,
    db: DB,
    q: str = Query("", max_length=160),
    offset: int = Query(0, ge=0, le=50000),
):
    authorize(db, request, campus_id, "draft_read")
    get_draft(db, campus_id, revision_id)
    return [
        NodeOption(id=n.id, label=n.label, visibility=n.visibility)
        for n in db.scalars(
            select(Node)
            .where(
                Node.dataset_revision_id == revision_id, Node.label.icontains(q, autoescape=True)
            )
            .order_by(Node.label, Node.id)
            .limit(100)
            .offset(offset)
        )
    ]


def edit_context(db, request, campus_id, revision_id, entity, payload, if_match):
    user = authorize(db, request, campus_id, "catalog_edit")
    revision = get_draft(db, campus_id, revision_id)
    if payload and payload.entity != entity:
        raise DomainError("invalid_input", "Catalog entity and payload type do not match.")
    version = claim_version(db, revision, if_match)
    return user, revision, version


@router.post(
    "/campuses/{campus_id}/drafts/{revision_id}/catalog/{entity}",
    response_model=MutationOut,
    status_code=201,
)
def create_catalog(
    campus_id: UUID,
    revision_id: UUID,
    entity: Entity,
    payload: CatalogWrite,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    user, revision, version = edit_context(
        db, request, campus_id, revision_id, entity, payload, if_match
    )
    row, before, after = write_record(db, revision, payload)
    audit(
        db,
        f"catalog.{entity}.create",
        request.state.request_id,
        actor_id=user.id,
        campus_id=campus_id,
        revision_id=revision.id,
        resource_id=row.id,
        before=before,
        after=after,
    )
    return MutationOut(id=row.id, revision_version=version)


@router.put(
    "/campuses/{campus_id}/drafts/{revision_id}/catalog/{entity}/{resource_id}",
    response_model=MutationOut,
)
def update_catalog(
    campus_id: UUID,
    revision_id: UUID,
    entity: Entity,
    resource_id: UUID,
    payload: CatalogWrite,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    user, revision, version = edit_context(
        db, request, campus_id, revision_id, entity, payload, if_match
    )
    row, before, after = write_record(db, revision, payload, resource_id)
    audit(
        db,
        f"catalog.{entity}.update",
        request.state.request_id,
        actor_id=user.id,
        campus_id=campus_id,
        revision_id=revision.id,
        resource_id=row.id,
        before=before,
        after=after,
    )
    return MutationOut(id=row.id, revision_version=version)


@router.delete(
    "/campuses/{campus_id}/drafts/{revision_id}/catalog/{entity}/{resource_id}",
    response_model=MutationOut,
)
def delete_catalog(
    campus_id: UUID,
    revision_id: UUID,
    entity: Entity,
    resource_id: UUID,
    request: Request,
    db: DB,
    if_match: Version = None,
):
    user, revision, version = edit_context(
        db, request, campus_id, revision_id, entity, None, if_match
    )
    before = remove_record(db, revision, entity, resource_id)
    audit(
        db,
        f"catalog.{entity}.delete",
        request.state.request_id,
        actor_id=user.id,
        campus_id=campus_id,
        revision_id=revision.id,
        resource_id=resource_id,
        before=before,
    )
    return MutationOut(id=resource_id, revision_version=version)


@router.get("/campuses/{campus_id}/audit", response_model=list[AuditOut])
def events(campus_id: UUID, request: Request, db: DB, offset: int = Query(0, ge=0, le=100000)):
    authorize(db, request, campus_id, "audit_read")
    return [
        AuditOut(**{name: getattr(event, name) for name in AuditOut.model_fields})
        for event in db.scalars(
            select(AuditEvent)
            .where(AuditEvent.campus_id == campus_id)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id)
            .limit(50)
            .offset(offset)
        )
    ]


def user_output(db, user, campus_id):
    return UserOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        roles=list(
            db.scalars(
                select(RoleAssignment.role)
                .where(RoleAssignment.user_id == user.id, RoleAssignment.campus_id == campus_id)
                .order_by(RoleAssignment.role)
            )
        ),
    )


@router.get("/campuses/{campus_id}/users", response_model=list[UserOut])
def users(campus_id: UUID, request: Request, db: DB, offset: int = Query(0, ge=0, le=10000)):
    authorize(db, request, campus_id, "user_admin")
    ids = select(RoleAssignment.user_id).where(RoleAssignment.campus_id == campus_id)
    return [
        user_output(db, user, campus_id)
        for user in db.scalars(
            select(User).where(User.id.in_(ids)).order_by(User.username).offset(offset).limit(50)
        )
    ]


@router.post("/campuses/{campus_id}/users", response_model=UserOut, status_code=201)
def create_user(campus_id: UUID, payload: UserInput, request: Request, db: DB):
    actor = authorize(db, request, campus_id, "user_admin")
    if db.scalar(select(User.id).where(User.username == payload.username)):
        raise DomainError("conflict", "Username is unavailable. Choose another username.", 409)
    user = User(
        id=uuid4(),
        username=payload.username,
        display_name=payload.display_name,
        password_hash=HASHER.hash(payload.password.get_secret_value()),
    )
    db.add(user)
    db.flush()
    db.add(RoleAssignment(user_id=user.id, campus_id=campus_id, role=payload.role))
    db.flush()
    audit(
        db,
        "identity.create",
        request.state.request_id,
        actor_id=actor.id,
        campus_id=campus_id,
        resource_id=user.id,
        after={"username": user.username, "role": payload.role},
    )
    return user_output(db, user, campus_id)


@router.put("/campuses/{campus_id}/users/{user_id}/role", response_model=UserOut)
def replace_role(campus_id: UUID, user_id: UUID, payload: RoleInput, request: Request, db: DB):
    actor = authorize(db, request, campus_id, "user_admin")
    # Serialize role changes so two administrators cannot remove the last administrator.
    db.execute(select(Campus.id).where(Campus.id == campus_id).with_for_update())
    # Re-authorize after acquiring the lock: a concurrent request may have revoked the actor.
    authorize(db, request, campus_id, "user_admin")
    grants = db.scalars(
        select(RoleAssignment).where(
            RoleAssignment.campus_id == campus_id, RoleAssignment.user_id == user_id
        )
    ).all()
    if not grants:
        raise DomainError("location_not_found", "User not found in this campus.", 404)
    roles = [grant.role for grant in grants]
    if "system_admin" in roles and payload.role != "system_admin":
        others = db.scalar(
            select(func.count())
            .select_from(RoleAssignment)
            .join(User, User.id == RoleAssignment.user_id)
            .where(
                RoleAssignment.campus_id == campus_id,
                RoleAssignment.role == "system_admin",
                User.active,
                RoleAssignment.user_id != user_id,
            )
        )
        if not others:
            raise DomainError(
                "conflict",
                "At least one active system administrator must remain in this campus.",
                409,
            )
    for grant in grants:
        db.delete(grant)
    db.flush()
    db.add(RoleAssignment(user_id=user_id, campus_id=campus_id, role=payload.role))
    db.flush()
    audit(
        db,
        "identity.roles",
        request.state.request_id,
        actor_id=actor.id,
        campus_id=campus_id,
        resource_id=user_id,
        before={"roles": roles},
        after={"roles": [payload.role]},
    )
    return user_output(db, db.get(User, user_id), campus_id)


@router.post("/campuses/{campus_id}/muj-setup", status_code=201)
def setup_muj(campus_id: UUID, request: Request, db: DB):
    # Scoped system administrators can explicitly provision this one pinned, separate campus.
    # No arbitrary campus/role payload, account bootstrap, overwrite, approval or publication.
    from app.services.muj_setup import provision

    actor = authorize(db, request, campus_id, "user_admin")
    return provision(db, actor, request.state.request_id)
