"""Original educational topology, NOT a campus draft, release or approved plan.

Only the production pure Dijkstra engine is reused. Unit traversal costs express
an authored schematic connection, never a measurement or verification claim.
No DB/session/publication service is imported or called.
"""

from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict

from app.core.errors import DomainError
from app.routing.dijkstra import Arc, shortest_path
from app.schemas.api import RouteFloor, RouteSegment

VERSION = "indoor-school-v1"
QUALIFICATION = "Demonstration layout — not an actual MUJ floorplan."


def identity(key):
    return str(uuid5(NAMESPACE_URL, f"scns:educational:{VERSION}:{key}"))


class DemoRoom(BaseModel):
    id: UUID
    name: str
    room_code: str
    floor_id: UUID
    frame_id: UUID
    local_point: dict[str, float]


class DemoData(BaseModel):
    version: str
    qualification: str
    source: str
    floors: list[RouteFloor]
    rooms: list[DemoRoom]


class DemoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: UUID
    destination_id: UUID
    expected_version: str


class DemoRoute(BaseModel):
    version: str
    qualification: str
    source_id: UUID
    destination_id: UUID
    cost_units: str = "traversals"
    traversal_count: int
    distance_m: None = None
    estimated_duration_s: None = None
    segments: list[RouteSegment]
    arrival_instruction: str


# All coordinates are unscaled illustration pixels (x right/y down), not metres.
ROOMS = [
    ("a", "Demo Classroom A", "A", "ground", 190, 180),
    ("library", "Demo Library", "LIB", "ground", 500, 180),
    ("b", "Demo Classroom B", "B", "ground", 190, 450),
    ("isolated", "Demo Disconnected Room", "X", "ground", 500, 470),
    ("c", "Demo Classroom C", "C", "first", 190, 180),
    ("reading", "Demo Reading Room", "READ", "first", 500, 180),
    ("studio", "Demo Studio", "STUDIO", "first", 190, 450),
]


def topology():
    nodes, edges = {}, []
    for floor in ("ground", "first"):
        for key, x, y, label in [
            ("west", 190, 310, "west corridor junction"),
            ("middle", 500, 310, "central corridor junction"),
            ("east", 810, 310, "east corridor junction"),
            ("stairs", 810, 450, "Demo Stairs"),
        ]:
            nodes[f"{floor}-{key}"] = dict(floor=floor, x=x, y=y, label=label)
    for key, name, _, floor, x, y in ROOMS:
        nodes[key] = dict(floor=floor, x=x, y=y, label=name)

    def pair(a, b, kind="indoor"):
        edges.extend([(a, b, kind), (b, a, kind)])

    for floor in ("ground", "first"):
        pair(f"{floor}-west", f"{floor}-middle")
        pair(f"{floor}-middle", f"{floor}-east")
        pair(f"{floor}-east", f"{floor}-stairs")
    for key, _, _, floor, _, _ in ROOMS:
        if key != "isolated":
            pair(key, f"{floor}-{'middle' if key in {'library', 'reading'} else 'west'}")
    pair("ground-stairs", "first-stairs", "stairs")
    return nodes, edges


def describe():
    return DemoData(
        version=VERSION,
        qualification=QUALIFICATION,
        source="Original SCNS educational schematic and authored graph. Production Dijkstra engine; no campus release, real survey, approval or accessibility evidence.",
        floors=[
            RouteFloor(
                id=identity(floor),
                building_id=identity("building"),
                building_name="Demo Learning Building",
                label=label,
                ordering=order,
                frame_id=identity(f"{floor}-frame"),
                layer_id=identity(f"{floor}-image"),
                width_px=1000,
                height_px=620,
                metres_per_pixel=None,
                navigation_mode="directions_only",
                asset_url=f"/demos/indoor-school/v1/{floor}.svg",
                attribution="Original SCNS educational schematic · unscaled illustration, not a surveyed plan",
            )
            for floor, label, order in [("ground", "Ground floor", 0), ("first", "First floor", 1)]
        ],
        rooms=[
            DemoRoom(
                id=identity(key),
                name=name,
                room_code=code,
                floor_id=identity(floor),
                frame_id=identity(f"{floor}-frame"),
                local_point={"x_px": x, "y_px": y},
            )
            for key, name, code, floor, x, y in ROOMS
        ],
    )


def route(request):
    if request.expected_version != VERSION:
        raise DomainError(
            "stale_demo",
            "The demonstration changed. Reload its layout before calculating again.",
            409,
        )
    rooms = {identity(row[0]): row for row in ROOMS}
    source, destination = str(request.source_id), str(request.destination_id)
    if source not in rooms or destination not in rooms:
        raise DomainError(
            "demo_room_not_found",
            "Choose start and destination rooms from this demonstration only.",
            404,
        )
    nodes, links = topology()
    indexed = {identity(f"{a}:{b}"): (a, b, kind) for a, b, kind in links}
    path = shortest_path(
        [Arc(key, a, b, 1.0, kind, "unknown") for key, (a, b, kind) in indexed.items()],
        {rooms[source][0]},
        {rooms[destination][0]},
    )
    if path is None:
        raise DomainError(
            "demo_no_route",
            "No demo route: the disconnected room has no authored graph connection. Choose another room; no line is drawn through a wall.",
            422,
        )
    segments = []
    names = {"ground": "Ground floor", "first": "First floor"}
    for key in path.edges:
        a, b, kind = indexed[key]
        start, end = nodes[a], nodes[b]
        instruction = (
            f"Take Demo Stairs from {names[start['floor']]} to {names[end['floor']]}. No verified step-free alternative is demonstrated."
            if kind == "stairs"
            else f"Follow the demo corridor to {end['label']} on {names[end['floor']]} .".replace(
                " .", "."
            )
        )
        segments.append(
            RouteSegment(
                edge_id=key,
                from_node_id=identity(a),
                to_node_id=identity(b),
                kind=kind,
                polyline=[[start["x"], start["y"]], [end["x"], end["y"]]]
                if kind == "indoor"
                else None,
                floor_id=identity(start["floor"]),
                to_floor_id=identity(end["floor"]),
                building_id=identity("building"),
                frame_id=identity(f"{start['floor']}-frame"),
                connector_id=identity("stairs") if kind == "stairs" else None,
                from_local_point={"x_px": start["x"], "y_px": start["y"]},
                to_local_point={"x_px": end["x"], "y_px": end["y"]},
                distance_m=None,
                distance_status="unknown",
                estimated_duration_s=None,
                instruction=instruction,
            )
        )
    return DemoRoute(
        version=VERSION,
        qualification=QUALIFICATION,
        source_id=source,
        destination_id=destination,
        traversal_count=len(path.edges),
        segments=segments,
        arrival_instruction=f"Arrive at {rooms[destination][1]}.",
    )
