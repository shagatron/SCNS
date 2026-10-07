from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.api import DTO


class SourceInput(DTO):
    title: str = Field(min_length=1, max_length=160)
    rights: Literal["synthetic", "authorized", "restricted"]
    provenance: str = Field(min_length=10, max_length=4000)
    attribution: str = Field(min_length=1, max_length=500)
    original: dict | None = None
    display_overlay: bool = False


class RouteExpectation(DTO):
    source: UUID
    target: UUID
    profile: Literal["shortest", "step_free"]
    expected_found: bool
    maximum_distance_m: float | None = Field(default=None, gt=0, le=100000, allow_inf_nan=False)
    reason: str = Field(min_length=10, max_length=2000)


class ValidateInput(DTO):
    routes: list[RouteExpectation] = Field(min_length=2, max_length=50)


class SubmitInput(DTO):
    validation_id: UUID
    acknowledgements: dict[str, str] = Field(default_factory=dict, max_length=1000)


class DecisionInput(DTO):
    decision: Literal["approve", "reject", "withdraw"]
    notes: str = Field(min_length=10, max_length=4000)
    acknowledgements: dict[str, str] = Field(default_factory=dict, max_length=1000)


class PublishInput(DTO):
    submission_id: UUID
    expected_release_id: UUID | None
    key: str = Field(min_length=8, max_length=80)


class RollbackInput(DTO):
    target_release_id: UUID
    expected_release_id: UUID
    key: str = Field(min_length=8, max_length=80)
    reason: str = Field(min_length=10, max_length=4000)
