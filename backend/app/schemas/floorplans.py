"""Top-left image pixels are never WGS84 coordinates or implicit metres."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.api import DTO
from app.schemas.publication import ReviewText


class FloorInput(DTO):
    id: UUID | None = None
    building_id: UUID
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    label: str = Field(min_length=1, max_length=160)
    ordering: float = Field(ge=-100, le=1000, allow_inf_nan=False)
    elevation_m: float | None = Field(default=None, ge=-500, le=10000, allow_inf_nan=False)
    visibility: Literal["public", "restricted"] = "public"

    @field_validator("label")
    @classmethod
    def label_text(cls, value):
        if not value.strip():
            raise ValueError("Use a meaningful floor label")
        return value.strip()


class Pixel(DTO):
    x: float = Field(ge=0, le=10000, allow_inf_nan=False)
    y: float = Field(ge=0, le=10000, allow_inf_nan=False)


class Redaction(DTO):
    x: float = Field(ge=0, le=10000, allow_inf_nan=False)
    y: float = Field(ge=0, le=10000, allow_inf_nan=False)
    width: float = Field(gt=0, le=10000, allow_inf_nan=False)
    height: float = Field(gt=0, le=10000, allow_inf_nan=False)


class UploadInput(DTO):
    floor_id: UUID
    key: str = Field(min_length=8, max_length=80)
    filename: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9_. -]+$")
    title: str = Field(min_length=1, max_length=160)
    rights: Literal["synthetic", "authorized", "restricted"]
    provenance: str = Field(min_length=10, max_length=4000)
    attribution: str = Field(min_length=1, max_length=500)
    page: int = Field(default=1, ge=1, le=30)
    redactions: list[Redaction] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def safe_metadata(self):
        if self.filename.startswith(".") or not self.filename.lower().endswith(
            (".pdf", ".png", ".jpg", ".jpeg")
        ):
            raise ValueError("Use a plain PDF/PNG/JPEG filename")
        for key in ("title", "provenance", "attribution"):
            value = getattr(self, key).strip()
            if len(value) < (10 if key == "provenance" else 1):
                raise ValueError("Provide substantive source metadata")
            setattr(self, key, value)
        return self


class ApplyInput(DTO):
    replace_layer_id: UUID | None = None
    reset_calibration: bool = False


class DeleteFloor(DTO):
    remove_layer_ids: list[UUID] = Field(default_factory=list, max_length=100)


class Measurement(DTO):
    start: Pixel
    end: Pixel
    distance_m: float = Field(ge=0.1, le=10000, allow_inf_nan=False)


class CalibrationInput(ReviewText):
    method: Literal["uniform_scale"] = "uniform_scale"
    primary: Measurement
    checks: list[Measurement] = Field(min_length=1, max_length=10)
    measured_on: date
    evidence: str = Field(min_length=10, max_length=4000)
    uncertainty_m: float = Field(ge=0, le=5, allow_inf_nan=False)
    plan_quality: Literal["uniform", "distorted"] = "uniform"

    @field_validator("evidence")
    @classmethod
    def substantive_evidence(cls, value):
        if len(value.strip()) < 10:
            raise ValueError("Record the known measurement source and quality")
        return value.strip()


class PageInput(DTO):
    key: str = Field(min_length=8, max_length=80)
    page: int = Field(ge=1, le=30)
    redactions: list[Redaction] = Field(default_factory=list, max_length=20)
