from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


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
    point: Point
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


class RouteRequest(DTO):
    campus_id: UUID
    source: PlaceSource
    destination: PlaceSource
    profile: Literal["shortest", "step_free"] = "shortest"
    departure_at: AwareDatetime | None = None
    expected_release_id: UUID | None = None


class RouteSegment(DTO):
    edge_id: UUID
    from_node_id: UUID
    to_node_id: UUID
    kind: Literal["outdoor"] = "outdoor"
    geometry: LineString
    distance_m: float = Field(ge=0)
    instruction: str


class RouteOut(DTO):
    id: UUID
    campus_id: UUID
    release_id: UUID
    dataset_revision_id: UUID
    closure_overlay_version: int = 0
    generated_at: datetime
    departure_at: datetime
    profile: Literal["shortest", "step_free"]
    source_place_id: UUID
    destination_place_id: UUID
    source_anchor_id: UUID
    destination_anchor_id: UUID
    distance_m: float = Field(ge=0)
    estimated_duration_s: float = Field(ge=0)
    walking_speed_mps: float
    segments: list[RouteSegment]
    arrival_instruction: str
    warnings: list[str]
    schedule_policy: Literal["static_release_state"] = "static_release_state"


class ErrorDetail(DTO):
    code: str
    message: str
    request_id: str


class ErrorOut(DTO):
    error: ErrorDetail


class HealthOut(DTO):
    status: Literal["ok"] = "ok"
    database: Literal["ready"] | None = None
