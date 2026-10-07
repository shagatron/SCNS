"""Floor-local editor boundaries on isolated real PostGIS, never developer data."""

import json
from copy import deepcopy
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import DBAPIError

from app.models import Place, Revision
from app.models.admin import AuditEvent, RoleAssignment
from app.models.indoor import IndoorAccess, IndoorEdge, IndoorNode, Room
from tests.integration.test_admin import identity as owner_fixture
from tests.integration.test_admin import make_draft, sign_in, version
from tests.integration.test_floorplans import apply, create, current, ready
from tests.integration.test_publication import ack, expectations
from tests.integration.test_publication import reviewer as reviewer_fixture
from tests.unit.test_floorplan_contract import measure

pytestmark = pytest.mark.integration
FIXTURE = Path(__file__).resolve().parents[3] / "data/demo/indoor/synthetic-ground.json"


@pytest.fixture
def identity(db, bundle, seeded):
    return owner_fixture.__wrapped__(db, bundle, seeded)


@pytest.fixture
def reviewer(db, bundle):
    return reviewer_fixture.__wrapped__(db, bundle)


def prepared(client, db, bundle, identity, reviewer, metric=True):
    h = sign_in(client, identity)
    draft, path, floor = create(client, bundle, h)
    job = ready(client, db, path, h, floor)
    result = apply(client, path, h, job)
    assert result.status_code == 200, result.text
    layer = result.json()["layer_id"]
    data = client.get(path + "/floors").json()["floors"][0]
    if metric:
        r = client.post(
            path + f"/floors/{floor}/calibration",
            json=measure(),
            headers=version(h, current(client, path)),
        )
        assert r.status_code == 200, r.text
    rh = sign_in(client, reviewer)
    r = client.post(
        path + f"/sources/{data['layer']['source_id']}/approve",
        headers=version(rh, current(client, path)),
    )
    assert r.status_code == 200, r.text
    if metric:
        r = client.post(
            path + f"/floors/{floor}/calibration/approve",
            headers=version(rh, current(client, path)),
        )
        assert r.status_code == 200, r.text
    h = sign_in(client, identity)
    return draft, path, floor, layer, h


def fixture_payload(layer, mode="metric"):
    data = json.loads(FIXTURE.read_text())["records"]
    return {
        "layer_id": layer,
        "mode": mode,
        "changes": [
            {"entity": entity, "id": id, "data": item}
            for entity, items in data.items()
            for id, item in items.items()
        ],
    }


def save(client, path, floor, h, payload, v=None):
    return client.patch(
        path + f"/floors/{floor}/indoor",
        json=payload,
        headers=version(h, v or current(client, path)),
    )


def test_full_local_topology_canonical_links_metric_audit_and_public_isolation(
    client, db, bundle, identity, reviewer
):
    draft, path, floor, layer, h = prepared(client, db, bundle, identity, reviewer)
    old = client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()["id"]
    v = current(client, path)
    r = save(client, path, floor, h, fixture_payload(layer))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["revision_version"] == v + 1
    assert len(data["rooms"]) == 3 and len(data["edges"]) == 10 and len(data["access"]) == 3
    edge = next(
        e for e in data["edges"].values() if e["polyline"] == [[100, 100], [200, 100], [300, 100]]
    )
    key = next(k for k, e in data["edges"].items() if e == edge)
    assert data["metrics"][key] == {"distance_m": 10, "distance_status": "calibrated"}
    assert edge["width_m"] is None and edge["accessibility_status"] == "unknown"
    room_id = next(k for k, r in data["rooms"].items() if r["code"] == "101")
    place = db.get(Place, (UUID(draft["id"]), UUID(room_id)))
    assert place.point is None and place.aliases == ["Synthetic quiet study"]
    events = db.scalars(select(AuditEvent).where(AuditEvent.action == "indoor.patch")).all()
    assert len(events) == 1 and events[0].actor_id == identity[0].id
    assert events[0].after["floor_id"] == floor and events[0].after["layer_id"] == layer
    public = client.get(f"/api/v1/campuses/{bundle.campus.id}/directory").json()
    assert room_id not in json.dumps(public)
    assert client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()["id"] == old
    val = client.get(path + f"/floors/{floor}/indoor/validation").json()
    assert val["errors"] == 0 and any(
        d["code"] == "indoor_3c_unavailable" for d in val["diagnostics"]
    )
    assert save(client, path, floor, h, fixture_payload(layer), v).status_code == 409
    assert db.scalar(select(func.count()).select_from(Room)) == 3


