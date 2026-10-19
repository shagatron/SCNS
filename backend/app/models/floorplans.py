"""Draft floors/layers and private durable processing; no indoor routing entities."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
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


class Floor(RevisionEntity, Base):
    __tablename__ = "floors"
    building_id: Mapped[uuid.UUID] = mapped_column(UUID)
    code: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(160))
    ordering: Mapped[float] = mapped_column(Float)
    elevation_m: Mapped[float | None] = mapped_column(Float)
    visibility: Mapped[str] = mapped_column(String(16))
    frame_id: Mapped[uuid.UUID | None] = mapped_column(UUID)
    layer_id: Mapped[uuid.UUID | None] = mapped_column(UUID)
    __table_args__ = (
        revision_fk(),
        ForeignKeyConstraint(
            ["dataset_revision_id", "building_id"],
            ["buildings.dataset_revision_id", "buildings.id"],
        ),
        ForeignKeyConstraint(
            ["dataset_revision_id", "frame_id"],
            ["coordinate_frames.dataset_revision_id", "coordinate_frames.id"],
        ),
        ForeignKeyConstraint(
            ["dataset_revision_id", "layer_id", "id"],
            [
                "floorplan_layers.dataset_revision_id",
                "floorplan_layers.id",
                "floorplan_layers.floor_id",
            ],
            use_alter=True,
            name="floor_current_layer_fk",
        ),
        UniqueConstraint("dataset_revision_id", "building_id", "code"),
        CheckConstraint("visibility IN ('public','restricted')"),
        CheckConstraint("ordering > '-Infinity'::float AND ordering < 'Infinity'::float"),
        CheckConstraint(
            "elevation_m IS NULL OR (elevation_m > '-Infinity'::float AND elevation_m < 'Infinity'::float)"
        ),
    )


class MapLayer(RevisionEntity, Base):
    __tablename__ = "floorplan_layers"
    floor_id: Mapped[uuid.UUID] = mapped_column(UUID)
    frame_id: Mapped[uuid.UUID] = mapped_column(UUID)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID)
    page: Mapped[int] = mapped_column(Integer)
    width_px: Mapped[int] = mapped_column(Integer)
    height_px: Mapped[int] = mapped_column(Integer)
    display_width_px: Mapped[int] = mapped_column(Integer)
    display_height_px: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    png: Mapped[bytes] = mapped_column(LargeBinary)
    processing: Mapped[dict] = mapped_column(JSONB)
    __table_args__ = (
        revision_fk(),
        UniqueConstraint("dataset_revision_id", "id", "floor_id"),
        ForeignKeyConstraint(
            ["dataset_revision_id", "floor_id"], ["floors.dataset_revision_id", "floors.id"]
        ),
        ForeignKeyConstraint(
            ["dataset_revision_id", "frame_id"],
            ["coordinate_frames.dataset_revision_id", "coordinate_frames.id"],
        ),
        ForeignKeyConstraint(
            ["dataset_revision_id", "source_id"],
            ["source_assets.dataset_revision_id", "source_assets.id"],
        ),
        CheckConstraint(
            "page > 0 AND width_px > 0 AND height_px > 0 AND display_width_px > 0 AND display_height_px > 0"
        ),
    )


class FloorplanJob(Base):
    __tablename__ = "floorplan_jobs"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    campus_id: Mapped[uuid.UUID] = mapped_column(UUID)
    revision_id: Mapped[uuid.UUID] = mapped_column(UUID)
    floor_id: Mapped[uuid.UUID] = mapped_column(
        UUID
    )  # Historical target, retained after explicit deletion.
    uploader_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admin_users.id"))
    key: Mapped[str] = mapped_column(String(80))
    fingerprint: Mapped[str] = mapped_column(String(64))
    filename: Mapped[str] = mapped_column(String(160))
    media_type: Mapped[str] = mapped_column(String(64))
    original: Mapped[bytes] = mapped_column(LargeBinary)
    original_checksum: Mapped[str] = mapped_column(String(64))
    options: Mapped[dict] = mapped_column(JSONB)
    apply_options: Mapped[dict | None] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(16), default="uploaded")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease: Mapped[uuid.UUID | None] = mapped_column(UUID)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    png: Mapped[bytes | None] = mapped_column(LargeBinary)
    failure: Mapped[str | None] = mapped_column(Text)
    layer_id: Mapped[uuid.UUID | None] = mapped_column(UUID)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        ForeignKeyConstraint(
            ["campus_id", "revision_id"], ["dataset_revisions.campus_id", "dataset_revisions.id"]
        ),
        UniqueConstraint("campus_id", "uploader_id", "key"),
        CheckConstraint(
            "state IN ('uploaded','processing','ready','failed','cancelled','applied')"
        ),
        CheckConstraint("attempts >= 0 AND attempts <= 3"),
    )
