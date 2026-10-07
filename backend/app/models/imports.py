"""Private, durable import staging; public services never read these tables."""

import uuid
from datetime import datetime

from sqlalchemy import (
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


class ImportJob(Base):
    __tablename__ = "import_jobs"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    campus_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("campuses.id"), index=True)
    revision_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("dataset_revisions.id"))
    uploader_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("admin_users.id"))
    applier_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey("admin_users.id"))
    submission_key: Mapped[str] = mapped_column(String(80))
    checksum: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(40))
    filename: Mapped[str] = mapped_column(String(160))
    byte_size: Mapped[int] = mapped_column(Integer)
    options: Mapped[dict] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(24), default="uploaded", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    preview_version: Mapped[int | None] = mapped_column(Integer)
    preview: Mapped[dict | None] = mapped_column(JSONB)
    history: Mapped[list] = mapped_column(JSONB, default=list)
    failure: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("campus_id", "uploader_id", "submission_key"),
        ForeignKeyConstraint(
            ["campus_id", "revision_id"], ["dataset_revisions.campus_id", "dataset_revisions.id"]
        ),
        CheckConstraint(
            "state IN ('uploaded','parsing','preview_ready','validated','committed','failed','cancelled')",
            name="import_state",
        ),
        CheckConstraint("attempts >= 0 AND attempts <= 3", name="import_attempts"),
        CheckConstraint("byte_size > 0", name="import_bytes"),
    )


class ImportBinding(RevisionEntity, Base):
    __tablename__ = "import_bindings"
    entity: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(120))
    record_id: Mapped[uuid.UUID] = mapped_column(UUID)
    __table_args__ = (
        revision_fk(),
        UniqueConstraint("dataset_revision_id", "entity", "external_id"),
    )