@pytest.mark.parametrize(
    "role,read,write",
    [
        ("editor", 200, 200),
        ("reviewer_publisher", 200, 403),
        ("operations", 403, 403),
        ("system_admin", 200, 200),
    ],
)
def test_indoor_roles_campus_isolation_and_csrf(
    client, db, bundle, identity, reviewer, role, read, write
):
    _, path, floor, layer, h = prepared(client, db, bundle, identity, reviewer)
    db.execute(delete(RoleAssignment).where(RoleAssignment.user_id == identity[0].id))
    db.add(RoleAssignment(user_id=identity[0].id, campus_id=bundle.campus.id, role=role))
    db.flush()
    h = sign_in(client, identity)
    url = path + f"/floors/{floor}/indoor"
    assert client.get(url).status_code == read
    assert (
        save(
            client,
            path,
            floor,
            h,
            fixture_payload(layer),
            current(client, path) if read == 200 else 6,
        ).status_code
        == write
    )
    assert client.get(url.replace(str(bundle.campus.id), str(uuid4()))).status_code == 403
    assert (
        client.patch(
            url,
            json=fixture_payload(layer),
            headers={"Origin": "http://127.0.0.1:5173", "If-Match": '"7"'},
        ).status_code
        == 403
    )
    client.cookies.clear()
    assert client.get(url).status_code == 401


@pytest.mark.parametrize(
    "failure",
    [
        "bounds",
        "pair",
        "door",
        "endpoint",
        "loop",
        "duplicate",
        "evidence",
        "floor",
        "layer",
        "department",
    ],
)
def test_invalid_atomic_patches_no_partial_write_or_audit(
    client, db, bundle, identity, reviewer, failure
):
    draft, path, floor, layer, h = prepared(client, db, bundle, identity, reviewer)
    payload = fixture_payload(layer)
    rooms = [x for x in payload["changes"] if x["entity"] == "rooms"]
    nodes = [x for x in payload["changes"] if x["entity"] == "nodes"]
    edges = [x for x in payload["changes"] if x["entity"] == "edges"]
    access = [x for x in payload["changes"] if x["entity"] == "access"]
    if failure == "bounds":
        rooms[0]["data"]["x_px"] = 700
    elif failure == "pair":
        edges[1]["data"]["is_open"] = False
    elif failure == "door":
        access[0]["data"]["node_id"] = nodes[0]["id"]
    elif failure == "endpoint":
        edges[0]["data"]["polyline"][0] = [2, 3]
    elif failure == "loop":
        edges[0]["data"]["polyline"] = [[100, 100], [300, 200], [100, 200], [300, 100]]
        edges[1]["data"]["polyline"] = edges[0]["data"]["polyline"][::-1]
    elif failure == "duplicate":
        rooms[1]["data"]["code"] = rooms[0]["data"]["code"]
    elif failure == "evidence":
        access[0]["data"]["accessibility_status"] = "verified_step_free"
    elif failure == "floor":
        edges[0]["data"]["to_node_id"] = str(uuid4())
    elif failure == "layer":
        payload["layer_id"] = str(uuid4())
    elif failure == "department":
        rooms[0]["data"]["department_ids"] = [str(uuid4())]
    v = current(client, path)
    r = save(client, path, floor, h, payload)
    assert r.status_code in (409, 422), r.text
    assert current(client, path) == v
    assert not db.scalar(select(func.count()).select_from(Room))
    assert not db.scalar(select(func.count()).select_from(IndoorEdge))
    assert not db.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "indoor.patch")
    )
    assert db.get(Revision, UUID(draft["id"])).status == "draft"


