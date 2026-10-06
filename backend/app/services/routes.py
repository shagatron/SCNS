import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import DomainError
from app.models import Anchor, Campus, Edge, Node, Place
from app.routing.dijkstra import Arc, shortest_path
from app.schemas.api import RouteOut, RouteRequest, RouteSegment
from app.services.catalog import active_release


def calculate_route(session: Session, request: RouteRequest) -> RouteOut:
    release = active_release(session, request.campus_id)
    if request.expected_release_id and request.expected_release_id != release.id:
        raise DomainError(
            "stale_release", "The map has changed. Refresh the campus and try again.", 409
        )
    revision = release.dataset_revision_id
    places = {}
    for place_id in {request.source.place_id, request.destination.place_id}:
        place = session.get(Place, (revision, place_id))
        if place is None or place.visibility != "public":
            raise DomainError("location_not_found", "This public location could not be found.", 404)
        places[place_id] = place
    settings = get_settings()
    nodes = session.scalars(
        select(Node)
        .where(Node.dataset_revision_id == revision, Node.visibility == "public")
        .limit(settings.graph_node_limit + 1)
    ).all()
    if len(nodes) > settings.graph_node_limit:
        raise DomainError(
            "service_unavailable", "This graph exceeds the configured routing budget.", 503
        )
    labels = {str(n.id): n.label for n in nodes}
    node_ids = {n.id for n in nodes}
    anchors = session.scalars(
        select(Anchor).where(
            Anchor.dataset_revision_id == revision, Anchor.place_id.in_(places), Anchor.is_open
        )
    ).all()
    candidates = {
        place_id: [a for a in anchors if a.place_id == place_id and a.node_id in node_ids]
        for place_id in places
    }
    if any(not items for items in candidates.values()):
        raise DomainError(
            "location_not_routable",
            "Location mapped, routing unavailable: no usable entrance is mapped.",
        )
    if request.profile == "step_free":
        candidates = {
            key: [a for a in items if a.accessibility_status == "verified_step_free"]
            for key, items in candidates.items()
        }
    rows = session.execute(
        select(Edge, func.ST_AsGeoJSON(Edge.geometry))
        .where(Edge.dataset_revision_id == revision, Edge.visibility == "public")
        .limit(settings.graph_edge_limit + 1)
    ).all()
    if len(rows) > settings.graph_edge_limit:
        raise DomainError(
            "service_unavailable", "This graph exceeds the configured routing budget.", 503
        )
    edges = {
        str(e.id): (e, json.loads(g))
        for e, g in rows
        if e.from_node_id in node_ids and e.to_node_id in node_ids
    }
    path = shortest_path(
        [
            Arc(
                str(e.id),
                str(e.from_node_id),
                str(e.to_node_id),
                e.distance_m,
                e.kind,
                e.accessibility_status,
                e.is_open,
                e.visibility,
            )
            for e, _ in edges.values()
        ],
        {str(a.node_id) for a in candidates[request.source.place_id]},
        {str(a.node_id) for a in candidates[request.destination.place_id]},
        request.profile,
    )
    if path is None:
        code = "no_verified_step_free_route" if request.profile == "step_free" else "no_route"
        message = (
            "No verified step-free route is available. Unknown accessibility and stairs are excluded."
            if request.profile == "step_free"
            else "No permitted walking route connects these locations. Try a different mapped start or destination."
        )
        raise DomainError(code, message)
    segments = []
    for edge_id in path.edges:
        edge, geometry = edges[edge_id]
        verb = (
            "Take the stairs"
            if edge.kind == "stairs"
            else "Follow the ramp"
            if edge.kind == "ramp"
            else "Follow the path"
        )
        segments.append(
            RouteSegment(
                edge_id=edge.id,
                from_node_id=edge.from_node_id,
                to_node_id=edge.to_node_id,
                geometry=geometry,
                distance_m=round(edge.distance_m, 2),
                instruction=f"{verb} to {labels[str(edge.to_node_id)]}.",
            )
        )
    now = datetime.now(UTC)
    campus = session.get(Campus, request.campus_id)
    warnings = [
        f"Baseline ETA assumes a walking speed of {settings.walking_speed_mps:.1f} m/s; it excludes stops and personal mobility differences.",
        "Opening and closure state comes from this map release. No live closures or time-dependent schedules are available.",
    ]
    if campus.is_demo:
        warnings.insert(
            0,
            "Synthetic campus: invented coordinates and paths, not real navigation or accessibility evidence.",
        )
    return RouteOut(
        id=uuid4(),
        campus_id=request.campus_id,
        release_id=release.id,
        dataset_revision_id=revision,
        generated_at=now,
        departure_at=request.departure_at or now,
        profile=request.profile,
        source_place_id=request.source.place_id,
        destination_place_id=request.destination.place_id,
        source_anchor_id=next(
            a.id for a in candidates[request.source.place_id] if str(a.node_id) == path.nodes[0]
        ),
        destination_anchor_id=next(
            a.id
            for a in candidates[request.destination.place_id]
            if str(a.node_id) == path.nodes[-1]
        ),
        distance_m=round(path.distance_m, 2),
        estimated_duration_s=round(path.distance_m / settings.walking_speed_mps, 1),
        walking_speed_mps=settings.walking_speed_mps,
        segments=segments,
        arrival_instruction=f"Arrive at {places[request.destination.place_id].name}.",
        warnings=warnings,
    )
