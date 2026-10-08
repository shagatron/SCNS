from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Point(DTO):
    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float]


class LineString(DTO):
    type: Literal["LineString"] = "LineString"
    coordinates: list[tuple[float, float]]


class Polygon(DTO):
    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[tuple[float, float]]]


class CampusOut(DTO):
    id: UUID
    code: str
    name: str
    timezone: str
    is_demo: bool
    center: Point
    boundary: Polygon


class ReleaseOut(DTO):
    id: UUID
    campus_id: UUID
    dataset_revision_id: UUID
    checksum: str
    published_at: datetime
    version: int
    closure_overlay_version: int = 0
    publication_order: int = 0
    artifact_checksum: str | None = None
    artifact_url: str | None = None


class PlaceOut(DTO):
    id: UUID
    campus_id: UUID
    code: str
    name: str
    kind: str
    description: str
    aliases: list[str]
    building_name: str | None
    point: Point | None
    floor_id: UUID | None = None
    floor_label: str | None = None
    frame_id: UUID | None = None
    room_code: str | None = None
    local_point: dict[str, float] | None = None
    navigation_mode: Literal["outdoor", "indoor_catalog_only", "metric", "directions_only"] = (
        "outdoor"
    )
    routable: bool
    accessibility: Literal["unknown", "synthetic_evidence_only"] = "unknown"


class SearchOut(DTO):
    items: list[PlaceOut]
    total: int
    limit: int
    offset: int
    release_id: UUID


class MapFeature(DTO):
    type: Literal["Feature"] = "Feature"
    id: UUID
    geometry: Point | LineString | Polygon
    properties: dict[str, str | bool]


class MapOut(DTO):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[MapFeature]
    release_id: UUID
    truncated: bool


class PlaceSource(DTO):
    kind: Literal["place"] = "place"
    place_id: UUID


class QRSource(DTO):
    kind: Literal["qr"]
    marker_id: UUID
    expected_marker_version: int = Field(ge=1)
    confirmed: Literal[True]


class RouteRequest(DTO):
    campus_id: UUID
    source: PlaceSource | QRSource = Field(discriminator="kind")
    destination: PlaceSource
    profile: Literal["shortest", "step_free", "fastest"] = "shortest"
    cost_mode: Literal["metric", "directions_only"] = "metric"
    departure_at: AwareDatetime | None = None
    expected_release_id: UUID | None = None
    expected_closure_overlay_version: int | None = Field(default=None, ge=0)

    @field_validator("source", mode="before")
    @classmethod
    def legacy_place_source(cls, value):
        if isinstance(value, dict) and "kind" not in value and "place_id" in value:
            return {"kind": "place", **value}
        return value


class RouteSegment(DTO):
    edge_id: UUID
    from_node_id: UUID
    to_node_id: UUID
    kind: Literal["outdoor", "indoor", "entrance_transition", "stairs", "lift", "ramp"] = "outdoor"
    geometry: LineString | None = None
    polyline: list[list[float]] | None = None
    floor_id: UUID | None = None
    to_floor_id: UUID | None = None
    building_id: UUID | None = None
    frame_id: UUID | None = None
    connector_id: UUID | None = None
    from_local_point: dict[str, float] | None = None
    to_local_point: dict[str, float] | None = None
    distance_status: Literal["measured", "calibrated", "estimated", "unknown"] = "measured"
    estimated_duration_s: float | None = Field(default=None, ge=0)
    distance_m: float | None = Field(default=None, ge=0)
    instruction: str


class RouteFloor(DTO):
    id: UUID
    building_id: UUID
    building_name: str
    label: str
    ordering: float
    frame_id: UUID
    layer_id: UUID
    width_px: int
    height_px: int
    metres_per_pixel: float | None
    navigation_mode: Literal["display_only", "metric", "directions_only"]
    asset_url: str
    attribution: str


class FloorsOut(DTO):
    release_id: UUID
    floors: list[RouteFloor]


class RouteOut(DTO):
    id: UUID
    campus_id: UUID
    release_id: UUID
    dataset_revision_id: UUID
    closure_overlay_version: int = 0
    generated_at: datetime
    departure_at: datetime
    valid_until: datetime | None = None
    restriction_window_end: datetime | None = None
    next_closure_change_at: datetime | None = None
    profile: Literal["shortest", "step_free", "fastest"]
    source_place_id: UUID | None = None
    source_marker_id: UUID | None = None
    source_node_id: UUID | None = None
    destination_place_id: UUID
    source_anchor_id: UUID | None = None
    destination_anchor_id: UUID
    distance_m: float | None = Field(default=None, ge=0)
    estimated_duration_s: float | None = Field(default=None, ge=0)
    known_distance_m: float | None = Field(default=None, ge=0)
    distance_status: Literal["complete", "partial", "unknown"] = "complete"
    cost_mode: Literal["metric", "directions_only"] = "metric"
    cost_units: Literal["metres", "seconds", "traversals"] = "metres"
    optimization_cost: float | None = Field(default=None, ge=0)
    floors: list[RouteFloor] = Field(default_factory=list)
    walking_speed_mps: float
    segments: list[RouteSegment]
    arrival_instruction: str
    warnings: list[str]
    schedule_policy: Literal["static_release_state", "live_overlay_conservative_window"] = (
        "static_release_state"
    )


class ErrorDetail(DTO):
    code: str
    message: str
    request_id: str


class ErrorOut(DTO):
    error: ErrorDetail


class HealthOut(DTO):
    status: Literal["ok"] = "ok"
    database: Literal["ready"] | None = None
