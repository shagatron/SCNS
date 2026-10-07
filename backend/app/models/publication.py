"""Exact-content review evidence and immutable public release artifacts."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, RevisionEntity, revision_fk


class SourceAsset(RevisionEntity, Base):
    __tablename__ = "source_assets"
    title: Mapped[str] = mapped_column(String(160))
    rights: Mapped[str] = mapped_column(String(16))
    provenance: Mapped[str] = mapped_column(Text)
    attribution: Mapped[str] = mapped_column(String(500))
    uploader_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admin_users.id"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id"))
    original: Mapped[bytes | None] = mapped_column(LargeBinary)
    original_checksum: Mapped[str | None] = mapped_column(String(64))
    derivative: Mapped[dict | None] = mapped_column(JSONB)
    __table_args__ = (
        revision_fk(),
        CheckConstraint("rights IN ('synthetic','authorized','restricted')"),
        CheckConstraint("approved_by IS NULL OR approved_by <> uploader_id"),
    )


class ValidationRun(Base):
    __tablename__ = "validation_runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    campus_id: Mapped[uuid.UUID] = mapped_column(UUID)
    revision_id: Mapped[uuid.UUID] = mapped_column(UUID)
    edit_version: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    validator: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admin_users.id"))
    report: Mapped[dict] = mapped_column(JSONB)
    evidence: Mapped[list] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        ForeignKeyConstraint(
            ["campus_id", "revision_id"], ["dataset_revisions.campus_id", "dataset_revisions.id"]
        ),
    )


class ReviewSubmission(Base):
    __tablename__ = "review_submissions"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    campus_id: Mapped[uuid.UUID] = mapped_column(UUID)
    revision_id: Mapped[uuid.UUID] = mapped_column(UUID)
    validation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("validation_runs.id"), unique=True)
    submitter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admin_users.id"))
    edit_version: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    acknowledgements: Mapped[dict] = mapped_column(JSONB)
    __table_args__ = (
        ForeignKeyConstraint(
            ["campus_id", "revision_id"], ["dataset_revisions.campus_id", "dataset_revisions.id"]
        ),
        CheckConstraint("status IN ('submitted','approved','rejected','withdrawn','published')"),
    )


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("review_submissions.id"))
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admin_users.id"))
    decision: Mapped[str] = mapped_column(String(16))
    notes: Mapped[str] = mapped_column(Text)
    acknowledgements: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (CheckConstraint("decision IN ('approve','reject','withdraw')"),)


class ReleaseArtifact(Base):
    __tablename__ = "release_artifacts"
    release_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    campus_id: Mapped[uuid.UUID] = mapped_column(UUID)
    checksum: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict] = mapped_column(JSONB)
    publisher_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admin_users.id"))
    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("review_submissions.id"))
    __table_args__ = (
        ForeignKeyConstraint(["campus_id", "release_id"], ["releases.campus_id", "releases.id"]),
    )


class ReleaseAction(Base):
    __tablename__ = "release_actions"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    campus_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campuses.id"))
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admin_users.id"))
    key: Mapped[str] = mapped_column(String(80))
    fingerprint: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSONB)
    __table_args__ = (UniqueConstraint("campus_id", "actor_id", "key"),)