def test_dependency_deletion_move_and_sql_guards(client, db, bundle, identity, reviewer):
    draft, path, floor, layer, h = prepared(client, db, bundle, identity, reviewer)
    r = save(client, path, floor, h, fixture_payload(layer))
    assert r.status_code == 200, r.text
    data = r.json()
    node_id = next(k for k, n in data["nodes"].items() if n["label"] == "Synthetic west")
    v = current(client, path)
    bad = {"layer_id": layer, "changes": [{"entity": "nodes", "id": node_id}]}
    assert save(client, path, floor, h, bad).status_code == 422
    assert current(client, path) == v
    moved = deepcopy(data["nodes"][node_id])
    moved["x_px"] = 90
    update = [{"entity": "nodes", "id": node_id, "data": moved}]
    for id, e in data["edges"].items():
        if node_id in [e["from_node_id"], e["to_node_id"]]:
            e = deepcopy(e)
            e["polyline"][0 if e["from_node_id"] == node_id else -1] = [90, 100]
            update.append({"entity": "edges", "id": id, "data": e})
    r = save(client, path, floor, h, {"layer_id": layer, "changes": update})
    assert r.status_code == 200, r.text
    assert (
        client.post(
            path + f"/floors/{floor}/calibration",
            json=measure(),
            headers=version(h, current(client, path)),
        ).status_code
        == 409
    )
    assert (
        client.request(
            "DELETE",
            path + f"/floors/{floor}",
            json={"remove_layer_ids": [layer]},
            headers=version(h, current(client, path)),
        ).status_code
        == 409
    )
    assert (
        client.delete(
            path + f"/catalog/buildings/{bundle.buildings[0].id}",
            headers=version(h, current(client, path)),
        ).status_code
        == 409
    )
    from tests.integration.test_floorplans import floor_payload

    assert (
        client.put(
            path + f"/floors/{floor}",
            json={**floor_payload(bundle), "visibility": "restricted"},
            headers=version(h, current(client, path)),
        ).status_code
        == 409
    )
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(
            text(
                "UPDATE floors SET visibility='restricted' WHERE dataset_revision_id=:revision AND id=:floor"
            ),
            {"revision": draft["id"], "floor": floor},
        )
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(
            text("UPDATE indoor_edges SET distance_m=999 WHERE dataset_revision_id=:r"),
            {"r": draft["id"]},
        )
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(
            text("UPDATE indoor_nodes SET x_px=99 WHERE dataset_revision_id=:r AND id=:id"),
            {"r": draft["id"], "id": node_id},
        )
        db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    r = save(
        client,
        path,
        floor,
        h,
        {
            "layer_id": layer,
            "changes": [
                {"entity": e, "id": id}
                for e in ["access", "edges", "nodes", "rooms"]
                for id in data[e]
            ],
        },
    )
    assert r.status_code == 200, r.text
    assert not db.scalar(select(func.count()).select_from(IndoorNode))
    assert not db.scalar(select(func.count()).select_from(IndoorAccess))


def test_unknown_scale_explicit_mode_and_live_prerequisites(client, db, bundle, identity, reviewer):
    _, path, floor, layer, h = prepared(client, db, bundle, identity, reviewer, False)
    assert save(client, path, floor, h, fixture_payload(layer)).status_code == 409
    r = save(client, path, floor, h, fixture_payload(layer, "directions_only"))
    assert r.status_code == 200, r.text
    assert all(
        m["distance_m"] is None and m["distance_status"] == "unknown"
        for m in r.json()["metrics"].values()
    )
    db.execute(delete(RoleAssignment).where(RoleAssignment.user_id == reviewer[0].id))
    db.flush()
    assert (
        save(client, path, floor, h, fixture_payload(layer, "directions_only")).status_code == 409
    )


