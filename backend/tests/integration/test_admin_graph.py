"""Real PostGIS graph writes, scope, geometry, rollback and frozen-public isolation."""

from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select

from app.models import Revision
from app.models.admin import AuditEvent, RoleAssignment
from tests.integration.test_admin import identity as admin_identity
from tests.integration.test_admin import make_draft, sign_in, version

pytestmark = pytest.mark.integration


@pytest.fixture
def identity(db, bundle, seeded):
    return admin_identity.__wrapped__(db, bundle, seeded)


def start(client, bundle, identity):
    headers = sign_in(client, identity)
    draft = make_draft(client, bundle, headers)
    path = f"/api/v1/admin/campuses/{bundle.campus.id}/drafts/{draft['id']}/graph"
    return (headers, draft, path, client.get(path).json())


def node_data(state, identity):
    return deepcopy(
        {
            k: state["nodes"][identity][k]
            for k in ("frame_id", "label", "visibility", "point", "evidence")
        }
    )


def edge_data(state, identity):
    return deepcopy({k: v for k, v in state["edges"][identity].items() if k != "distance_m"})


def save(client, path, headers, number, changes):
    return client.post(path, json={"changes": changes}, headers=version(headers, number))


@pytest.mark.parametrize(
    "role,read,write",
    [
        ("editor", 200, 200),
        ("system_admin", 200, 200),
        ("reviewer_publisher", 200, 403),
        ("operations", 403, 403),
    ],
)
def test_graph_permissions_and_live_scope(client, db, bundle, identity, role, read, write):
    headers, draft, path, state = start(client, bundle, identity)
    db.execute(delete(RoleAssignment))
    db.add(RoleAssignment(user_id=identity[0].id, campus_id=bundle.campus.id, role=role))
    db.flush()
    assert client.get(path).status_code == read
    assert client.get(path + "/validation").status_code == read
    identity_id = next(iter(state["nodes"]))
    data = node_data(state, identity_id)
    data["label"] = "Updated by scoped editor"
    response = save(
        client, path, headers, 1, [{"entity": "nodes", "id": identity_id, "data": data}]
    )
    assert response.status_code == write, response.text
    assert client.get(path.replace(str(bundle.campus.id), str(uuid4()))).status_code == 403
    assert (
        save(
            client,
            path.replace(str(bundle.campus.id), str(uuid4())),
            headers,
            1,
            [{"entity": "nodes", "id": identity_id, "data": data}],
        ).status_code
        == 403
    )
    assert client.get(path.replace(draft["id"], str(uuid4()))).status_code == (
        404 if read == 200 else 403
    )


