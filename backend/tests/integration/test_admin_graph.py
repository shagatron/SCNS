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
    for key in ["id", "generated_at", "departure_at", "valid_until", "restriction_window_end"]:
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


def test_crossings_remain_disconnected_until_explicit_split_and_shared_node(
    client, bundle, identity
):
    headers, draft, path, state = start(client, bundle, identity)
    frame = next((i for i, f in state["frames"].items() if f["kind"] == "outdoor"))
    ids = [str(uuid4()) for _ in range(7)]
    a, b, c, d, e, f, junction = ids
    points = {a: [0.0026, 0.0024], b: [0.0032, 0.0024], c: [0.0029, 0.0021], d: [0.0029, 0.0027]}
    nodes = [
        {
            "entity": "nodes",
            "id": i,
            "data": {
                "frame_id": frame,
                "label": i,
                "point": {"type": "Point", "coordinates": point},
            },
        }
        for i, point in points.items()
    ]
    edge_a = {
        "frame_id": frame,
        "from_node_id": a,
        "to_node_id": b,
        "physical_path_id": str(uuid4()),
        "geometry": {"type": "LineString", "coordinates": [points[a], points[b]]},
        "evidence": "Synthetic crossing; no physical verification",
    }
    edge_b = {
        **edge_a,
        "from_node_id": c,
        "to_node_id": d,
        "physical_path_id": str(uuid4()),
        "geometry": {"type": "LineString", "coordinates": [points[c], points[d]]},
    }
    response = save(
        client,
        path,
        headers,
        1,
        nodes
        + [
            {"entity": "edges", "id": e, "data": edge_a},
            {"entity": "edges", "id": f, "data": edge_b},
        ],
    )
    assert response.status_code == 200, response.text
    assert len(response.json()["nodes"]) == len(state["nodes"]) + 4
    report = client.get(path + "/validation").json()
    assert any(
        x["code"] == "unmapped_intersection" and set(x["ids"]) == {e, f}
        for x in report["diagnostics"]
    )
    changes = [
        {
            "entity": "nodes",
            "id": junction,
            "data": {
                "frame_id": frame,
                "label": "Deliberate shared crossing",
                "point": {"type": "Point", "coordinates": [0.0029, 0.0024]},
            },
        },
        {"entity": "edges", "id": e},
        {"entity": "edges", "id": f},
    ]
    for edge in (edge_a, edge_b):
        for source, target, coords in [
            (edge["from_node_id"], junction, [points[edge["from_node_id"]], [0.0029, 0.0024]]),
            (junction, edge["to_node_id"], [[0.0029, 0.0024], points[edge["to_node_id"]]]),
        ]:
            changes.append(
                {
                    "entity": "edges",
                    "id": str(uuid4()),
                    "data": {
                        **edge,
                        "from_node_id": source,
                        "to_node_id": target,
                        "physical_path_id": str(uuid4()),
                        "geometry": {"type": "LineString", "coordinates": coords},
                    },
                }
            )
    response = save(client, path, headers, 2, changes)
    assert response.status_code == 200, response.text
    assert (
        sum(
            junction in (x["from_node_id"], x["to_node_id"])
            for x in response.json()["edges"].values()
        )
        == 4
    )
    assert not any(
        x["code"] == "unmapped_intersection" and e in x["ids"]
        for x in client.get(path + "/validation").json()["diagnostics"]
    )


