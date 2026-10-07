"""Revision keys are composite: logical UUIDs remain stable across releases."""

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Campus(Base):
    __tablename__ = "campuses"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    timezone: Mapped[str] = mapped_column(String(64))
    is_demo: Mapped[bool] = mapped_column(Boolean)
    center = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    boundary = mapped_column(Geometry("POLYGON", srid=4326), nullable=False)


class Revision(Base):
    __tablename__ = "dataset_revisions"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    campus_id: Mapped[uuid.UUID] = mapped_column(UUID)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    checksum: Mapped[str | None] = mapped_column(String(64))
    edit_version: Mapped[int] = mapped_column(Integer, server_default="1")
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("campus_id", "id"),
        UniqueConstraint("campus_id", "version"),
        ForeignKeyConstraint(["campus_id"], ["campuses.id"]),
        ForeignKeyConstraint(
            ["campus_id", "parent_id"], ["dataset_revisions.campus_id", "dataset_revisions.id"]
        ),
        CheckConstraint("status IN ('draft', 'review', 'frozen')"),
        CheckConstraint(
            "status <> 'frozen' OR checksum IS NOT NULL", name="frozen_checksum_required"
        ),
    )


class RevisionEntity:
    dataset_revision_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    campus_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False)


def revision_fk():
    return ForeignKeyConstraint(
        ["campus_id", "dataset_revision_id"],
        ["dataset_revisions.campus_id", "dataset_revisions.id"],
    )


class Frame(RevisionEntity, Base):
    __tablename__ = "coordinate_frames"
    code: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))
    width_px: Mapped[int | None] = mapped_column(Integer)
    height_px: Mapped[int | None] = mapped_column(Integer)
    metres_per_pixel: Mapped[float | None] = mapped_column(Float)
    calibration: Mapped[dict | None] = mapped_column(JSONB)
    __table_args__ = (
        revision_fk(),
        CheckConstraint(
            "kind <> 'indoor' OR (width_px IS NOT NULL AND height_px IS NOT NULL)",
            name="indoor_frame_dimensions_required",
        ),
        CheckConstraint("kind IN ('outdoor', 'indoor')"),
        CheckConstraint(
            "(kind = 'outdoor' AND width_px IS NULL AND height_px IS NULL AND metres_per_pixel IS NULL) OR (kind = 'indoor' AND width_px > 0 AND height_px > 0)"
        ),
        CheckConstraint(
            "metres_per_pixel IS NULL OR (metres_per_pixel > 0 AND metres_per_pixel < 'Infinity'::float)"
        ),
    )


class Building(RevisionEntity, Base):
    __tablename__ = "buildings"
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(160))
    footprint = mapped_column(Geometry("POLYGON", srid=4326), nullable=False)
    visibility: Mapped[str] = mapped_column(String(16), default="public")
    __table_args__ = (
        revision_fk(),
        UniqueConstraint("dataset_revision_id", "code"),
    )


class Place(RevisionEntity, Base):
    __tablename__ = "places"
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text)
    aliases: Mapped[list] = mapped_column(JSONB)
    search_text: Mapped[str] = mapped_column(Text, index=True)
    building_id: Mapped[uuid.UUID | None] = mapped_column(UUID)
    visibility: Mapped[str] = mapped_column(String(16))
    point = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    __table_args__ = (
        revision_fk(),
        UniqueConstraint("dataset_revision_id", "code"),
        ForeignKeyConstraint(
            ["dataset_revision_id", "building_id"],
            ["buildings.dataset_revision_id", "buildings.id"],
        ),
        CheckConstraint("visibility IN ('public', 'restricted')"),
    )


class Node(RevisionEntity, Base):
    __tablename__ = "navigation_nodes"
    frame_id: Mapped[uuid.UUID] = mapped_column(UUID)
    label: Mapped[str] = mapped_column(String(160))
    visibility: Mapped[str] = mapped_column(String(16))
    point = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    x_px: Mapped[float | None] = mapped_column(Float)
    y_px: Mapped[float | None] = mapped_column(Float)
    __table_args__ = (
        revision_fk(),
        ForeignKeyConstraint(
            ["dataset_revision_id", "frame_id"],
            ["coordinate_frames.dataset_revision_id", "coordinate_frames.id"],
        ),
        CheckConstraint(
            "(point IS NOT NULL AND x_px IS NULL AND y_px IS NULL) OR (point IS NULL AND x_px >= 0 AND y_px >= 0 AND x_px < 'Infinity'::float AND y_px < 'Infinity'::float)"
        ),
        CheckConstraint("visibility IN ('public', 'restricted')"),
    )


