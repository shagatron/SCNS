import json
from typing import Annotated
from uuid import UUID, uuid5

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.session import get_session
from app.models import ActiveRelease, Building, Campus, Edge, Node, Place, Release
from app.models.floorplans import MapLayer
from app.models.publication import ReleaseArtifact
from app.schemas.api import (
    CampusOut,
    ErrorOut,
    FloorsOut,
    HealthOut,
    MapFeature,
    MapOut,
    PlaceOut,
    ReleaseOut,
    RouteOut,
    RouteRequest,
    SearchOut,
)
from app.services.catalog import active_release, normalize, place_output, public_places
from app.services.publication import canonical
from app.services.routes import calculate_route

router = APIRouter(
    prefix="/api/v1",
    responses={
        404: {"model": ErrorOut},
        422: {"model": ErrorOut},
        409: {"model": ErrorOut},
        503: {"model": ErrorOut},
    },
)
DB = Annotated[Session, Depends(get_session)]


@router.get("/health/live", response_model=HealthOut)
def live():
    return HealthOut()


@router.get("/health/ready", response_model=HealthOut)
def ready(db: DB):
    db.execute(text("SELECT PostGIS_Version()"))
    db.execute(select(ActiveRelease).limit(1))
    return HealthOut(database="ready")


@router.get("/campuses", response_model=list[CampusOut])
def campuses(db: DB):
    rows = db.execute(
        select(Campus, func.ST_AsGeoJSON(Campus.center), func.ST_AsGeoJSON(Campus.boundary))
        .join(ActiveRelease, ActiveRelease.campus_id == Campus.id)
        .where(ActiveRelease.audience == "public")
        .limit(100)
    )
    return [
        CampusOut(
            id=c.id,
            code=c.code,
            name=c.name,
            timezone=c.timezone,
            is_demo=c.is_demo,
            center=json.loads(center),
            boundary=json.loads(boundary),
        )
        for c, center, boundary in rows
    ]


@router.get("/campuses/{campus_id}/release", response_model=ReleaseOut)
def release(campus_id: UUID, db: DB):
    return active_release(db, campus_id)


@router.get("/campuses/{campus_id}/search", response_model=SearchOut)
def search(
    campus_id: UUID,
    db: DB,
    q: str = Query("", max_length=120),
    kind: str | None = Query(None, max_length=32),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
    expected_release_id: UUID | None = None,
):
    release = active_release(db, campus_id)
    check_expected(release, expected_release_id)
    query = public_places(release.dataset_revision_id)
    value = normalize(q)
    if value:
        # Literal contains: '%' and '_' in input cannot become wildcard operators.
        query = query.where(Place.search_text.contains(value, autoescape=True))
    if kind:
        query = query.where(Place.kind == kind)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    ranking = case(
        (func.lower(Place.code) == value, 0),
        (func.lower(Place.name) == value, 0),
        (func.lower(Place.name).startswith(value, autoescape=True), 1),
        else_=2,
    )
    places = db.scalars(
        query.order_by(ranking, Place.name, Place.id).limit(limit).offset(offset)
    ).all()
    return SearchOut(
        items=place_output(db, places, release.dataset_revision_id),
        total=total,
        limit=limit,
        offset=offset,
        release_id=release.id,
    )


@router.get("/places/{place_id}", response_model=PlaceOut)
def place(place_id: UUID, db: DB):
    found = db.scalar(
        select(Place)
        .join(Release, Release.dataset_revision_id == Place.dataset_revision_id)
        .join(ActiveRelease, ActiveRelease.release_id == Release.id)
        .where(
            Place.id == place_id, Place.visibility == "public", ActiveRelease.audience == "public"
        )
    )
    if found is None:
        raise DomainError("location_not_found", "This public location could not be found.", 404)
    if db.scalar(public_places(found.dataset_revision_id).where(Place.id == found.id)) is None:
        raise DomainError("location_not_found", "This public location could not be found.", 404)
    return place_output(db, [found], found.dataset_revision_id)[0]


