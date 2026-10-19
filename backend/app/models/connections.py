"""Explicit cross-frame relationships; no geometry is fabricated between frames."""

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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, RevisionEntity, revision_fk
from app.models.indoor import IndoorEntity, common, floor_ref, ref


class FloorRouting(IndoorEntity, Base):
    __tablename__ = "floor_routing"
    enabled: Mapped[bool] = mapped_column(Boolean)
    mode: Mapped[str] = mapped_column(String(24))
    __table_args__ = (
        *common(),
        CheckConstraint(
            "verified_on IS NULL OR (length(trim(evidence))>=10 AND verified_by IS NOT NULL)"
        ),
        UniqueConstraint("dataset_revision_id", "floor_id"),
        CheckConstraint("id=floor_id"),
        CheckConstraint("NOT enabled OR verified_on IS NOT NULL"),
        CheckConstraint("mode IN ('metric','directions_only')"),
    )


class VerifiedEntity(RevisionEntity):
    evidence: Mapped[str] = mapped_column(Text)
    verified_on: Mapped[date | None] = mapped_column(Date)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id"))
    visibility: Mapped[str] = mapped_column(String(16))


class Connector(VerifiedEntity, Base):
    __tablename__ = "connectors"
    building_id: Mapped[uuid.UUID] = mapped_column(UUID)
    code: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(24))
    operational_status: Mapped[str] = mapped_column(String(24))
    __table_args__ = (
        revision_fk(),
        CheckConstraint(
            "verified_on IS NULL OR (length(trim(evidence))>=10 AND verified_by IS NOT NULL)"
        ),
        ref("buildings", "building_id"),
        UniqueConstraint("dataset_revision_id", "building_id", "code"),
        CheckConstraint("kind IN ('stairs','lift','ramp','entrance')"),
        CheckConstraint("operational_status IN ('available','unavailable','unknown')"),
        CheckConstraint("visibility IN ('public','restricted')"),
    )


class ConnectorStop(IndoorEntity, Base):
    __tablename__ = "connector_stops"
    connector_id: Mapped[uuid.UUID] = mapped_column(UUID)
    node_id: Mapped[uuid.UUID] = mapped_column(UUID)
    __table_args__ = (
        *common(),
        CheckConstraint(
            "verified_on IS NULL OR (length(trim(evidence))>=10 AND verified_by IS NOT NULL)"
        ),
        ref("connectors", "connector_id"),
        floor_ref("indoor_nodes", "node_id"),
        UniqueConstraint("dataset_revision_id", "connector_id", "id"),
        UniqueConstraint("dataset_revision_id", "connector_id", "node_id"),
    )


def stop_ref(field):
    return ForeignKeyConstraint(
        ["dataset_revision_id", "connector_id", field],
        [
            "connector_stops.dataset_revision_id",
            "connector_stops.connector_id",
            "connector_stops.id",
        ],
    )


class Traversal(VerifiedEntity):
    connector_id: Mapped[uuid.UUID] = mapped_column(UUID)
    physical_path_id: Mapped[uuid.UUID] = mapped_column(UUID)
    distance_m: Mapped[float | None] = mapped_column(Float)
    distance_status: Mapped[str] = mapped_column(String(16))
    horizontal_distance_m: Mapped[float | None] = mapped_column(Float)
    vertical_rise_m: Mapped[float | None] = mapped_column(Float)
    baseline_traversal_s: Mapped[float | None] = mapped_column(Float)
    wait_estimate_s: Mapped[float | None] = mapped_column(Float)
    uncertainty_note: Mapped[str] = mapped_column(String(1000))
    accessibility_status: Mapped[str] = mapped_column(String(32))
    width_m: Mapped[float | None] = mapped_column(Float)
    slope_percent: Mapped[float | None] = mapped_column(Float)
    step_count: Mapped[int | None] = mapped_column()
    surface: Mapped[str | None] = mapped_column(String(120))
    is_open: Mapped[bool] = mapped_column(Boolean)


def traversal_checks():
    return (
        revision_fk(),
        CheckConstraint(
            "verified_on IS NULL OR (length(trim(evidence))>=10 AND verified_by IS NOT NULL)"
        ),
        ref("connectors", "connector_id"),
        CheckConstraint("visibility IN ('public','restricted')"),
        CheckConstraint("distance_status IN ('measured','estimated','unknown')"),
        CheckConstraint(
            "(distance_status='unknown' AND distance_m IS NULL) OR (distance_status<>'unknown' AND distance_m>0 AND distance_m<'Infinity'::float)"
        ),
        *(
            CheckConstraint(f"{key} IS NULL OR ({key} >= 0 AND {key} < 'Infinity'::float)")
            for key in (
                "horizontal_distance_m",
                "vertical_rise_m",
                "wait_estimate_s",
                "slope_percent",
            )
        ),
        *(
            CheckConstraint(f"{key} IS NULL OR ({key} > 0 AND {key} < 'Infinity'::float)")
            for key in ("baseline_traversal_s", "width_m")
        ),
        CheckConstraint("step_count IS NULL OR step_count>=0"),
        CheckConstraint("accessibility_status IN ('unknown','not_step_free','verified_step_free')"),
        CheckConstraint(
            "accessibility_status<>'verified_step_free' OR step_count IS NULL OR step_count=0"
        ),
    )


class ConnectorPath(Traversal, Base):
    __tablename__ = "connector_paths"
    from_stop_id: Mapped[uuid.UUID] = mapped_column(UUID)
    to_stop_id: Mapped[uuid.UUID] = mapped_column(UUID)
    __table_args__ = (
        *traversal_checks(),
        stop_ref("from_stop_id"),
        stop_ref("to_stop_id"),
        CheckConstraint("from_stop_id<>to_stop_id"),
    )


class EntranceTransition(Traversal, Base):
    __tablename__ = "entrance_transitions"
    stop_id: Mapped[uuid.UUID] = mapped_column(UUID)
    anchor_id: Mapped[uuid.UUID] = mapped_column(UUID)
    direction: Mapped[str] = mapped_column(String(8))
    priority: Mapped[int] = mapped_column()
    __table_args__ = (
        *traversal_checks(),
        stop_ref("stop_id"),
        ref("place_anchors", "anchor_id"),
        CheckConstraint("direction IN ('in','out')"),
        CheckConstraint("priority BETWEEN 0 AND 1000"),
    )