def test_map_precision_dated_accessibility_anchor_update_and_near_duplicate_diagnostics(
    client, db, bundle, identity
):
    from datetime import date

    headers, draft, path, state = start(client, bundle, identity)
    frame = next((i for i, f in state["frames"].items() if f["kind"] == "outdoor"))
    a, b, e, r, physical, anchor = [str(uuid4()) for _ in range(6)]
    first = [0.002617737293243408, 0.002439938719937187]
    second = [0.002997737293243408, 0.002769938719937187]
    changes = [
        {
            "entity": "nodes",
            "id": i,
            "data": {
                "frame_id": frame,
                "label": i,
                "point": {"type": "Point", "coordinates": point},
            },
        }
        for i, point in [(a, first), (b, second)]
    ]
    edge = {
        "frame_id": frame,
        "from_node_id": a,
        "to_node_id": b,
        "physical_path_id": physical,
        "geometry": {"type": "LineString", "coordinates": [first, [0.00273, 0.00275], second]},
        "evidence": "Synthetic editor test; not a physical survey",
    }
    changes += [
        {"entity": "edges", "id": e, "data": edge},
        {
            "entity": "edges",
            "id": r,
            "data": {
                **edge,
                "from_node_id": b,
                "to_node_id": a,
                "geometry": {
                    "type": "LineString",
                    "coordinates": edge["geometry"]["coordinates"][::-1],
                },
            },
        },
    ]
    result = save(client, path, headers, 1, changes)
    assert result.status_code == 200, result.text
    stored = result.json()
    assert (
        stored["edges"][e]["geometry"]["coordinates"][0]
        == stored["nodes"][a]["point"]["coordinates"]
    )
    event = db.scalar(select(AuditEvent).where(AuditEvent.resource_id == e))
    assert event.after["distance_m"] == stored["edges"][e]["distance_m"]
    edge = edge_data(stored, e)
    reverse = edge_data(stored, r)
    for data in (edge, reverse):
        data["accessibility_status"] = "verified_step_free"
    attempt = save(
        client,
        path,
        headers,
        2,
        [{"entity": "edges", "id": e, "data": edge}, {"entity": "edges", "id": r, "data": reverse}],
    )
    assert attempt.status_code == 422 and "YYYY-MM-DD" in attempt.text
    for data in (edge, reverse):
        data["evidence"] = (
            f"Synthetic test source {date.today().isoformat()}; no physical verification."
        )
        data.update(width_m=1.8, slope_percent=3.4, step_count=0, surface="Synthetic concrete")
    result = save(
        client,
        path,
        headers,
        2,
        [{"entity": "edges", "id": e, "data": edge}, {"entity": "edges", "id": r, "data": reverse}],
    )
    assert result.status_code == 200, result.text
    for edge_id in (e, r):
        assert result.json()["edges"][edge_id]["width_m"] == 1.8
        assert result.json()["edges"][edge_id]["slope_percent"] == 3.4
        assert result.json()["edges"][edge_id]["step_count"] == 0
        assert result.json()["edges"][edge_id]["surface"] == "Synthetic concrete"
    place = next((i for i, p in state["places"].items() if p["visibility"] == "public"))
    data = {"place_id": place, "node_id": a, "accessibility_status": "unknown"}
    result = save(client, path, headers, 3, [{"entity": "anchors", "id": anchor, "data": data}])
    assert result.status_code == 200, result.text
    data.update(node_id=b, is_open=False)
    result = save(client, path, headers, 4, [{"entity": "anchors", "id": anchor, "data": data}])
    assert result.status_code == 200, result.text
    assert (
        result.json()["anchors"][anchor]["node_id"] == b
        and result.json()["anchors"][anchor]["is_open"] is False
    )
    near = str(uuid4())
    result = save(
        client,
        path,
        headers,
        5,
        [
            {
                "entity": "nodes",
                "id": near,
                "data": {
                    "frame_id": frame,
                    "label": "Nearly duplicate",
                    "point": {"type": "Point", "coordinates": [first[0] + 1e-06, first[1]]},
                },
            }
        ],
    )
    assert result.status_code == 200, result.text
    diagnostics = client.get(path + "/validation").json()["diagnostics"]
    assert any(x["code"] == "near_duplicate" and set(x["ids"]) == {a, near} for x in diagnostics)
    assert any(x["code"] == "components_step_free" for x in diagnostics)


@pytest.mark.parametrize(
    "field,value",
    [
        ("width_m", 0),
        ("width_m", -1),
        ("slope_percent", -1),
        ("step_count", -1),
        ("step_count", 1.5),
        ("surface", ""),
    ],
)
def test_invalid_measurement_does_not_consume_version(client, bundle, identity, field, value):
    headers, draft, path, state = start(client, bundle, identity)
    edge_id = next(iter(state["edges"]))
    data = edge_data(state, edge_id)
    data[field] = value
    response = save(client, path, headers, 1, [{"entity": "edges", "id": edge_id, "data": data}])
    assert response.status_code == 422, response.text
    assert client.get(path).json() == state
