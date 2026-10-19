"""Reference pixel polylines, never geographic geometry or client-provided metrics."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator, model_validator

from app.schemas.api import DTO

PixelValue = Annotated[float, Field(ge=0, le=10000, allow_inf_nan=False)]
PixelPair = Annotated[list[PixelValue], Field(min_length=2, max_length=2)]
Visibility = Literal["public", "restricted"]
AccessStatus = Literal["unknown", "not_step_free", "verified_step_free"]


class Evidence(DTO):
    evidence: str = Field(default="", max_length=2000)
    verified_on: date | None = None
    visibility: Visibility = "public"


class RoomFields(Evidence):
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=160)
    kind: Literal["room", "laboratory", "office", "facility", "indoor_destination"] = "room"
    description: str = Field(default="", max_length=4000)
    aliases: list[Annotated[str, StringConstraints(min_length=1, max_length=160)]] = Field(
        default_factory=list, max_length=50
    )
    department_ids: list[UUID] = Field(default_factory=list, max_length=50)
    x_px: PixelValue
    y_px: PixelValue

    @field_validator("code")
    @classmethod
    def room_code(cls, value):
        return value.upper()

    @field_validator("name")
    @classmethod
    def substantive_name(cls, value):
        if not value.strip():
            raise ValueError("Use a meaningful indoor destination name")
        return value.strip()


class IndoorNodeFields(Evidence):
    kind: Literal["corridor", "junction", "door", "entrance"] = "junction"
    label: str = Field(min_length=1, max_length=160)
    x_px: PixelValue
    y_px: PixelValue

    @field_validator("label")
    @classmethod
    def meaningful_label(cls, value):
        if not value.strip():
            raise ValueError("Use a meaningful node label")
        return value.strip()


class IndoorEdgeFields(Evidence):
    physical_path_id: UUID
    from_node_id: UUID
    to_node_id: UUID
    kind: Literal["corridor", "door"] = "corridor"
    polyline: list[PixelPair] = Field(min_length=2, max_length=500)
    accessibility_status: AccessStatus = "unknown"
    width_m: float | None = Field(default=None, gt=0, le=100, allow_inf_nan=False)
    slope_percent: float | None = Field(default=None, ge=0, le=1000, allow_inf_nan=False)
    step_count: int | None = Field(default=None, ge=0, le=10000)
    surface: str | None = Field(default=None, max_length=120)
    is_open: bool = True


class IndoorAccessFields(Evidence):
    room_id: UUID
    node_id: UUID
    role: Literal["door"] = "door"
    priority: int = Field(default=0, ge=0, le=1000)
    accessibility_status: AccessStatus = "unknown"
    is_open: bool = True


class RoomChange(DTO):
    entity: Literal["rooms"]
    id: UUID
    data: RoomFields | None = None


class IndoorNodeChange(DTO):
    entity: Literal["nodes"]
    id: UUID
    data: IndoorNodeFields | None = None


class IndoorEdgeChange(DTO):
    entity: Literal["edges"]
    id: UUID
    data: IndoorEdgeFields | None = None


class IndoorAccessChange(DTO):
    entity: Literal["access"]
    id: UUID
    data: IndoorAccessFields | None = None


class IndoorPatch(DTO):
    layer_id: UUID
    mode: Literal["metric", "directions_only"] = "metric"
    changes: list[RoomChange | IndoorNodeChange | IndoorEdgeChange | IndoorAccessChange] = Field(
        min_length=1, max_length=500
    )

    @model_validator(mode="after")
    def unique_keys(self):
        keys = [(c.entity, c.id) for c in self.changes]
        if len(keys) != len(set(keys)):
            raise ValueError("Each layer/ID may occur once per patch")
        return self
