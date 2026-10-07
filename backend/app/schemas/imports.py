from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.admin import Code, Name
from app.schemas.api import DTO, LineString, Point
from app.schemas.dataset import Accessibility, Visibility, validate_positions

ImportEntity = Literal[
    "frames",
    "buildings",
    "places",
    "nodes",
    "edges",
    "departments",
    "department_places",
    "aliases",
    "anchors",
]


class ImportOptions(DTO):
    schema_version: Literal["import-v1"] = "import-v1"
    format: Literal["csv", "json", "geojson"]
    entity: ImportEntity = "places"
    campus_code: str = Field(min_length=1, max_length=32)
    timezone: str = Field(min_length=1, max_length=64)
    units: Literal["WGS84_degrees_and_metres"] = "WGS84_degrees_and_metres"
    source_rights: str = Field(min_length=1, max_length=2000)
    provenance: str = Field(min_length=1, max_length=2000)
    policy: Literal["create_only", "upsert"] = "create_only"
    mapping: dict[str, str] = Field(default_factory=dict, max_length=40)

    @field_validator("source_rights", "provenance")
    @classmethod
    def nonblank_source(cls, value):
        if not value.strip():
            raise ValueError("Source rights and provenance cannot be blank")
        return value.strip()

    @field_validator("mapping")
    @classmethod
    def bounded_mapping(cls, value):
        if any(len(k) > 64 or len(v) > 160 for k, v in value.items()):
            raise ValueError("Mapping names exceed limits")
        return value


class FrameFields(DTO):
    code: Code
    kind: Literal["outdoor"] = "outdoor"


class NodeFields(DTO):
    evidence: str = Field(default="", max_length=2000)
    frame_id: UUID
    label: Name
    visibility: Visibility = "public"
    point: Point

    @field_validator("point")
    @classmethod
    def valid_point(cls, value):
        validate_positions([value.coordinates])
        return value


class EdgeFields(DTO):
    frame_id: UUID
    from_node_id: UUID
    to_node_id: UUID
    physical_path_id: UUID
    kind: Literal["walkway", "ramp", "stairs"] = "walkway"
    geometry: LineString
    distance_status: Literal["measured", "estimated"] = "estimated"
    accessibility_status: Accessibility = "unknown"
    visibility: Visibility = "public"
    is_open: bool = True
    evidence: str = Field(min_length=1, max_length=2000)

    @field_validator("geometry")
    @classmethod
    def valid_line(cls, value):
        if not 2 <= len(value.coordinates) <= 500:
            raise ValueError("Polyline must have 2–500 positions")
        validate_positions(value.coordinates)
        return value


class DepartmentPlaceFields(DTO):
    department_id: UUID
    place_id: UUID


class ImportRecord(DTO):
    entity: ImportEntity
    external_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,120}$")
    existing_id: UUID | None = None
    data: dict


class ImportBundle(DTO):
    schema_version: Literal["import-v1"]
    units: Literal["WGS84_degrees_and_metres"]
    campus_code: str = Field(min_length=1, max_length=32)
    timezone: str = Field(min_length=1, max_length=64)
    records: list[ImportRecord] = Field(min_length=1, max_length=10000)