@router.get("/campuses/{campus_id}/map", response_model=MapOut)
def map_data(
    campus_id: UUID,
    db: DB,
    bbox: str = Query(..., max_length=120),
    zoom: int = Query(17, ge=14, le=22),
    expected_release_id: UUID | None = None,
):
    release = active_release(db, campus_id)
    check_expected(release, expected_release_id)
    try:
        west, south, east, north = map(float, bbox.split(","))
        if not (
            -180 <= west < east <= 180
            and -90 <= south < north <= 90
            and east - west <= 0.1
            and north - south <= 0.1
        ):
            raise ValueError()
    except ValueError:
        raise DomainError(
            "invalid_input", "bbox must be west,south,east,north with extent at most 0.1 degrees."
        ) from None
    extent = func.ST_MakeEnvelope(west, south, east, north, 4326)
    features, truncated = [], False
    for model, geometry, layer in [
        (Building, Building.footprint, "building"),
        (Edge, Edge.geometry, "path"),
    ]:
        query = select(model, func.ST_AsGeoJSON(geometry)).where(
            model.dataset_revision_id == release.dataset_revision_id,
            model.visibility == "public",
            func.ST_Intersects(geometry, extent),
        )
        if model is Edge:
            visible_nodes = select(Node.id).where(
                Node.dataset_revision_id == release.dataset_revision_id, Node.visibility == "public"
            )
            query = query.where(
                Edge.from_node_id.in_(visible_nodes), Edge.to_node_id.in_(visible_nodes)
            )
        rows = db.execute(query.order_by(model.id).limit(1001)).all()
        truncated |= len(rows) > 1000
        for item, shape in rows[:1000]:
            properties = {"layer": layer}
            if model is Building:
                properties["name"] = item.name
            else:
                properties.update({"open": item.is_open, "kind": item.kind})
            features.append(
                MapFeature(id=item.id, geometry=json.loads(shape), properties=properties)
            )
    artifact = db.get(ReleaseArtifact, release.id)
    if artifact:
        for asset in artifact.content["assets"].values():
            for index, feature in enumerate(asset["geojson"]["features"]):
                shape = feature["geometry"]
                if db.scalar(
                    select(
                        func.ST_Intersects(
                            func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(shape)), 4326),
                            extent,
                        )
                    )
                ):
                    if len(features) >= 2500:
                        truncated = True
                        break
                    features.append(
                        MapFeature(
                            id=uuid5(UUID(asset["id"]), str(index)),
                            geometry=shape,
                            properties={
                                "layer": "overlay",
                                "name": feature["properties"]["label"],
                                "attribution": asset["attribution"],
                            },
                        )
                    )
    return MapOut(features=features, release_id=release.id, truncated=truncated)


@router.post("/routes", response_model=RouteOut)
def route(request: RouteRequest, db: DB, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return calculate_route(db, request)


def check_expected(release, expected):
    if expected is not None and expected != release.id:
        raise DomainError(
            "stale_release",
            "The campus release changed. Reload coherent campus data before trying again.",
            409,
        )


@router.get("/campuses/{campus_id}/artifacts/{release_id}/{artifact_checksum}.json")
def public_artifact(campus_id: UUID, release_id: UUID, artifact_checksum: str, db: DB):
    artifact = db.scalar(
        select(ReleaseArtifact).where(
            ReleaseArtifact.campus_id == campus_id,
            ReleaseArtifact.release_id == release_id,
            ReleaseArtifact.checksum == artifact_checksum,
        )
    )
    if not artifact:
        raise DomainError("location_not_found", "Public artifact not found.", 404)
    return Response(
        canonical(artifact.content),
        media_type="application/json",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": f'"{artifact.checksum}"',
            "Content-Disposition": 'attachment; filename="public-release.json"',
        },
    )


@router.get("/campuses/{campus_id}/directory")
def department_directory(campus_id: UUID, db: DB, expected_release_id: UUID | None = None):
    release = active_release(db, campus_id)
    check_expected(release, expected_release_id)
    artifact = db.get(ReleaseArtifact, release.id)
    return {
        "release_id": str(release.id),
        "departments": list(artifact.content["departments"].values()) if artifact else [],
    }


@router.get(
    "/campuses/{campus_id}/releases/{release_id}/floorplans/{layer_id}/{sha256}.png",
    response_class=Response,
)
def approved_floorplan(campus_id: UUID, release_id: UUID, layer_id: UUID, sha256: str, db: DB):
    import hashlib

    artifact = db.get(ReleaseArtifact, release_id)
    release = db.get(Release, release_id)
    descriptor = (
        artifact.content.get("floorplans", {}).get(str(layer_id))
        if artifact and artifact.campus_id == campus_id
        else None
    )
    if (
        not descriptor
        or descriptor["checksum"] != sha256
        or not release
        or release.campus_id != campus_id
    ):
        raise DomainError("location_not_found", "Approved public floorplan not found.", 404)
    layer = db.get(MapLayer, (release.dataset_revision_id, layer_id))
    if not layer or layer.campus_id != campus_id or hashlib.sha256(layer.png).hexdigest() != sha256:
        raise DomainError("location_not_found", "Approved public floorplan not found.", 404)
    return Response(
        layer.png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable", "ETag": f'"{sha256}"'},
    )


@router.get("/campuses/{campus_id}/floors", response_model=FloorsOut)
def public_floors(campus_id: UUID, db: DB, expected_release_id: UUID | None = None):
    from app.services.mixed_routes import floor_descriptors, release_projection

    release = active_release(db, campus_id)
    if expected_release_id and expected_release_id != release.id:
        raise DomainError(
            "stale_release", "The map has changed. Refresh all campus/floor data and retry.", 409
        )
    return {
        "release_id": release.id,
        "floors": floor_descriptors(release_projection(db, release), release),
    }
