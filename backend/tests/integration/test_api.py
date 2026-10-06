from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.cli.dataset import seed_bundle
from app.models import Anchor, Edge, Frame, Node, Place, Release, Revision

pytestmark = pytest.mark.integration


def body(bundle, source="GATE", destination="LIB", **extra):
    places = {p.code: str(p.id) for p in bundle.places}
    return {
        "campus_id": str(bundle.campus.id),
        "source": {"kind": "place", "place_id": places[source]},
        "destination": {"kind": "place", "place_id": places[destination]},
        **extra,
    }


def test_health_catalog_alias_filters_pagination_and_public_projection(client, bundle):
    campus = str(bundle.campus.id)
    assert client.get("/api/v1/health/ready").json()["database"] == "ready"
    assert client.get("/api/v1/campuses").json()[0]["is_demo"]
    search = client.get(f"/api/v1/campuses/{campus}/search?q=BOOKS").json()
    assert [p["code"] for p in search["items"]] == ["LIB"]
    assert client.get(f"/api/v1/campuses/{campus}/search?kind=water").json()["total"] == 1
    first = client.get(f"/api/v1/campuses/{campus}/search?limit=3").json()
    second = client.get(f"/api/v1/campuses/{campus}/search?limit=3&offset=3").json()
    assert first["total"] == 10
    assert not {p["id"] for p in first["items"]} & {p["id"] for p in second["items"]}
    restricted = next(p for p in bundle.places if p.visibility == "restricted")
    assert client.get(f"/api/v1/places/{restricted.id}").status_code == 404
    assert client.get(f"/api/v1/campuses/{campus}/search?q=Restricted").json()["total"] == 0
    features = client.get(f"/api/v1/campuses/{campus}/map?bbox=-.001,-.001,.004,.004").json()[
        "features"
    ]
    private_ids = {str(e.id) for e in bundle.edges if e.visibility == "restricted"}
    assert not private_ids & {f["id"] for f in features}
    assert len([f for f in features if f["properties"]["layer"] == "building"]) == 3


def test_routes_use_connected_stored_edges_and_polyline_distance(client, db, bundle, seeded):
    response = client.post("/api/v1/routes", json=body(bundle))
    assert response.status_code == 200, response.text
    result = response.json()
    assert response.headers["cache-control"] == "no-store"
    assert result["release_id"] == str(seeded.id)
    stored = {
        str(e.id): e
        for e in db.scalars(
            select(Edge).where(Edge.dataset_revision_id == seeded.dataset_revision_id)
        )
    }
    assert result["distance_m"] == round(
        sum(stored[s["edge_id"]].distance_m for s in result["segments"]), 2
    )
    assert result["estimated_duration_s"] == pytest.approx(result["distance_m"] / 1.4, abs=0.1)
    for previous, current in zip(result["segments"], result["segments"][1:], strict=False):
        assert previous["to_node_id"] == current["from_node_id"]
        assert previous["geometry"]["coordinates"][-1] == current["geometry"]["coordinates"][0]
    assert all(
        stored[s["edge_id"]].is_open and stored[s["edge_id"]].visibility == "public"
        for s in result["segments"]
    )
    length, straight = db.execute(
        text(
            "SELECT ST_Length(geometry::geography), ST_Distance(ST_StartPoint(geometry)::geography, ST_EndPoint(geometry)::geography) FROM navigation_edges WHERE ST_NPoints(geometry) > 2 LIMIT 1"
        )
    ).one()
    assert length > straight


@pytest.mark.parametrize(
    "source,destination,profile,code",
    [
        ("GATE", "GARDEN", "shortest", "no_route"),
        ("GATE", "HELP", "shortest", "location_not_routable"),
        ("EAST", "GATE", "shortest", "no_route"),
        ("GATE", "EAST", "step_free", "no_verified_step_free_route"),
        ("GATE", "STAFF", "shortest", "location_not_found"),
    ],
)
def test_honest_domain_failures(client, bundle, source, destination, profile, code):
    response = client.post(
        "/api/v1/routes", json=body(bundle, source, destination, profile=profile)
    )
    assert response.status_code in {404, 422}
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["request_id"]


def test_same_place_step_free_and_stale_release(client, bundle):
    same = client.post("/api/v1/routes", json=body(bundle, "LIB", "LIB")).json()
    assert same["distance_m"] == 0 and same["segments"] == []
    ordinary = client.post("/api/v1/routes", json=body(bundle, "GATE", "ACA")).json()
    accessible = client.post(
        "/api/v1/routes", json=body(bundle, "GATE", "ACA", profile="step_free")
    ).json()
    assert accessible["distance_m"] > ordinary["distance_m"]
    stairs = {str(e.id) for e in bundle.edges if e.kind == "stairs"}
    assert not stairs & {s["edge_id"] for s in accessible["segments"]}
    stale = client.post("/api/v1/routes", json=body(bundle, expected_release_id=str(uuid4())))
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale_release"