def test_move_recomputes_full_geometry_audit_concurrency_and_public_isolation(
    client, db, bundle, identity
):
    headers, draft, path, state = start(client, bundle, identity)
    public = f"/api/v1/campuses/{bundle.campus.id}"
    before = [
        client.get(public + "/release").json(),
        client.get(public + "/search").json(),
        client.get(public + "/map?bbox=-.001,-.001,.004,.004").json(),
    ]
    places = {p.code: str(p.id) for p in bundle.places}
    route = {
        "campus_id": str(bundle.campus.id),
        "source": {"kind": "place", "place_id": places["GATE"]},
        "destination": {"kind": "place", "place_id": places["LIB"]},
    }
    route_before = client.post("/api/v1/routes", json=route).json()
    identity_id = next(
        (
            i
            for i, n in state["nodes"].items()
            if n["visibility"] == "public"
            and any(e["from_node_id"] == i for e in state["edges"].values())
        )
    )
    data = node_data(state, identity_id)
    data["point"]["coordinates"][0] += 2e-05
    data["label"] = "Moved draft node"
    data["evidence"] = "Synthetic editor exercise; no field verification."
    assert (
        client.post(
            path,
            json={"changes": [{"entity": "nodes", "id": identity_id, "data": data}]},
            headers=headers,
        ).status_code
        == 428
    )
    assert (
        client.post(
            path,
            json={"changes": [{"entity": "nodes", "id": identity_id, "data": data}]},
            headers={"Origin": headers["Origin"], "If-Match": '"1"'},
        ).status_code
        == 403
    )
    response = save(
        client, path, headers, 1, [{"entity": "nodes", "id": identity_id, "data": data}]
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["revision_version"] == 2
    for edge_id, edge in state["edges"].items():
        if identity_id not in (edge["from_node_id"], edge["to_node_id"]):
            continue
        updated = result["edges"][edge_id]
        assert updated["accessibility_status"] == "unknown"
        assert updated["geometry"]["coordinates"][1:-1] == edge["geometry"]["coordinates"][1:-1]
        assert updated["distance_m"] != edge["distance_m"]
    stale = save(client, path, headers, 1, [{"entity": "nodes", "id": identity_id, "data": data}])
    assert stale.status_code == 409
    assert client.get(path).json() == result
    events = db.scalars(select(AuditEvent).where(AuditEvent.action.like("graph.%"))).all()
    assert len(events) > 1 and all(
        e.actor_id == identity[0].id and str(e.revision_id) == draft["id"] and e.before and e.after
        for e in events
    )
    assert [
        client.get(public + "/release").json(),
        client.get(public + "/search").json(),
        client.get(public + "/map?bbox=-.001,-.001,.004,.004").json(),
    ] == before
    route_after = client.post("/api/v1/routes", json=route).json()
    for key in ["id", "generated_at", "departure_at"]:
        route_before.pop(key)
        route_after.pop(key)
    assert route_after == route_before


def test_new_paired_polyline_anchor_edit_and_explicit_cascade(client, db, bundle, identity):
    headers, draft, path, state = start(client, bundle, identity)
    frame = next((i for i, f in state["frames"].items() if f["kind"] == "outdoor"))
    a, b, e, r, p, anchor = map(str, [uuid4() for _ in range(6)])
    nodes = [
        {
            "entity": "nodes",
            "id": i,
            "data": {
                "frame_id": frame,
                "label": label,
                "point": {"type": "Point", "coordinates": point},
            },
        }
        for i, label, point in [(a, "New start", [0.0025, 0.0025]), (b, "New end", [0.003, 0.0025])]
    ]
    data = {
        "frame_id": frame,
        "from_node_id": a,
        "to_node_id": b,
        "physical_path_id": p,
        "geometry": {
            "type": "LineString",
            "coordinates": [[0.0025, 0.0025], [0.0027, 0.0028], [0.003, 0.0025]],
        },
        "evidence": "Synthetic test 2026-10-07, no survey",
    }
    reverse = {
        **data,
        "from_node_id": b,
        "to_node_id": a,
        "geometry": {"type": "LineString", "coordinates": data["geometry"]["coordinates"][::-1]},
    }
    place = next((i for i, x in state["places"].items() if x["visibility"] == "public"))
    changes = nodes + [
        {"entity": "edges", "id": e, "data": data},
        {"entity": "edges", "id": r, "data": reverse},
        {"entity": "anchors", "id": anchor, "data": {"place_id": place, "node_id": a}},
    ]
    response = save(client, path, headers, 1, changes)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["edges"][e]["distance_m"] > 55.6
    assert result["edges"][e]["accessibility_status"] == "unknown"
    data = edge_data(result, e)
    reverse = edge_data(result, r)
    for fields in [data, reverse]:
        fields.update(
            visibility="restricted",
            is_open=False,
            kind="ramp",
            accessibility_status="not_step_free",
        )
    assert (
        save(
            client,
            path,
            headers,
            2,
            [
                {"entity": "edges", "id": e, "data": data},
                {"entity": "edges", "id": r, "data": reverse},
            ],
        ).status_code
        == 200
    )
    bad = save(client, path, headers, 3, [{"entity": "nodes", "id": a}])
    assert bad.status_code == 422
    assert "Restore the endpoint" in bad.text
    assert client.get(path).json()["revision_version"] == 3
    response = save(
        client,
        path,
        headers,
        3,
        [
            {"entity": "edges", "id": e},
            {"entity": "edges", "id": r},
            {"entity": "anchors", "id": anchor},
            {"entity": "nodes", "id": a},
            {"entity": "nodes", "id": b},
        ],
    )
    assert response.status_code == 200, response.text
    assert a not in response.json()["nodes"] and anchor not in response.json()["anchors"]


@pytest.mark.parametrize(
    "failure", ["missing", "geometry", "boundary", "pair", "visibility", "stairs", "evidence"]
)
def test_bad_combined_write_rolls_back_everything(client, db, bundle, identity, failure):
    headers, draft, path, state = start(client, bundle, identity)
    edge_id = next(iter(state["edges"]))
    data = edge_data(state, edge_id)
    if failure == "missing":
        data["to_node_id"] = str(uuid4())
    if failure == "geometry":
        data["geometry"]["coordinates"].insert(1, data["geometry"]["coordinates"][0])
    if failure == "boundary":
        data["geometry"]["coordinates"].insert(1, [1, 1])
    if failure == "pair":
        data["is_open"] = not data["is_open"]
    if failure == "visibility":
        data["from_node_id"] = next(
            (i for i, n in state["nodes"].items() if n["visibility"] == "restricted")
        )
    if failure == "stairs":
        data.update(kind="stairs", accessibility_status="verified_step_free")
    if failure == "evidence":
        data.update(accessibility_status="verified_step_free", evidence=" ")
    node_id = next(iter(state["nodes"]))
    node = node_data(state, node_id)
    node["label"] = "Must roll back"
    response = save(
        client,
        path,
        headers,
        1,
        [
            {"entity": "nodes", "id": node_id, "data": node},
            {"entity": "edges", "id": edge_id, "data": data},
        ],
    )
    assert response.status_code == 422, response.text
    assert client.get(path).json() == state
    assert (
        db.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.action.like("graph.%"))
        )
        == 0
    )
    assert db.get(Revision, draft["id"]).edit_version == 1


