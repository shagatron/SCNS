"""Deterministic synthetic fixes only, against actual indexed PostGIS/published graphs."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models.admin import AuditEvent
from tests.integration.test_closures import create, endpoint, payload, sign_in

pytestmark = pytest.mark.integration


def observation(**changes):
    return {
        "latitude": 0.0002,
        "longitude": 0.00015,
        "accuracy_m": 5,
        "observed_at": datetime.now(UTC).isoformat(),
        **changes,
    }


def match_payload(client, bundle, **changes):
    release = client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()
    return {
        "campus_id": str(bundle.campus.id),
        "observation": observation(),
        "expected_release_id": release["id"],
        "expected_closure_overlay_version": release["closure_overlay_version"],
        "profile": "shortest",
        **changes,
    }


def route_payload(bundle, value, node, **changes):
    library = next(p for p in bundle.places if p.code == "LIB")
    return {
        "campus_id": str(bundle.campus.id),
        "source": {
            "kind": "gps",
            **value["observation"],
            "confirmed_node_id": node,
            "confirmed": True,
        },
        "destination": {"place_id": str(library.id)},
        "profile": value["profile"],
        "expected_release_id": value["expected_release_id"],
        "expected_closure_overlay_version": value["expected_closure_overlay_version"],
        **changes,
    }


def test_indexed_pilot_match_confirmed_route_privacy_and_no_writes(client, db, bundle):
    before = db.scalar(select(func.count()).select_from(AuditEvent))
    value = match_payload(client, bundle)
    response = client.post("/api/v1/outdoor-location-match", json=value)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    match = response.json()
    assert match["candidates"][0]["label"] == "Gate"
    assert match["candidates"][0]["approach_distance_m"] == 0
    assert "latitude" not in response.text and "longitude" not in response.text
    route = client.post(
        "/api/v1/routes", json=route_payload(bundle, value, match["candidates"][0]["node_id"])
    )
    assert route.status_code == 200, route.text
    assert route.json()["distance_m"] == 256.88 and len(route.json()["segments"]) == 3
    assert "latitude" not in route.text and "longitude" not in route.text
    assert "excluded from distance/ETA" in route.text
    assert db.scalar(select(func.count()).select_from(AuditEvent)) == before


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"accuracy_m": 100}, "location_inaccurate"),
        ({"accuracy_m": 0}, "invalid_input"),
        ({"latitude": 91}, "invalid_input"),
        ({"observed_at": "2026-01-01T00:00:00"}, "invalid_input"),
        ({"observed_at": (datetime.now(UTC) - timedelta(minutes=5)).isoformat()}, "location_stale"),
        ({"observed_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat()}, "location_stale"),
        ({"latitude": 1, "longitude": 1}, "location_outside_campus"),
        ({"latitude": 0.00275, "longitude": 0.0035}, "location_no_suitable_path"),
        ({"latitude": 0.0008, "longitude": 0.0035}, "location_no_suitable_path"),
    ],
)
def test_bad_fixes_and_one_way_dead_end_offer_fallback(client, bundle, changes, code):
    response = client.post(
        "/api/v1/outdoor-location-match",
        json=match_payload(client, bundle, observation=observation(**changes)),
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == code
    assert "latitude" not in response.text and "longitude" not in response.text


def test_confirmation_versions_references_and_clock_are_rechecked(client, bundle):
    value = match_payload(client, bundle)
    node = client.post("/api/v1/outdoor-location-match", json=value).json()["candidates"][0][
        "node_id"
    ]
    base = route_payload(bundle, value, node)
    for changes, expected in [
        ({"confirmed": False}, 422),
        ({"confirmed_node_id": str(uuid4())}, 422),
        ({"observed_at": "2025-01-01T00:00:00Z"}, 422),
    ]:
        assert (
            client.post(
                "/api/v1/routes", json={**base, "source": {**base["source"], **changes}}
            ).status_code
            == expected
        )
    for changes in (
        {"expected_release_id": str(uuid4())},
        {"expected_closure_overlay_version": 100},
    ):
        assert client.post("/api/v1/routes", json={**base, **changes}).status_code == 409
        assert (
            client.post("/api/v1/outdoor-location-match", json={**value, **changes}).status_code
            == 409
        )
    assert (
        client.post("/api/v1/routes", json={**base, "expected_release_id": None}).status_code == 422
    )
    assert (
        client.post(
            "/api/v1/outdoor-location-match", json={**value, "campus_id": str(uuid4())}
        ).status_code
        == 404
    )


def test_matching_and_routing_observe_live_restrictions(client, bundle, identity):
    value = match_payload(client, bundle)
    match = client.post("/api/v1/outdoor-location-match", json=value).json()
    route = route_payload(bundle, value, match["candidates"][0]["node_id"])
    h = sign_in(client, identity)
    targets = client.get(endpoint(bundle)).json()["targets"]
    gate_path = next(
        t for t in targets if t["kind"] == "outdoor_path" and "Gate → Courtyard" in t["label"]
    )
    create(client, bundle, h, payload(client, bundle, "outdoor_path", gate_path["id"]))
    assert client.post("/api/v1/routes", json=route).status_code == 409
    fresh = match_payload(client, bundle)
    result = client.post("/api/v1/outdoor-location-match", json=fresh)
    assert (
        result.status_code == 422 and result.json()["error"]["code"] == "location_no_suitable_path"
    )
