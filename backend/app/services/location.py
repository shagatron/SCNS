"""Transient outdoor proximity matching; pilot routes require physical landmark confirmation."""

import json
import math
from datetime import UTC, datetime, timedelta

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select

from app.core.config import get_settings
from app.core.errors import DomainError
from app.models import Edge
from app.services import closures
from app.services.mixed_routes import release_projection


def policy():
    s = get_settings()
    return dict(
        max_accuracy_m=s.gps_max_accuracy_m,
        max_age_seconds=s.gps_max_age_seconds,
        max_path_distance_m=s.gps_max_path_distance_m,
        max_landmark_distance_m=s.gps_max_landmark_distance_m,
    )


def validate(observation, now=None):
    now = now or datetime.now(UTC)
    p = policy()
    if observation.accuracy_m > p["max_accuracy_m"]:
        raise DomainError(
            "location_inaccurate",
            "Location is too uncertain. Try again outdoors or choose a manual/QR start.",
            422,
        )
    age = (now - observation.observed_at).total_seconds()
    if age < -10 or age > p["max_age_seconds"]:
        raise DomainError(
            "location_stale",
            "Location is stale or the device clock is incorrect. Request a fresh fix or use a manual/QR start.",
            422,
        )
    return observation.observed_at + timedelta(seconds=p["max_age_seconds"])


def match(db, campus, observation, profile, release):
    expires = validate(observation)
    data = release_projection(db, release)
    p = policy()
    point = func.ST_SetSRID(func.ST_MakePoint(observation.longitude, observation.latitude), 4326)
    boundary = func.ST_SetSRID(
        func.ST_GeomFromGeoJSON(json.dumps(data["campus"]["boundary"])), 4326
    )
    if not db.scalar(select(func.ST_Covers(boundary, point))):
        raise DomainError(
            "location_outside_campus",
            "Location is outside this published campus. Choose the correct campus or a manual/QR start.",
            422,
        )
    # Conservatively exclude every scheduled incident, including unknown traversal time.
    data = closures.apply(data, closures.records(db, campus), None)
    edges = {
        i: e
        for i, e in data["edges"].items()
        if e["is_open"]
        and (
            profile != "step_free"
            or (e["kind"] != "stairs" and e["accessibility_status"] == "verified_step_free")
        )
    }
    outgoing = {e["from_node_id"] for e in edges.values()}
    anchors = {
        a["node_id"]
        for a in data["anchors"].values()
        if a["is_open"]
        and a["place_id"] in data["places"]
        and (profile != "step_free" or a["accessibility_status"] == "verified_step_free")
    }
    # Geometry GiST bounding-box prefilter, then geography proximity/projection in metres.
    radius = p["max_path_distance_m"]
    degrees = radius / (110000 * max(math.cos(math.radians(observation.latitude)), 0.001))
    distance = func.ST_Distance(
        cast(func.ST_ClosestPoint(Edge.geometry, point), Geography(srid=4326)),
        cast(point, Geography(srid=4326)),
    )
    rows = db.execute(
        select(Edge.id, distance)
        .where(
            Edge.dataset_revision_id == release.dataset_revision_id,
            Edge.visibility == "public",
            Edge.geometry.op("&&")(func.ST_Expand(point, degrees)),
            distance <= radius,
        )
        .order_by(distance, Edge.id)
        .limit(100)
    ).all()
    candidates = {}
    for identity, path_distance in rows:
        e = edges.get(str(identity))
        if not e:
            continue
        for node in (e["from_node_id"], e["to_node_id"]):
            if node not in anchors or node not in outgoing or node not in data["nodes"]:
                continue
            coordinates = data["nodes"][node]["point"]["coordinates"]
            landmark = func.ST_SetSRID(func.ST_MakePoint(*coordinates), 4326)
            approach = db.scalar(
                select(
                    func.ST_Distance(
                        cast(landmark, Geography(srid=4326)), cast(point, Geography(srid=4326))
                    )
                )
            )
            if approach <= p["max_landmark_distance_m"]:
                value = dict(
                    node_id=node,
                    label=data["nodes"][node]["label"],
                    path_distance_m=round(path_distance, 2),
                    approach_distance_m=round(approach, 2),
                )
                if (
                    node not in candidates
                    or value["path_distance_m"] < candidates[node]["path_distance_m"]
                ):
                    candidates[node] = value
    if not candidates:
        raise DomainError(
            "location_no_suitable_path",
            "No suitable published path and nearby labelled landmark. Choose a known manual/QR start; do not cross walls or fences toward a GPS suggestion.",
            422,
        )
    return dict(
        release_id=release.id,
        closure_overlay_version=closures.version(db, campus),
        expires_at=expires,
        accuracy_m=observation.accuracy_m,
        candidates=sorted(
            candidates.values(),
            key=lambda c: (c["path_distance_m"], c["approach_distance_m"], c["node_id"]),
        )[:5],
    )
