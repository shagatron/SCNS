import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Request
from sqlalchemy import case, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import DomainError
from app.models import Campus
from app.models.admin import AdminSession, AuditEvent, LoginThrottle, RoleAssignment, User
from app.schemas.admin import GrantOut, SessionOut

COOKIE = "scns_admin"
COOKIE_PATH = "/api/v1/admin"
HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = HASHER.hash(secrets.token_urlsafe(32))
PERMISSIONS = {
    "editor": {
        "qr_read",
        "dashboard",
        "draft_read",
        "draft_create",
        "catalog_edit",
        "import_read",
        "import_write",
        "review_submit",
    },
    "reviewer_publisher": {
        "qr_read",
        "dashboard",
        "draft_read",
        "audit_read",
        "import_read",
        "review_read",
        "review_decide",
        "release_publish",
        "source_approve",
    },
    "operations": {"dashboard", "qr_read", "qr_manage"},
    "system_admin": {
        "qr_read",
        "qr_manage",
        "dashboard",
        "draft_read",
        "draft_create",
        "catalog_edit",
        "audit_read",
        "user_admin",
        "review_read",
        "review_submit",
        "review_decide",
        "release_publish",
        "source_approve",
        "import_read",
        "import_write",
    },
}


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_token(token: str) -> str:
    return hmac.new(token.encode(), b"scns-admin-csrf-v1", hashlib.sha256).hexdigest()


def audit(
    db: Session,
    action: str,
    request_id: str,
    *,
    actor_id=None,
    campus_id=None,
    revision_id=None,
    resource_id=None,
    before=None,
    after=None,
):
    db.add(
        AuditEvent(
            action=action,
            request_id=request_id,
            actor_id=actor_id,
            campus_id=campus_id,
            revision_id=revision_id,
            resource_id=resource_id,
            before=before,
            after=after,
        )
    )


def require_origin(request: Request):
    # Origin is mandatory even on login, preventing login CSRF; no forwarded headers trusted.
    if request.headers.get("origin") not in get_settings().allowed_origins:
        raise DomainError("access_denied", "This request origin is not allowed.", 403)


def authenticated(db: Session, request: Request) -> tuple[User, AdminSession, str]:
    token = request.cookies.get(COOKIE, "")
    if not 40 <= len(token) <= 100:
        raise DomainError("authentication_required", "Sign in to continue.", 401)
    session = db.scalar(
        select(AdminSession).where(
            AdminSession.token_hash == digest(token),
            AdminSession.revoked_at.is_(None),
            AdminSession.expires_at > datetime.now(UTC),
        )
    )
    user = db.get(User, session.user_id, populate_existing=True) if session else None
    if user is None or not user.active:
        raise DomainError(
            "authentication_required", "Your session has expired. Sign in again.", 401
        )
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require_origin(request)
        if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), csrf_token(token)):
            raise DomainError(
                "access_denied",
                "The security token is missing or invalid. Reload and try again.",
                403,
            )
    return user, session, token


def permissions(db: Session, user_id: UUID, campus_id: UUID) -> set[str]:
    roles = db.scalars(
        select(RoleAssignment.role).where(
            RoleAssignment.user_id == user_id, RoleAssignment.campus_id == campus_id
        )
    )
    return set().union(*(PERMISSIONS[role] for role in roles))


def authorize(db: Session, request: Request, campus_id: UUID, permission: str) -> User:
    user, _, _ = authenticated(db, request)
    if permission not in permissions(db, user.id, campus_id):
        # Same response for unknown campuses and campuses outside this user's scope.
        raise DomainError(
            "access_denied", "You do not have permission for this campus action.", 403
        )
    return user


def session_output(db: Session, user: User, session: AdminSession, token: str) -> SessionOut:
    rows = db.execute(
        select(Campus, RoleAssignment.role)
        .join(RoleAssignment, RoleAssignment.campus_id == Campus.id)
        .where(RoleAssignment.user_id == user.id)
        .order_by(Campus.name, RoleAssignment.role)
    )
    grants = {}
    for campus, role in rows:
        grant = grants.setdefault(
            campus.id,
            {"campus_id": campus.id, "campus_name": campus.name, "roles": [], "permissions": set()},
        )
        grant["roles"].append(role)
        grant["permissions"].update(PERMISSIONS[role])
    return SessionOut(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        csrf_token=csrf_token(token),
        expires_at=session.expires_at,
        grants=[
            GrantOut(**{**value, "permissions": sorted(value["permissions"])})
            for value in grants.values()
        ],
    )


def throttle(db: Session, key: str, maximum: int) -> bool:
    now = datetime.now(UTC)
    expires = now + timedelta(seconds=get_settings().login_window_seconds)
    stmt = insert(LoginThrottle).values(key=digest(key), attempts=1, expires_at=expires)
    stmt = stmt.on_conflict_do_update(
        index_elements=[LoginThrottle.key],
        set_={
            "attempts": case(
                (LoginThrottle.expires_at <= now, 1), else_=LoginThrottle.attempts + 1
            ),
            "expires_at": case(
                (LoginThrottle.expires_at <= now, expires), else_=LoginThrottle.expires_at
            ),
        },
    ).returning(LoginThrottle.attempts)
    return db.scalar(stmt) <= maximum


def login(db: Session, request: Request, username: str, password: str):
    require_origin(request)
    now = datetime.now(UTC)
    # Expired throttle rows contain only hashes and can be safely discarded.
    db.execute(delete(LoginThrottle).where(LoginThrottle.expires_at < now - timedelta(days=1)))
    ip = request.client.host if request.client else "unknown"
    allowed = throttle(db, "ip:" + ip, get_settings().login_ip_limit)
    if allowed:
        allowed = throttle(db, "account:" + username, get_settings().login_account_limit)
    if not allowed:
        return None, "rate_limited"
    user = db.scalar(select(User).where(User.username == username))
    valid = False
    try:
        valid = HASHER.verify(user.password_hash if user else DUMMY_HASH, password)
    except VerificationError:
        pass
    if not valid or not user or not user.active:
        audit(
            db,
            "auth.login_failed",
            request.state.request_id,
            after={"account_hash": digest(username)},
        )
        return None, "invalid_credentials"
    if HASHER.check_needs_rehash(user.password_hash):
        user.password_hash = HASHER.hash(password)
    previous = request.cookies.get(COOKIE)
    if previous:
        old = db.scalar(
            select(AdminSession).where(
                AdminSession.token_hash == digest(previous), AdminSession.user_id == user.id
            )
        )
        if old:
            old.revoked_at = now
    token = secrets.token_urlsafe(32)
    session = AdminSession(
        user_id=user.id,
        token_hash=digest(token),
        expires_at=now + timedelta(seconds=get_settings().session_ttl_seconds),
    )
    db.add(session)
    db.flush()
    audit(db, "auth.login", request.state.request_id, actor_id=user.id, resource_id=session.id)
    db.execute(delete(LoginThrottle).where(LoginThrottle.key == digest("account:" + username)))
    return (user, session, token), None