def test_late_write_failure_rolls_back_nodes_version_and_audit(
    client, db, bundle, identity, monkeypatch
):
    from app.services import admin_graph

    headers, draft, path, state = start(client, bundle, identity)
    old_guard = admin_graph.final_graph_guard

    def fail(*args):
        old_guard(*args)
        raise ValueError("Injected final integrity failure")

    monkeypatch.setattr(admin_graph, "final_graph_guard", fail)
    node_id = next(iter(state["nodes"]))
    data = node_data(state, node_id)
    data["label"] = "Late failure"
    response = save(client, path, headers, 1, [{"entity": "nodes", "id": node_id, "data": data}])
    assert response.status_code == 422
    assert client.get(path).json() == state
    assert (
        db.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.action.like("graph.%"))
        )
        == 0
    )


def test_validation_route_preview_and_frozen_rejection(client, bundle, identity, seeded):
    headers, draft, path, state = start(client, bundle, identity)
    result = client.get(path + "/validation")
    assert result.status_code == 200, result.text
    assert result.json()["errors"] == 0 and result.json()["warnings"] > 0
    assert any(d["code"] == "connectivity_step_free" for d in result.json()["diagnostics"])
    places = {p.code: str(p.id) for p in bundle.places}
    response = client.get(
        path + "/route-test", params={"source": places["GATE"], "target": places["LIB"]}
    )
    assert response.status_code == 200
    assert response.json()["found"] and len(response.json()["edge_ids"]) == 3
    assert round(response.json()["distance_m"], 2) == 256.88
    assert (
        client.get(
            path + "/route-test", params={"source": str(uuid4()), "target": places["LIB"]}
        ).status_code
        == 404
    )
    assert client.get(path.replace(draft["id"], str(seeded.dataset_revision_id))).status_code == 404
    node_id = next(iter(state["nodes"]))
    assert (
        save(
            client,
            path.replace(draft["id"], str(seeded.dataset_revision_id)),
            headers,
            1,
            [{"entity": "nodes", "id": node_id}],
        ).status_code
        == 404
    )
