from typing import Literal
from uuid import UUID

from pydantic import Field, ValidationInfo, field_validator, model_validator

from app.schemas.api import DTO


class ReviewText(DTO):
    @field_validator("notes", "reason", check_fields=False)
    @classmethod
    def nonblank_reason(cls, value):
        value = value.strip()
        if len(value) < 10:
            raise ValueError("Provide a substantive reason of at least ten characters")
        return value


class SourceInput(DTO):
    title: str = Field(min_length=1, max_length=160)
    rights: Literal["synthetic", "authorized", "restricted"]
    provenance: str = Field(min_length=10, max_length=4000)
    attribution: str = Field(min_length=1, max_length=500)
    original: dict | None = None
    original_text: str | None = Field(default=None, max_length=5 * 1024 * 1024)
    original_filename: str | None = Field(
        default=None, min_length=1, max_length=160, pattern=r"^[A-Za-z0-9_. -]+$"
    )
    display_overlay: bool = False

    @model_validator(mode="after")
    def one_original(self):
        if self.original is not None and self.original_text is not None:
            raise ValueError("Supply either inline JSON or original UTF-8 text, never both")
        if self.original_filename and (
            self.original_filename.startswith(".")
            or not self.original_filename.lower().endswith((".json", ".geojson"))
        ):
            raise ValueError("Use a plain .json/.geojson original filename")
        return self

    @field_validator("title", "provenance", "attribution")
    @classmethod
    def meaningful_source_text(cls, value, info: ValidationInfo):
        value = value.strip()
        if len(value) < (10 if info.field_name == "provenance" else 1):
            raise ValueError("Source text must not be blank; provenance needs ten characters")
        return value


class RouteExpectation(ReviewText):
    source: UUID
    target: UUID
    profile: Literal["shortest", "step_free", "fastest"]
    cost_mode: Literal["metric", "directions_only"] = "metric"
    expected_found: bool
    maximum_distance_m: float | None = Field(default=None, gt=0, le=100000, allow_inf_nan=False)
    reason: str = Field(min_length=10, max_length=2000)


class ValidateInput(DTO):
    routes: list[RouteExpectation] = Field(min_length=2, max_length=250)


class SubmitInput(DTO):
    validation_id: UUID
    acknowledgements: dict[str, str] = Field(default_factory=dict, max_length=1000)


class DecisionInput(ReviewText):
    decision: Literal["approve", "reject", "withdraw"]
    notes: str = Field(min_length=10, max_length=4000)
    acknowledgements: dict[str, str] = Field(default_factory=dict, max_length=1000)


class PublishInput(DTO):
    submission_id: UUID
    expected_release_id: UUID | None
    key: str = Field(min_length=8, max_length=80)


class RollbackInput(ReviewText):
    target_release_id: UUID
    expected_release_id: UUID
    key: str = Field(min_length=8, max_length=80)
    reason: str = Field(min_length=10, max_length=4000)
