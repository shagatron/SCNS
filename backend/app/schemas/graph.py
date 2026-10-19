"""Bounded, typed outdoor graph patches; IDs are stable across drafts/retries."""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.admin import AnchorFields
from app.schemas.api import DTO
from app.schemas.imports import EdgeFields, NodeFields


class GraphNodeFields(NodeFields):
    evidence: str = Field(default="", max_length=2000)


class NodeChange(DTO):
    entity: Literal["nodes"]
    id: UUID
    data: GraphNodeFields | None = None


class EdgeChange(DTO):
    entity: Literal["edges"]
    id: UUID
    data: EdgeFields | None = None


class AnchorChange(DTO):
    entity: Literal["anchors"]
    id: UUID
    data: AnchorFields | None = None


class GraphPatch(DTO):
    changes: list[NodeChange | EdgeChange | AnchorChange] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique_ids(self):
        keys = [(c.entity, c.id) for c in self.changes]
        if len(set(keys)) != len(keys):
            raise ValueError("Each entity/ID may occur only once in a patch")
        return self
