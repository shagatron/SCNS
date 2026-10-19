from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, field_validator, model_validator

from app.schemas.api import DTO

TargetKind = Literal["outdoor_edge", "outdoor_path", "indoor_edge", "connector"]


class ClosureCreate(DTO):
    key: str = Field(min_length=8, max_length=80)
    target_kind: TargetKind
    target_id: UUID
    reason: str = Field(min_length=10, max_length=1000)
    starts_at: AwareDatetime
    estimated_end_at: AwareDatetime | None = None
    reopening_policy: Literal["operator_verified"] = "operator_verified"

    @field_validator("reason")
    @classmethod
    def substantive(cls, value):
        if len(value.strip()) < 10:
            raise ValueError("Explain the public restriction")
        return value.strip()

    @model_validator(mode="after")
    def dates(self):
        if self.estimated_end_at is not None and self.estimated_end_at <= self.starts_at:
            raise ValueError("Estimated end must follow start; it never automatically reopens")
        return self


class ClosureDecision(DTO):
    key: str = Field(min_length=8, max_length=80)
    evidence: str = Field(min_length=10, max_length=2000)
    confirmed: Literal[True]

    @field_validator("evidence")
    @classmethod
    def substantive(cls, value):
        if len(value.strip()) < 10:
            raise ValueError("Record verification or target reconciliation")
        return value.strip()


class ClosureRebind(ClosureDecision):
    target_kind: TargetKind
    target_id: UUID


class PublicClosure(DTO):
    id: UUID
    target_kind: TargetKind | None
    target_id: UUID | None
    label: str
    reason: str
    starts_at: datetime
    estimated_end_at: datetime | None
    state: Literal["scheduled", "active", "unresolved"]
    reopening_policy: Literal["operator_verified"] = "operator_verified"


class ClosureStatus(DTO):
    release_id: UUID
    closure_overlay_version: int
    checked_at: datetime
    next_change_at: datetime | None
    unresolved_count: int
    items: list[PublicClosure]