class Edge(RevisionEntity, Base):
    __tablename__ = "navigation_edges"
    physical_path_id: Mapped[uuid.UUID] = mapped_column(UUID)
    from_node_id: Mapped[uuid.UUID] = mapped_column(UUID)
    to_node_id: Mapped[uuid.UUID] = mapped_column(UUID)
    frame_id: Mapped[uuid.UUID] = mapped_column(UUID)
    kind: Mapped[str] = mapped_column(String(32))
    geometry = mapped_column(Geometry("LINESTRING", srid=4326), nullable=False)
    distance_m: Mapped[float] = mapped_column(Float)
    distance_status: Mapped[str] = mapped_column(String(16))
    accessibility_status: Mapped[str] = mapped_column(String(32))
    visibility: Mapped[str] = mapped_column(String(16))
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    evidence: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        revision_fk(),
        ForeignKeyConstraint(
            ["dataset_revision_id", "from_node_id"],
            ["navigation_nodes.dataset_revision_id", "navigation_nodes.id"],
        ),
        ForeignKeyConstraint(
            ["dataset_revision_id", "to_node_id"],
            ["navigation_nodes.dataset_revision_id", "navigation_nodes.id"],
        ),
        ForeignKeyConstraint(
            ["dataset_revision_id", "frame_id"],
            ["coordinate_frames.dataset_revision_id", "coordinate_frames.id"],
        ),
        CheckConstraint("from_node_id <> to_node_id"),
        CheckConstraint("distance_m > 0 AND distance_m < 'Infinity'::float"),
        CheckConstraint("distance_status IN ('measured', 'calibrated', 'estimated')"),
        CheckConstraint("kind IN ('walkway', 'ramp', 'stairs')"),
        CheckConstraint(
            "accessibility_status IN ('verified_step_free', 'not_step_free', 'unknown')"
        ),
        CheckConstraint("visibility IN ('public', 'restricted')"),
    )


class Anchor(RevisionEntity, Base):
    __tablename__ = "place_anchors"
    place_id: Mapped[uuid.UUID] = mapped_column(UUID)
    node_id: Mapped[uuid.UUID] = mapped_column(UUID)
    accessibility_status: Mapped[str] = mapped_column(String(32))
    accessibility_evidence: Mapped[str] = mapped_column(Text, server_default="")
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (
        revision_fk(),
        ForeignKeyConstraint(
            ["dataset_revision_id", "place_id"], ["places.dataset_revision_id", "places.id"]
        ),
        ForeignKeyConstraint(
            ["dataset_revision_id", "node_id"],
            ["navigation_nodes.dataset_revision_id", "navigation_nodes.id"],
        ),
        UniqueConstraint("dataset_revision_id", "place_id", "node_id"),
        CheckConstraint(
            "accessibility_status IN ('verified_step_free', 'not_step_free', 'unknown')"
        ),
    )


class Release(Base):
    __tablename__ = "releases"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    campus_id: Mapped[uuid.UUID] = mapped_column(UUID)
    dataset_revision_id: Mapped[uuid.UUID] = mapped_column(UUID, unique=True)
    checksum: Mapped[str] = mapped_column(String(64))
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    __table_args__ = (
        revision_fk(),
        UniqueConstraint("campus_id", "id"),
    )


class ActiveRelease(Base):
    __tablename__ = "active_releases"
    campus_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    audience: Mapped[str] = mapped_column(String(16), primary_key=True, default="public")
    release_id: Mapped[uuid.UUID] = mapped_column(UUID)
    __table_args__ = (
        ForeignKeyConstraint(["campus_id", "release_id"], ["releases.campus_id", "releases.id"]),
        CheckConstraint("audience = 'public'"),
    )
