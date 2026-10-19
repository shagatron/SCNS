"""Explicit stops and directed abstract transitions, with nullable measured costs."""

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.api import DTO
from app.schemas.indoor import AccessStatus, Evidence


class FloorRoutingFields(Evidence):
    floor_id: UUID
    layer_id: UUID
    enabled: bool = False
    mode: Literal["metric", "directions_only"] = "metric"


class ConnectorFields(Evidence):
    building_id: UUID
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    label: str = Field(min_length=1, max_length=160)
    kind: Literal["stairs", "lift", "ramp", "entrance"]
    operational_status: Literal["available", "unavailable", "unknown"] = "unknown"

    @field_validator("label")
    @classmethod
    def meaningful(cls, value):
        if not value.strip():
            raise ValueError("Use a meaningful connector label")
        return value.strip()

    @field_validator("code")
    @classmethod
    def uppercase(cls, value):
        return value.upper()


class ConnectorStopFields(Evidence):
    connector_id: UUID
    floor_id: UUID
    layer_id: UUID
    node_id: UUID


class TraversalFields(Evidence):
    connector_id: UUID
    physical_path_id: UUID
    distance_m: float | None = Field(default=None, gt=0, le=100000, allow_inf_nan=False)
    distance_status: Literal["measured", "estimated", "unknown"] = "unknown"
    horizontal_distance_m: float | None = Field(default=None, ge=0, le=100000, allow_inf_nan=False)
    vertical_rise_m: float | None = Field(default=None, ge=0, le=10000, allow_inf_nan=False)
    baseline_traversal_s: float | None = Field(default=None, gt=0, le=86400, allow_inf_nan=False)
    wait_estimate_s: float | None = Field(default=None, ge=0, le=86400, allow_inf_nan=False)
    uncertainty_note: str = Field(default="", max_length=1000)
    accessibility_status: AccessStatus = "unknown"
    width_m: float | None = Field(default=None, gt=0, le=100, allow_inf_nan=False)
    slope_percent: float | None = Field(default=None, ge=0, le=1000, allow_inf_nan=False)
    step_count: int | None = Field(default=None, ge=0, le=10000)
    surface: str | None = Field(default=None, max_length=120)
    is_open: bool = True

    @model_validator(mode="after")
    def costs(self):
        if (self.distance_m is None) != (self.distance_status == "unknown"):
            raise ValueError(
                "Unknown distance must be NULL; known distance needs an explicit status"
            )
        if self.distance_m is not None and any(
            v is not None and v > self.distance_m
            for v in (self.horizontal_distance_m, self.vertical_rise_m)
        ):
            raise ValueError("A measured component cannot exceed full traversal distance")
        if self.accessibility_status == "verified_step_free" and (self.step_count or 0) > 0:
            raise ValueError("Positive steps cannot claim verified step-free")
        return self


class ConnectorPathFields(TraversalFields):
    from_stop_id: UUID
    to_stop_id: UUID


class EntranceTransitionFields(TraversalFields):
    stop_id: UUID
    anchor_id: UUID
    direction: Literal["in", "out"]
    priority: int = Field(default=0, ge=0, le=1000)


class FloorRoutingChange(DTO):
    entity: Literal["policies"]
    id: UUID
    data: FloorRoutingFields | None = None


class ConnectorChange(DTO):
    entity: Literal["connectors"]
    id: UUID
    data: ConnectorFields | None = None


class StopChange(DTO):
    entity: Literal["stops"]
    id: UUID
    data: ConnectorStopFields | None = None


class PathChange(DTO):
    entity: Literal["paths"]
    id: UUID
    data: ConnectorPathFields | None = None


class TransitionChange(DTO):
    entity: Literal["transitions"]
    id: UUID
    data: EntranceTransitionFields | None = None


class ConnectionsPatch(DTO):
    changes: list[
        FloorRoutingChange | ConnectorChange | StopChange | PathChange | TransitionChange
    ] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique_keys(self):
        keys = [(c.entity, c.id) for c in self.changes]
        if len(keys) != len(set(keys)):
            raise ValueError("Each entity/ID may occur once per patch")
        return self
