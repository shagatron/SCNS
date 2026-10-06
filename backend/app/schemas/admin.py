from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, SecretStr, field_validator

from app.schemas.api import DTO, Point, Polygon, ReleaseOut
from app.schemas.dataset import Accessibility, Visibility, validate_positions

Role = Literal["editor", "reviewer_publisher", "operations", "system_admin"]
Entity = Literal["buildings", "places", "departments", "aliases", "anchors"]
Name = Annotated[str, Field(min_length=1, max_length=160)]
Code = Annotated[str, Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")]


class LoginInput(DTO):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def canonical_username(cls, value):
        return value.lower()


class UserInput(LoginInput):
    password: SecretStr = Field(min_length=12, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)
    role: Role


class GrantOut(DTO):
    campus_id: UUID
    campus_name: str
    roles: list[Role]
    permissions: list[str]


class SessionOut(DTO):
    user_id: UUID
    username: str
    display_name: str
    csrf_token: str
    expires_at: datetime
    grants: list[GrantOut]


class DraftOut(DTO):
    id: UUID
    campus_id: UUID
    version: int
    edit_version: int
    status: Literal["draft", "review", "frozen"]
    created_at: datetime


class DashboardOut(DTO):
    campus_id: UUID
    campus_name: str
    permissions: list[str]
    release: ReleaseOut | None
    drafts: list[DraftOut]
    drafts_total: int
    limitations: list[str]


class BuildingFields(DTO):
    code: Code
    name: Name
    visibility: Visibility = "public"
    footprint: Polygon

    @field_validator("footprint")
    @classmethod
    def valid_polygon(cls, polygon):
        if not 1 <= len(polygon.coordinates) <= 10:
            raise ValueError("A footprint needs 1–10 rings")
        for ring in polygon.coordinates:
            validate_positions(ring)
            if not 4 <= len(ring) <= 500 or ring[0] != ring[-1]:
                raise ValueError("Rings must close and have 4–500 points")
        return polygon


class PlaceFields(DTO):
    code: Code
    name: Name
    kind: Literal["entrance", "building", "library", "cafe", "water", "washroom", "garden", "help"]
    description: str = Field(default="", max_length=2000)
    building_id: UUID | None = None
    visibility: Visibility = "public"
    point: Point

    @field_validator("point")
    @classmethod
    def valid_point(cls, point):
        validate_positions([point.coordinates])
        return point


class DepartmentFields(DTO):
    code: Code
    name: Name
    description: str = Field(default="", max_length=2000)
    place_ids: list[UUID] = Field(default_factory=list, max_length=100)


class AliasFields(DTO):
    place_id: UUID
    value: Name
    language: str = Field(default="en", pattern=r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$", max_length=16)


class AnchorFields(DTO):
    place_id: UUID
    node_id: UUID
    accessibility_status: Accessibility = "unknown"
    is_open: bool = True


class BuildingWrite(DTO):
    entity: Literal["buildings"]
    data: BuildingFields


class PlaceWrite(DTO):
    entity: Literal["places"]
    data: PlaceFields


class DepartmentWrite(DTO):
    entity: Literal["departments"]
    data: DepartmentFields


class AliasWrite(DTO):
    entity: Literal["aliases"]
    data: AliasFields


class AnchorWrite(DTO):
    entity: Literal["anchors"]
    data: AnchorFields


CatalogWrite = Annotated[
    BuildingWrite | PlaceWrite | DepartmentWrite | AliasWrite | AnchorWrite,
    Field(discriminator="entity"),
]


class CatalogRecord(DTO):
    id: UUID
    item: CatalogWrite


class CatalogPage(DTO):
    revision_version: int
    items: list[CatalogRecord]
    total: int
    offset: int
    limit: int


class MutationOut(DTO):
    id: UUID
    revision_version: int


class NodeOption(DTO):
    id: UUID
    label: str
    visibility: Visibility


class UserOut(DTO):
    id: UUID
    username: str
    display_name: str
    roles: list[Role]


class RoleInput(DTO):
    role: Role


class AuditOut(DTO):
    id: UUID
    actor_id: UUID | None
    campus_id: UUID | None
    revision_id: UUID | None
    action: str
    resource_id: UUID | None
    before: dict | None
    after: dict | None
    request_id: str
    created_at: datetime
