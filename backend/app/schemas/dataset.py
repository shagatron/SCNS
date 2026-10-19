"""Version 1 is an outdoor bundle; future import formats must be explicitly versioned."""

import math
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator

from app.schemas.api import DTO, LineString, Point, Polygon

Visibility = Literal["public", "restricted"]
Accessibility = Literal["verified_step_free", "not_step_free", "unknown"]


def validate_positions(positions):
    for lon, lat in positions:
        if (
            not math.isfinite(lon)
            or not math.isfinite(lat)
            or not (-180 <= lon <= 180 and -90 <= lat <= 90)
        ):
            raise ValueError("Invalid WGS84 [longitude, latitude] position")


class CampusData(DTO):
    id: UUID
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=160)
    timezone: str
    is_demo: bool
    center: Point
    boundary: Polygon


class FrameData(DTO):
    id: UUID
    code: str
    kind: Literal["outdoor"] = "outdoor"


class BuildingData(DTO):
    id: UUID
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=160)
    footprint: Polygon
    visibility: Visibility = "public"


class PlaceData(DTO):
    id: UUID
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    kind: Literal["entrance", "building", "library", "cafe", "water", "washroom", "garden", "help"]
    description: str = Field(max_length=2000)
    aliases: list[str] = Field(default_factory=list, max_length=30)
    building_id: UUID | None = None
    visibility: Visibility = "public"
    point: Point


class NodeData(DTO):
    id: UUID
    frame_id: UUID
    label: str = Field(min_length=1, max_length=160)
    visibility: Visibility = "public"
    point: Point


class EdgeData(DTO):
    id: UUID
    physical_path_id: UUID
    from_node_id: UUID
    to_node_id: UUID
    frame_id: UUID
    kind: Literal["walkway", "ramp", "stairs"] = "walkway"
    geometry: LineString
    # Distances are computed from this whole polyline by PostGIS, never trusted from an import.
    accessibility_status: Accessibility = "unknown"
    visibility: Visibility = "public"
    is_open: bool = True
    evidence: str = Field(min_length=1, max_length=2000)


class AnchorData(DTO):
    id: UUID
    place_id: UUID
    node_id: UUID
    accessibility_status: Accessibility = "unknown"
    is_open: bool = True


class Dataset(DTO):
    schema_version: Literal["1.0"]
    units: Literal["WGS84_degrees_and_metres"]
    source_rights: str = Field(min_length=1)
    provenance: str = Field(min_length=1)
    campus: CampusData
    frames: list[FrameData] = Field(min_length=1, max_length=100)
    buildings: list[BuildingData] = Field(max_length=1000)
    places: list[PlaceData] = Field(max_length=10000)
    nodes: list[NodeData] = Field(max_length=50000)
    edges: list[EdgeData] = Field(max_length=150000)
    anchors: list[AnchorData] = Field(max_length=30000)

    @model_validator(mode="after")
    def relationships(self):
        try:
            ZoneInfo(self.campus.timezone)
        except (KeyError, ValueError):
            raise ValueError("Campus timezone must be a valid IANA timezone") from None
        for collection in (
            self.frames,
            self.buildings,
            self.places,
            self.nodes,
            self.edges,
            self.anchors,
        ):
            if len({item.id for item in collection}) != len(collection):
                raise ValueError("Duplicate ID within entity collection")
        for collection in (self.frames, self.buildings, self.places):
            if len({item.code for item in collection}) != len(collection):
                raise ValueError("Duplicate entity code")
        frames = {f.id for f in self.frames}
        nodes = {n.id: n for n in self.nodes}
        places = {p.id: p for p in self.places}
        buildings = {b.id: b for b in self.buildings}
        validate_positions(
            [self.campus.center.coordinates]
            + [p.point.coordinates for p in self.places]
            + [n.point.coordinates for n in self.nodes]
        )
        for polygon in [self.campus.boundary] + [b.footprint for b in self.buildings]:
            if not polygon.coordinates:
                raise ValueError("Polygon needs a ring")
            for ring in polygon.coordinates:
                validate_positions(ring)
                if len(ring) < 4 or ring[0] != ring[-1]:
                    raise ValueError("Polygon rings must be closed with at least four positions")
        for place in self.places:
            if place.building_id and place.building_id not in buildings:
                raise ValueError(f"Place {place.id}: unknown building")
            if (
                place.visibility == "public"
                and place.building_id
                and buildings[place.building_id].visibility != "public"
            ):
                raise ValueError("Public place cannot belong to a restricted building")
        for node in self.nodes:
            if node.frame_id not in frames:
                raise ValueError(f"Node {node.id}: unknown frame")
        for edge in self.edges:
            if edge.from_node_id not in nodes or edge.to_node_id not in nodes:
                raise ValueError(f"Edge {edge.id}: unknown endpoint node")
            source, target = nodes[edge.from_node_id], nodes[edge.to_node_id]
            if source.id == target.id:
                raise ValueError("Movement edge needs distinct endpoints")
            if not (source.frame_id == target.frame_id == edge.frame_id):
                raise ValueError("Outdoor edge cannot cross coordinate frames")
            points = edge.geometry.coordinates
            validate_positions(points)
            if (
                len(points) < 2
                or points[0] != source.point.coordinates
                or points[-1] != target.point.coordinates
                or len(set(points)) < 2
            ):
                raise ValueError(f"Edge {edge.id}: polyline must follow its directed endpoints")
            if edge.visibility == "public" and (
                source.visibility != "public" or target.visibility != "public"
            ):
                raise ValueError("Public edge cannot expose restricted endpoints")
            if edge.kind == "stairs" and edge.accessibility_status == "verified_step_free":
                raise ValueError("Stairs cannot be step-free")
        if len({(a.place_id, a.node_id) for a in self.anchors}) != len(self.anchors):
            raise ValueError("Duplicate place/node anchor")
        for anchor in self.anchors:
            if anchor.place_id not in places or anchor.node_id not in nodes:
                raise ValueError(f"Anchor {anchor.id}: unknown place or node")
            if (
                places[anchor.place_id].visibility == "public"
                and nodes[anchor.node_id].visibility != "public"
            ):
                raise ValueError("Public anchor cannot expose a restricted node")
        return self