def test_validation_and_private_paths(client, bundle):
    assert client.post("/api/v1/routes", json=body(bundle, profile="magic")).status_code == 422
    assert (
        client.post(
            "/api/v1/routes", json=body(bundle, departure_at="2026-10-06T09:00:00")
        ).status_code
        == 422
    )
    for bbox in ["bad", "0,0,100,100", "nan,0,.01,.01"]:
        assert (
            client.get(
                f"/api/v1/campuses/{bundle.campus.id}/map", params={"bbox": bbox}
            ).status_code
            == 422
        )
    for path in [
        "/data/raw/floorplans/secret.pdf",
        "/storage/uploads/secret.pdf",
        "/api/v1/admin/revisions",
    ]:
        assert client.get(path).status_code == 404


def test_idempotent_seed_graph_change_new_release_and_old_immutability(client, db, bundle, seeded):
    again = seed_bundle(db, bundle)
    assert again.id == seeded.id
    old = client.post("/api/v1/routes", json=body(bundle, "GATE", "ACA")).json()
    modified = bundle.model_copy(deep=True)
    for edge in modified.edges:
        if edge.kind == "stairs":
            edge.is_open = False
    new = seed_bundle(db, modified)
    result = client.post("/api/v1/routes", json=body(bundle, "GATE", "ACA")).json()
    assert result["release_id"] == str(new.id) != old["release_id"]
    assert result["distance_m"] > old["distance_m"]
    assert db.scalar(select(func.count()).select_from(Release)) == 2
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(
            text("UPDATE navigation_edges SET is_open=false WHERE dataset_revision_id=:rev"),
            {"rev": seeded.dataset_revision_id},
        )
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(
            text("UPDATE dataset_revisions SET status='draft' WHERE id=:rev"),
            {"rev": seeded.dataset_revision_id},
        )


def test_draft_invisible_and_cross_revision_references_rejected(client, db, bundle, seeded):
    draft = Revision(
        id=uuid4(), campus_id=bundle.campus.id, version=2, status="draft", checksum="a" * 64
    )
    db.add(draft)
    db.flush()
    source_place = db.scalar(
        select(Place).where(Place.dataset_revision_id == seeded.dataset_revision_id)
    )
    place = Place(
        id=uuid4(),
        dataset_revision_id=draft.id,
        campus_id=bundle.campus.id,
        code="DRAFT",
        name="Secret draft",
        kind="help",
        description="unpublished",
        aliases=[],
        search_text="secret draft",
        visibility="public",
        point=source_place.point,
    )
    db.add(place)
    db.flush()
    assert client.get(f"/api/v1/places/{place.id}").status_code == 404
    assert client.get(f"/api/v1/campuses/{bundle.campus.id}/search?q=Secret").json()["total"] == 0
    node = db.scalar(select(Node).where(Node.dataset_revision_id == seeded.dataset_revision_id))
    with pytest.raises(DBAPIError), db.begin_nested():
        db.add(
            Anchor(
                id=uuid4(),
                dataset_revision_id=draft.id,
                campus_id=bundle.campus.id,
                place_id=place.id,
                node_id=node.id,
                accessibility_status="unknown",
            )
        )
        db.flush()
    with pytest.raises(DBAPIError), db.begin_nested():
        db.add(
            Release(
                id=uuid4(),
                campus_id=bundle.campus.id,
                dataset_revision_id=draft.id,
                checksum=draft.checksum,
            )
        )
        db.flush()


def test_indoor_frame_constraints(db, bundle, seeded):
    revision = Revision(
        id=uuid4(), campus_id=bundle.campus.id, version=2, status="draft", checksum="b" * 64
    )
    db.add(revision)
    db.flush()
    with pytest.raises(DBAPIError), db.begin_nested():
        db.add(
            Frame(
                id=uuid4(),
                dataset_revision_id=revision.id,
                campus_id=bundle.campus.id,
                code="unknown-image",
                kind="indoor",
            )
        )
        db.flush()
    frame = Frame(
        id=uuid4(),
        dataset_revision_id=revision.id,
        campus_id=bundle.campus.id,
        code="floor-1",
        kind="indoor",
        width_px=800,
        height_px=600,
        metres_per_pixel=0.05,
    )
    db.add(frame)
    db.flush()
    node = Node(
        id=uuid4(),
        dataset_revision_id=revision.id,
        campus_id=bundle.campus.id,
        frame_id=frame.id,
        label="Indoor foundation",
        visibility="public",
        x_px=20,
        y_px=30,
    )
    db.add(node)
    db.flush()
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(text("UPDATE navigation_nodes SET x_px=801 WHERE id=:id"), {"id": node.id})


def test_failed_seed_rolls_back_everything(db, bundle, seeded):
    modified = bundle.model_copy(deep=True)
    modified.nodes[0].frame_id = uuid4()  # Simulates invalid data bypassing the DTO boundary.
    count = db.scalar(select(func.count()).select_from(Revision))
    with pytest.raises(DBAPIError), db.begin_nested():
        seed_bundle(db, modified)
    assert db.scalar(select(func.count()).select_from(Revision)) == count
