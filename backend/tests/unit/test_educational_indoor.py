"""Isolated educational preview; no developer data or fabricated approvals."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.educational_indoor import DemoRequest, describe, identity, route, topology


def request(a, b, **kw):
    return DemoRequest(
        source_id=identity(a), destination_id=identity(b), expected_version="indoor-school-v1", **kw
    )


@pytest.mark.parametrize(
    "a,b,count,stairs",
    [
        ("a", "library", 3, 0),
        ("a", "c", 9, 1),
        ("c", "a", 9, 1),
        ("library", "reading", 7, 1),
        ("a", "a", 0, 0),
    ],
)
def test_computed_paths_and_unknown_metrics(a, b, count, stairs):
    result = route(request(a, b))
    assert result.traversal_count == count
    assert sum(s.kind == "stairs" for s in result.segments) == stairs
    assert result.distance_m is result.estimated_duration_s is None
    assert all(s.distance_m is s.estimated_duration_s is None for s in result.segments)
    assert all(s.distance_status == "unknown" for s in result.segments)
    assert all(s.floor_id == s.to_floor_id for s in result.segments if s.polyline)
    assert "release_id" not in result.model_dump() and '"verified":' not in result.model_dump_json()


def test_api_is_read_only_separate_namespace_and_validates_context(monkeypatch):
    from sqlalchemy.orm import Session

    monkeypatch.setattr(
        Session,
        "execute",
        lambda *a, **kw: pytest.fail("Educational preview must not query or mutate a database"),
    )
    with TestClient(app) as client:
        data = client.get("/api/v1/educational/indoor-school")
        assert data.status_code == 200 and data.headers["cache-control"] == "no-store"
        assert len(data.json()["floors"]) == 2 and len(data.json()["rooms"]) == 7
        body = request("a", "c").model_dump(mode="json")
        response = client.post("/api/v1/educational/indoor-school/routes", json=body)
        assert response.status_code == 200 and response.json()["traversal_count"] == 9
        assert (
            client.post(
                "/api/v1/educational/indoor-school/routes",
                json={**body, "expected_version": "stale"},
            ).status_code
            == 409
        )
        assert (
            client.post(
                "/api/v1/educational/indoor-school/routes",
                json={**body, "source_id": identity("foreign-campus-room")},
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/api/v1/educational/indoor-school/routes", json={**body, "cost_mode": "metric"}
            ).status_code
            == 422
        )
        response = client.post(
            "/api/v1/educational/indoor-school/routes",
            json=request("a", "isolated").model_dump(mode="json"),
        )
        assert response.status_code == 422 and response.json()["error"]["code"] == "demo_no_route"
        assert client.post("/api/v1/educational/indoor-school", json={}).status_code == 405


def test_topology_has_no_outdoor_links_approvals_scale_or_accessibility_evidence():
    data = describe()
    assert all(
        f.metres_per_pixel is None and f.navigation_mode == "directions_only" for f in data.floors
    )
    nodes, links = topology()
    assert all(n["floor"] in {"ground", "first"} for n in nodes.values())
    assert not any("isolated" in (a, b) for a, b, _ in links)
    assert all((b, a, k) in links for a, b, k in links)


def test_routes_follow_graph_changes_rather_than_saved_highlighted_results(monkeypatch):
    from app.core.errors import DomainError
    from app.services import educational_indoor

    nodes, links = topology()
    removed = {("ground-west", "ground-middle"), ("ground-middle", "ground-west")}
    monkeypatch.setattr(
        educational_indoor,
        "topology",
        lambda: (nodes, [(a, b, kind) for a, b, kind in links if (a, b) not in removed]),
    )
    with pytest.raises(DomainError) as failure:
        route(request("a", "library"))
    assert failure.value.code == "demo_no_route"
    assert route(request("a", "b")).traversal_count == 2
