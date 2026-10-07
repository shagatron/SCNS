"""Floor-local topology is distinct from the outdoor geographic routing graph."""

import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, RevisionEntity, revision_fk


def ref(table, field):
    return ForeignKeyConstraint(
        ["dataset_revision_id", field], [f"{table}.dataset_revision_id", f"{table}.id"]
    )


class IndoorEntity(RevisionEntity):
    floor_id: Mapped[uuid.UUID] = mapped_column(UUID)
    frame_id: Mapped[uuid.UUID] = mapped_column(UUID)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID)
    evidence: Mapped[str] = mapped_column(Text)
    verified_on: Mapped[date | None] = mapped_column(Date)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id"))
    visibility: Mapped[str] = mapped_column(String(16))


def common():
    return (
        revision_fk(),
        ref("floors", "floor_id"),
        ref("coordinate_frames", "frame_id"),
        ref("source_assets", "source_id"),
        CheckConstraint("visibility IN ('public','restricted')"),
    )


class Room(IndoorEntity, Base):
    __tablename__ = "indoor_rooms"
    code: Mapped[str] = mapped_column(String(32))
    x_px: Mapped[float] = mapped_column(Float)
    y_px: Mapped[float] = mapped_column(Float)
    __table_args__ = (
        *common(),
        ref("places", "id"),
        UniqueConstraint("dataset_revision_id", "floor_id", "code"),
        UniqueConstraint("dataset_revision_id", "floor_id", "id"),
        CheckConstraint(
            "x_px >= 0 AND y_px >= 0 AND x_px < 'Infinity'::float AND y_px < 'Infinity'::float"
        ),
    )


class IndoorNode(IndoorEntity, Base):
    __tablename__ = "indoor_nodes"
    kind: Mapped[str] = mapped_column(String(16))
    label: Mapped[str] = mapped_column(String(160))
    x_px: Mapped[float] = mapped_column(Float)
    y_px: Mapped[float] = mapped_column(Float)
    __table_args__ = (
        *common(),
        UniqueConstraint("dataset_revision_id", "floor_id", "id"),
        CheckConstraint("kind IN ('corridor','junction','door','entrance')"),
        CheckConstraint(
            "x_px >= 0 AND y_px >= 0 AND x_px < 'Infinity'::float AND y_px < 'Infinity'::float"
        ),
    )


def floor_ref(table, field):
    return ForeignKeyConstraint(
        ["dataset_revision_id", "floor_id", field],
        [f"{table}.dataset_revision_id", f"{table}.floor_id", f"{table}.id"],
    )


class IndoorEdge(IndoorEntity, Base):
    __tablename__ = "indoor_edges"
    physical_path_id: Mapped[uuid.UUID] = mapped_column(UUID)
    from_node_id: Mapped[uuid.UUID] = mapped_column(UUID)
    to_node_id: Mapped[uuid.UUID] = mapped_column(UUID)
    kind: Mapped[str] = mapped_column(String(16))
    polyline: Mapped[list] = mapped_column(JSONB)
    distance_m: Mapped[float | None] = mapped_column(Float)
    distance_status: Mapped[str] = mapped_column(String(16))
    accessibility_status: Mapped[str] = mapped_column(String(32))
    width_m: Mapped[float | None] = mapped_column(Float)
    slope_percent: Mapped[float | None] = mapped_column(Float)
    step_count: Mapped[int | None] = mapped_column()
    surface: Mapped[str | None] = mapped_column(String(120))
    is_open: Mapped[bool] = mapped_column(Boolean)
    __table_args__ = (
        *common(),
        floor_ref("indoor_nodes", "from_node_id"),
        floor_ref("indoor_nodes", "to_node_id"),
        CheckConstraint("from_node_id <> to_node_id"),
        CheckConstraint("kind IN ('corridor','door')"),
        CheckConstraint("jsonb_array_length(polyline) BETWEEN 2 AND 500"),
        CheckConstraint("distance_status IN ('calibrated','unknown')"),
        CheckConstraint(
            "(distance_status='unknown' AND distance_m IS NULL) OR (distance_status='calibrated' AND distance_m > 0 AND distance_m < 'Infinity'::float)"
        ),
        CheckConstraint("accessibility_status IN ('unknown','not_step_free','verified_step_free')"),
        CheckConstraint("width_m IS NULL OR (width_m > 0 AND width_m < 'Infinity'::float)"),
        CheckConstraint(
            "slope_percent IS NULL OR (slope_percent >= 0 AND slope_percent < 'Infinity'::float)"
        ),
        CheckConstraint("step_count IS NULL OR step_count >= 0"),
        CheckConstraint(
            "accessibility_status <> 'verified_step_free' OR step_count IS NULL OR step_count=0"
        ),
    )


class IndoorAccess(IndoorEntity, Base):
    __tablename__ = "indoor_access"
    room_id: Mapped[uuid.UUID] = mapped_column(UUID)
    node_id: Mapped[uuid.UUID] = mapped_column(UUID)
    role: Mapped[str] = mapped_column(String(16))
    priority: Mapped[int] = mapped_column()
    accessibility_status: Mapped[str] = mapped_column(String(32))
    is_open: Mapped[bool] = mapped_column(Boolean)
    __table_args__ = (
        *common(),
        floor_ref("indoor_rooms", "room_id"),
        floor_ref("indoor_nodes", "node_id"),
        UniqueConstraint("dataset_revision_id", "room_id", "node_id"),
        CheckConstraint("role='door'"),
        CheckConstraint("priority BETWEEN 0 AND 1000"),
        CheckConstraint("accessibility_status IN ('unknown','not_step_free','verified_step_free')"),
    )
