from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import Field, ValidationInfo, field_validator

from app.schemas.api import DTO
from app.schemas.publication import ReviewText


class MarkerInput(DTO):
    label: str = Field(min_length=1, max_length=160)
    node_kind: Literal["outdoor", "indoor"]
    node_id: UUID
    intended_position: str = Field(min_length=10, max_length=2000)

    @field_validator("label", "intended_position")
    @classmethod
    def meaningful(cls, value, info: ValidationInfo):
        value = value.strip()
        if len(value) < (10 if info.field_name == "intended_position" else 1):
            raise ValueError("Provide meaningful marker text")
        return value


class MarkerCreate(MarkerInput):
    key: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


class Installation(ReviewText):
    actual_position: str = Field(min_length=10, max_length=2000)
    installer: str = Field(min_length=1, max_length=160)
    installed_on: date
    verified_on: date
    evidence: str = Field(min_length=10, max_length=2000)

    @field_validator("actual_position", "installer", "evidence")
    @classmethod
    def meaningful(cls, value, info: ValidationInfo):
        if len(value.strip()) < (1 if info.field_name == "installer" else 10):
            raise ValueError("Provide installation and verification evidence")
        return value.strip()


class Revoke(ReviewText):
    reason: str = Field(min_length=10, max_length=2000)


class MarkerResolution(DTO):
    id: UUID
    campus_id: UUID
    campus_name: str
    building_name: str | None = None
    version: int
    state: Literal["active", "planned", "revoked", "retired", "needs_verification"]
    release_id: UUID
    label: str | None = None
    node_id: UUID | None = None
    node_kind: Literal["outdoor", "indoor"] | None = None
    node_label: str | None = None
    floor_id: UUID | None = None
    floor_label: str | None = None
    verified_on: date | None = None
    is_demo: bool
    message: str
