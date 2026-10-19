"""Administrative identity, campus permissions and revision-scoped catalog additions."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, RevisionEntity, revision_fk


class User(Base):
    __tablename__ = "admin_users"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RoleAssignment(Base):
    __tablename__ = "role_assignments"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admin_users.id"), primary_key=True)
    campus_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campuses.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(32), primary_key=True)
    __table_args__ = (
        CheckConstraint("role IN ('editor','reviewer_publisher','operations','system_admin')"),
    )


class AdminSession(Base):
    __tablename__ = "admin_sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admin_users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LoginThrottle(Base):
    __tablename__ = "login_throttles"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class BootstrapState(Base):
    __tablename__ = "admin_bootstrap"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (CheckConstraint("id = 1"),)


class Department(RevisionEntity, Base):
    __tablename__ = "departments"
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    __table_args__ = (revision_fk(), UniqueConstraint("dataset_revision_id", "code"))


class DepartmentPlace(RevisionEntity, Base):
    __tablename__ = "department_places"
    department_id: Mapped[uuid.UUID] = mapped_column(UUID)
    place_id: Mapped[uuid.UUID] = mapped_column(UUID)
    __table_args__ = (
        revision_fk(),
        ForeignKeyConstraint(
            ["dataset_revision_id", "department_id"],
            ["departments.dataset_revision_id", "departments.id"],
        ),
        ForeignKeyConstraint(
            ["dataset_revision_id", "place_id"], ["places.dataset_revision_id", "places.id"]
        ),
        UniqueConstraint("dataset_revision_id", "department_id", "place_id"),
    )


class PlaceAlias(RevisionEntity, Base):
    __tablename__ = "place_aliases"
    place_id: Mapped[uuid.UUID] = mapped_column(UUID)
    value: Mapped[str] = mapped_column(String(160))
    normalized: Mapped[str] = mapped_column(String(160))
    language: Mapped[str] = mapped_column(String(16), default="en")
    __table_args__ = (
        revision_fk(),
        ForeignKeyConstraint(
            ["dataset_revision_id", "place_id"], ["places.dataset_revision_id", "places.id"]
        ),
        UniqueConstraint("dataset_revision_id", "place_id", "normalized", "language"),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id"))
    campus_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("campuses.id"), index=True)
    revision_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("dataset_revisions.id"))
    action: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID)
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    request_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