def test_exact_review_projection_clone_and_retained_rollback(
    client, db, bundle, identity, reviewer
):
    _, path, floor, layer, h = prepared(client, db, bundle, identity, reviewer)
    old = client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()["id"]
    r = save(client, path, floor, h, fixture_payload(layer))
    assert r.status_code == 200, r.text
    room = next(k for k, r in r.json()["rooms"].items() if r["code"] == "101")
    run = client.post(
        path + "/validations", json=expectations(bundle), headers=version(h, current(client, path))
    )
    assert run.status_code == 200, run.text
    assert run.json()["report"]["errors"] == 0, run.text
    sub = client.post(
        path + "/submissions",
        json={"validation_id": run.json()["id"], "acknowledgements": ack(run.json())},
        headers=version(h, current(client, path)),
    )
    assert sub.status_code == 200, sub.text
    assert save(client, path, floor, h, fixture_payload(layer)).status_code == 409
    rh = sign_in(client, reviewer)
    r = client.post(
        path + f"/submissions/{sub.json()['id']}/decision",
        json={
            "decision": "approve",
            "notes": "Independent synthetic indoor tracing review, no field accessibility or 3C route.",
            "acknowledgements": ack(run.json()),
        },
        headers=version(rh, current(client, path)),
    )
    assert r.status_code == 200, r.text
    r = client.post(
        path + "/publish",
        json={"submission_id": sub.json()["id"], "expected_release_id": old, "key": str(uuid4())},
        headers=version(rh, current(client, path)),
    )
    assert r.status_code == 200, r.text
    release = client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()
    artifact = client.get(release["artifact_url"]).json()
    assert (
        len(artifact["indoor_rooms"]) == 2
        and len(artifact["indoor_nodes"]) == 5
        and len(artifact["indoor_edges"]) == 8
        and len(artifact["indoor_access"]) == 2
    )
    assert "PRIVATE-INDOOR-NOTE" not in json.dumps(
        artifact
    ) and "Synthetic restricted store" not in json.dumps(artifact)
    search = client.get(f"/api/v1/campuses/{bundle.campus.id}/search?q=quiet%20study").json()
    assert search["items"][0]["id"] == room and search["items"][0]["point"] is None
    assert (
        search["items"][0]["room_code"] == "101"
        and search["items"][0]["navigation_mode"] == "indoor_catalog_only"
    )
    # Existing geographic map response never receives pixels or NULL geometry.
    assert (
        client.get(
            f"/api/v1/campuses/{bundle.campus.id}/map?bbox=-0.001,-0.001,0.004,0.004"
        ).status_code
        == 200
    )
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(
            text("UPDATE indoor_rooms SET x_px=1 WHERE dataset_revision_id=:revision"),
            {"revision": release["dataset_revision_id"]},
        )
    route = client.post(
        "/api/v1/routes",
        json={
            "campus_id": str(bundle.campus.id),
            "source": {
                "kind": "place",
                "place_id": str(next(p.id for p in bundle.places if p.code == "GATE")),
            },
            "destination": {"kind": "place", "place_id": room},
            "profile": "shortest",
        },
    )
    assert route.status_code == 422 and route.json()["error"]["code"] == "location_not_routable", (
        route.text
    )
    h = sign_in(client, identity)
    clone = make_draft(client, bundle, h)
    nextpath = path.rsplit("/", 1)[0] + "/" + clone["id"]
    copied = client.get(nextpath + f"/floors/{floor}/indoor").json()
    assert copied["rooms"] == json.loads(FIXTURE.read_text())["records"]["rooms"]
    rh = sign_in(client, reviewer)
    r = client.post(
        f"/api/v1/admin/campuses/{bundle.campus.id}/rollback",
        json={
            "target_release_id": old,
            "expected_release_id": release["id"],
            "key": str(uuid4()),
            "reason": "Synthetic rollback retaining immutable indoor history.",
        },
        headers=rh,
    )
    assert r.status_code == 200, r.text
    assert client.get(release["artifact_url"]).json() == artifact
    assert not client.get(f"/api/v1/campuses/{bundle.campus.id}/search?q=quiet%20study").json()[
        "items"
    ]


