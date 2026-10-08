"""Release-pinned mixed-frame routing and public floor metadata."""

from datetime import UTC, datetime
from uuid import uuid4

from app.core.config import get_settings
from app.core.errors import DomainError
from app.models import Revision
from app.models.publication import ReleaseArtifact
from app.routing.mixed import compute
from app.schemas.api import RouteOut


def release_projection(db, release):
    artifact = db.get(ReleaseArtifact, release.id)
    if artifact:
        return artifact.content
    # Historical trusted synthetic seeds predate artifacts; never mutate their hashes.
    from app.services.publication import public_projection, snapshot

    return public_projection(snapshot(db, db.get(Revision, release.dataset_revision_id)))


def floor_descriptors(data, release):
    descriptors = []
    for identity, f in sorted(
        data.get("floors", {}).items(),
        key=lambda item: (item[1]["building_id"], item[1]["ordering"], item[0]),
    ):
        layer = data.get("floorplans", {}).get(f["layer_id"])
        frame = data.get("frames", {}).get(f["frame_id"])
        if not layer or not frame:
            continue
        descriptors.append(
            dict(
                id=identity,
                building_id=f["building_id"],
                building_name=data["buildings"][f["building_id"]]["name"],
                label=f["label"],
                ordering=f["ordering"],
                frame_id=f["frame_id"],
                layer_id=f["layer_id"],
                width_px=frame["width_px"],
                height_px=frame["height_px"],
                metres_per_pixel=frame["metres_per_pixel"],
                navigation_mode=f["navigation_mode"],
                asset_url=f"/api/v1/campuses/{release.campus_id}/releases/{release.id}/floorplans/{f['layer_id']}/{layer['checksum']}.png",
                attribution=layer["attribution"],
            )
        )
    return descriptors


def calculate(db, request, release, data=None):
    data = data or release_projection(db, release)
    settings = get_settings()
    if (
        sum(len(data.get(k, {})) for k in ("nodes", "indoor_nodes")) > settings.graph_node_limit
        or sum(
            len(data.get(k, {}))
            for k in ("edges", "indoor_edges", "connector_paths", "entrance_transitions")
        )
        > settings.graph_edge_limit
    ):
        raise DomainError(
            "service_unavailable", "This graph exceeds the configured routing budget.", 503
        )
    start_node = None
    source_place = None
    source_marker = None
    if request.source.kind == "qr":
        from app.services.qr import resolve

        marker = resolve(db, request.source.marker_id)
        if marker.campus_id != request.campus_id:
            raise DomainError("location_not_found", "This marker belongs to another campus.", 404)
        if marker.release_id != release.id:
            raise DomainError(
                "stale_release", "The map changed. Confirm the marker on the current release.", 409
            )
        if marker.state != "active":
            raise DomainError("qr_unavailable", marker.message, 410)
        if marker.version != request.source.expected_marker_version:
            raise DomainError(
                "stale_marker",
                "The QR marker changed. Reload and confirm its current label before routing.",
                409,
            )
        start_node = (marker.node_kind, str(marker.node_id))
        source_marker = marker.id
    elif request.source.kind == "gps":
        from app.services.location import match

        suggestion = match(db, request.campus_id, request.source, request.profile, release)
        candidate = next(
            (
                c
                for c in suggestion["candidates"]
                if c["node_id"] == str(request.source.confirmed_node_id)
            ),
            None,
        )
        if candidate is None:
            raise DomainError(
                "location_needs_confirmation",
                "The landmark is no longer suitable. Request location again or choose a manual/QR start.",
                422,
            )
        start_node = ("outdoor", str(request.source.confirmed_node_id))
    else:
        source_place = request.source.place_id
    result = compute(
        data,
        str(source_place),
        str(request.destination.place_id),
        request.profile,
        request.cost_mode,
        settings.walking_speed_mps,
        start_node=start_node,
    )
    used = {s[k] for s in result["segments"] for k in ("floor_id", "to_floor_id") if s[k]}
    if start_node and start_node[0] == "indoor":
        used.add(data["indoor_nodes"][start_node[1]]["floor_id"])
    for identity in (str(source_place), str(request.destination.place_id)):
        room = data.get("indoor_rooms", {}).get(identity)
        if room:
            used.add(room["floor_id"])
    warnings = [
        "Published static availability is combined with live operational restrictions; recurring opening hours and lift queues are unsupported.",
        f"Baseline walking estimates assume {settings.walking_speed_mps:.1f}m/s. Connector traversal and lift wait use reviewed estimates when supplied; unknown components have no ETA.",
    ]
    if request.source.kind == "gps":
        warnings.append(
            f"Outdoor location accuracy ±{request.source.accuracy_m:g}m. Route starts at the landmark you explicitly confirmed; its approximate straight-line approach distance is {candidate['approach_distance_m']:g}m, not verified walking distance and excluded from distance/ETA. No GPS-to-path shortcut or indoor position is inferred; this is not continuous tracking."
        )
    elif start_node:
        warnings.append(
            "Start is the labelled QR marker you explicitly confirmed, not a continuously tracked position."
        )
    if data["campus"]["is_demo"]:
        warnings.insert(
            0,
            "Synthetic campus: invented topology and accessibility evidence, not real navigation.",
        )
    if request.cost_mode == "directions_only":
        warnings.append(
            "Directions-only minimizes stored traversals, not metres or travel time. Unknown distances remain NULL."
        )
    if result["distance_m"] is None:
        warnings.append(
            "Total distance is unknown; the known subtotal excludes unmeasured components."
        )
    now = datetime.now(UTC)
    return RouteOut(
        id=uuid4(),
        campus_id=request.campus_id,
        release_id=release.id,
        dataset_revision_id=release.dataset_revision_id,
        generated_at=now,
        departure_at=request.departure_at or now,
        profile=request.profile,
        cost_mode=request.cost_mode,
        source_place_id=source_place,
        source_marker_id=source_marker,
        source_node_id=start_node[1] if start_node else None,
        destination_place_id=request.destination.place_id,
        walking_speed_mps=settings.walking_speed_mps,
        floors=[f for f in floor_descriptors(data, release) if f["id"] in used],
        warnings=warnings,
        **result,
    )
