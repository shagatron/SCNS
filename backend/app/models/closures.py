"""Operational restrictions are independent of immutable map revisions."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class ClosureOverlay(Base):
    __tablename__ = "closure_overlays"
    campus_id: Mapped[UUID] = mapped_column(ForeignKey("campuses.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (CheckConstraint("version >= 0"),)


class Closure(Base):
    __tablename__ = "closures"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    campus_id: Mapped[UUID] = mapped_column(ForeignKey("campuses.id"), index=True)
    target_kind: Mapped[str] = mapped_column(String(24))
    target_id: Mapped[UUID] = mapped_column()
    target_checksum: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(300))
    reason: Mapped[str] = mapped_column(String(1000))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    estimated_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(16), default="closed")
    created_by: Mapped[UUID] = mapped_column(ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reopen_evidence: Mapped[str | None] = mapped_column(String(2000))
    __table_args__ = (
        CheckConstraint("target_kind IN ('outdoor_edge','outdoor_path','indoor_edge','connector')"),
        CheckConstraint("state IN ('closed','unresolved','reopened')"),
        CheckConstraint("estimated_end_at IS NULL OR estimated_end_at > starts_at"),
        CheckConstraint("(state = 'reopened') = (reopened_at IS NOT NULL)"),
    )


class ClosureAction(Base):
    __tablename__ = "closure_actions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    campus_id: Mapped[UUID] = mapped_column(ForeignKey("campuses.id"))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("admin_users.id"))
    key: Mapped[str] = mapped_column(String(80))
    fingerprint: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSONB)
    __table_args__ = (UniqueConstraint("campus_id", "actor_id", "key"),)