def test_preview_is_nonmutating_typed_and_stale_guarded(client, db, bundle, identity, reviewer):
    _, path, floor, layer, h = prepared(client, db, bundle, identity, reviewer)
    v = current(client, path)
    r = client.post(
        path + f"/floors/{floor}/indoor/preview", json=fixture_payload(layer), headers=version(h, v)
    )
    assert r.status_code == 200 and len(r.json()["rooms"]) == 3
    assert current(client, path) == v
    assert not db.scalar(select(func.count()).select_from(Room))
    assert not db.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "indoor.patch")
    )
    assert (
        client.post(
            path + f"/floors/{floor}/indoor/preview",
            json=fixture_payload(layer),
            headers=version(h, v - 1),
        ).status_code
        == 409
    )


def test_graph_validation_reports_crossings_directed_unlinked_unknown_access(
    client, db, bundle, identity, reviewer
):
    _, path, floor, layer, h = prepared(client, db, bundle, identity, reviewer)
    payload = fixture_payload(layer)
    # Remove reverse door direction only: one-way is valid but room door loses return reachability.
    edges = [c for c in payload["changes"] if c["entity"] == "edges"]
    reverse = next(
        c for c in edges if c["data"]["polyline"] == [[180, 120], [180, 100], [100, 100]]
    )
    payload["changes"].remove(reverse)
    # A distinct shaped line crosses the corridor without sharing a topology node.
    a, b = uuid4(), uuid4()
    for id, x, y in [(a, 200, 50), (b, 200, 150)]:
        payload["changes"].append(
            {
                "entity": "nodes",
                "id": str(id),
                "data": {
                    "kind": "junction",
                    "label": "Synthetic isolated crossing",
                    "x_px": x,
                    "y_px": y,
                },
            }
        )
    payload["changes"].append(
        {
            "entity": "edges",
            "id": str(uuid4()),
            "data": {
                "physical_path_id": str(uuid4()),
                "from_node_id": str(a),
                "to_node_id": str(b),
                "polyline": [[200, 50], [200, 150]],
            },
        }
    )
    r = save(client, path, floor, h, payload)
    assert r.status_code == 200, r.text
    val = client.get(path + f"/floors/{floor}/indoor/validation").json()
    codes = {d["code"] for d in val["diagnostics"]}
    assert val["errors"] == 0
    assert {
        "indoor_unmapped_intersection",
        "indoor_door_unreachable",
        "indoor_step_free_unknown",
        "indoor_components",
    } <= codes


def test_replacement_and_foreign_floor_identity_guards(client, db, bundle, identity, reviewer):
    from tests.integration.test_floorplans import floor_payload

    _, path, floor, layer, h = prepared(client, db, bundle, identity, reviewer)
    r = save(client, path, floor, h, fixture_payload(layer))
    assert r.status_code == 200, r.text
    old = r.json()
    v = current(client, path)
    job = ready(client, db, path, h, floor, "synthetic-two-pages.pdf", 2)
    assert apply(client, path, h, job, replace=layer, reset=True).status_code == 409
    assert current(client, path) == v
    other = client.post(path + "/floors", json=floor_payload(bundle, "B1"), headers=version(h, v))
    assert other.status_code == 201
    otherid = other.json()["id"]
    job = ready(client, db, path, h, otherid)
    r = apply(client, path, h, job)
    assert r.status_code == 200
    layer2 = r.json()["layer_id"]
    floor2 = next(f for f in client.get(path + "/floors").json()["floors"] if f["id"] == otherid)
    rh = sign_in(client, reviewer)
    assert (
        client.post(
            path + f"/sources/{floor2['layer']['source_id']}/approve",
            headers=version(rh, current(client, path)),
        ).status_code
        == 200
    )
    h = sign_in(client, identity)
    r = save(client, path, otherid, h, fixture_payload(layer2, "directions_only"))
    assert r.status_code == 409
    # Same identity cannot be implicitly moved even when frame coordinates happen to match.
    assert client.get(path + f"/floors/{floor}/indoor").json()["nodes"] == old["nodes"]
    assert client.get(path + f"/floors/{otherid}/indoor").json()["rooms"] == {}


