"""Operational inventory, separate from immutable map revisions."""

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


class QRMarker(Base):
    __tablename__ = "qr_markers"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    campus_id: Mapped[UUID] = mapped_column(ForeignKey("campuses.id"), index=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("admin_users.id"))
    key: Mapped[str] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(Integer, default=1)
    label: Mapped[str] = mapped_column(String(160))
    node_kind: Mapped[str] = mapped_column(String(16))
    node_id: Mapped[UUID] = mapped_column()
    release_id: Mapped[UUID] = mapped_column(ForeignKey("releases.id"))
    target_checksum: Mapped[str] = mapped_column(String(64))
    intended_position: Mapped[str] = mapped_column(String(2000))
    installation: Mapped[dict] = mapped_column(JSONB, default=dict)
    state: Mapped[str] = mapped_column(String(24), default="planned")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("campus_id", "created_by", "key"),
        CheckConstraint("version > 0"),
        CheckConstraint("node_kind IN ('outdoor', 'indoor')"),
        CheckConstraint(
            "state IN ('planned', 'active', 'revoked', 'retired', 'needs_verification')"
        ),
        CheckConstraint("state <> 'active' OR installation ? 'verified_by'"),
    )