def test_stored_frame_source_mismatch_is_actionable_and_department_links_are_canonical(
    client, db, bundle, identity, reviewer
):
    from app.models.admin import DepartmentPlace
    from tests.integration.test_admin import catalog_path

    draft, path, floor, layer, h = prepared(client, db, bundle, identity, reviewer)
    department = client.post(
        catalog_path(bundle, draft, "departments"),
        json={
            "entity": "departments",
            "data": {
                "code": "INDOOR",
                "name": "Synthetic indoor support",
                "description": "Public test department",
                "place_ids": [],
            },
        },
        headers=version(h, current(client, path)),
    )
    assert department.status_code == 201, department.text
    payload = fixture_payload(layer)
    room = next(
        c for c in payload["changes"] if c["entity"] == "rooms" and c["data"]["code"] == "101"
    )
    room["data"]["department_ids"] = [department.json()["id"]]
    r = save(client, path, floor, h, payload)
    assert r.status_code == 200, r.text
    assert db.scalar(
        select(DepartmentPlace).where(
            DepartmentPlace.dataset_revision_id == UUID(draft["id"]),
            DepartmentPlace.place_id == UUID(room["id"]),
        )
    ).department_id == UUID(department.json()["id"])
    with db.begin_nested():
        db.execute(text("SET LOCAL session_replication_role=replica"))
        db.execute(
            text("UPDATE indoor_nodes SET frame_id=:bad WHERE dataset_revision_id=:revision"),
            {"bad": str(bundle.frames[0].id), "revision": draft["id"]},
        )
        db.execute(text("SET LOCAL session_replication_role=origin"))
        db.expire_all()
        val = client.get(path + f"/floors/{floor}/indoor/validation").json()
        assert val["errors"] > 0
        assert any(
            d["code"] == "indoor_frame_source" and d["entity"] == "nodes"
            for d in val["diagnostics"]
        )


def test_dense_pair_validation_budget_blocks_incomplete_apply_atomically(
    client, db, bundle, identity, reviewer
):
    _, path, floor, layer, h = prepared(client, db, bundle, identity, reviewer)
    changes = []
    # 50 disjoint parallel polylines with overlapping envelopes: 1,225 potential
    # pairs, but no crossings that could otherwise stop at the warning cap.
    for i in range(50):
        a, b = uuid4(), uuid4()
        for id, x, y in [(a, 100, 100 + i), (b, 400, 200 + i)]:
            changes.append(
                {
                    "entity": "nodes",
                    "id": str(id),
                    "data": {
                        "kind": "corridor",
                        "label": f"Synthetic parallel {i}",
                        "x_px": x,
                        "y_px": y,
                    },
                }
            )
        changes.append(
            {
                "entity": "edges",
                "id": str(uuid4()),
                "data": {
                    "physical_path_id": str(uuid4()),
                    "from_node_id": str(a),
                    "to_node_id": str(b),
                    "polyline": [[100, 100 + i], [400, 200 + i]],
                },
            }
        )
    v = current(client, path)
    r = save(client, path, floor, h, {"layer_id": layer, "changes": changes})
    assert r.status_code == 422 and "indoor_spatial_budget" in r.text, r.text
    assert current(client, path) == v
    assert db.scalar(select(func.count()).select_from(IndoorNode)) == 0
    assert db.scalar(select(func.count()).select_from(IndoorEdge)) == 0
