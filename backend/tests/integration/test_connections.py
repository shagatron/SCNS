"""Two calibrated floors and explicit synthetic transitions on disposable PostGIS."""

import json
from copy import deepcopy
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.core.errors import DomainError
from app.models import Revision
from app.models.admin import AuditEvent
from app.models.connections import Connector, FloorRouting
from app.routing.mixed import compute
from app.services.publication import public_projection, snapshot
from tests.integration.test_admin import sign_in, version
from tests.integration.test_floorplans import apply, current, floor_payload, ready
from tests.integration.test_indoor import identity as identity_fixture
from tests.integration.test_indoor import prepared, save
from tests.integration.test_indoor import reviewer as reviewer_fixture
from tests.unit.test_floorplan_contract import measure

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[3] / "data/demo/indoor-routing"
EXPECTED = json.loads((ROOT / "expected.json").read_text())


@pytest.fixture
def identity(db, bundle, seeded):
    return identity_fixture.__wrapped__(db, bundle, seeded)


@pytest.fixture
def reviewer(db, bundle):
    return reviewer_fixture.__wrapped__(db, bundle)


def write(client, path, h, changes, v=None):
    return client.patch(
        path + "/connections",
        json={"changes": changes},
        headers=version(h, current(client, path) if v is None else v),
    )


def setup_two(client, db, bundle, identity, reviewer):
    draft, path, ground, layer, h = prepared(client, db, bundle, identity, reviewer)
    payload = floor_payload(bundle, "F1")
    payload.update(label="Synthetic first floor", ordering=1)
    r = client.post(path + "/floors", json=payload, headers=version(h, current(client, path)))
    assert r.status_code == 201, r.text
    upper = r.json()["id"]
    job = ready(client, db, path, h, upper)
    r = apply(client, path, h, job)
    assert r.status_code == 200, r.text
    upper_layer = r.json()["layer_id"]
    r = client.post(
        path + f"/floors/{upper}/calibration",
        json=measure(),
        headers=version(h, current(client, path)),
    )
    assert r.status_code == 200, r.text
    rh = sign_in(client, reviewer)
    f = next(f for f in client.get(path + "/floors").json()["floors"] if f["id"] == upper)
    r = client.post(
        path + f"/sources/{f['layer']['source_id']}/approve",
        headers=version(rh, current(client, path)),
    )
    assert r.status_code == 200, r.text
    r = client.post(
        path + f"/floors/{upper}/calibration/approve", headers=version(rh, current(client, path))
    )
    assert r.status_code == 200, r.text
    h = sign_in(client, identity)
    for floor, plan, name in ((ground, layer, "ground.json"), (upper, upper_layer, "upper.json")):
        records = json.loads((ROOT / name).read_text())["records"]
        r = save(
            client,
            path,
            floor,
            h,
            {
                "layer_id": plan,
                "mode": "metric",
                "changes": [
                    {"entity": e, "id": i, "data": row}
                    for e, rows in records.items()
                    for i, row in rows.items()
                ],
            },
        )
        assert r.status_code == 200, r.text
    graph = client.get(path + "/graph").json()
    building = str(bundle.buildings[0].id)
    entrance = next(i for i, p in graph["places"].items() if p["building_id"] == building)
    anchor = next(i for i, a in graph["anchors"].items() if a["place_id"] == entrance)
    other = next(
        i
        for i, n in graph["nodes"].items()
        if n["label"] == "Central" and n["visibility"] == "public"
    )
    secondary = str(uuid4())
    r = client.post(
        path + "/graph",
        json={
            "changes": [
                {
                    "entity": "anchors",
                    "id": secondary,
                    "data": {
                        "place_id": entrance,
                        "node_id": other,
                        "accessibility_status": "verified_step_free",
                        "is_open": True,
                        "accessibility_evidence": "Synthetic alternative entrance 2026-10-01, invented test only",
                    },
                }
            ]
        },
        headers=version(h, current(client, path)),
    )
    assert r.status_code == 200, r.text
    encoded = (ROOT / "connections.json").read_text()
    for key, value in {
        "GROUND_LAYER": layer,
        "UPPER_LAYER": upper_layer,
        "GROUND": ground,
        "UPPER": upper,
        "BUILDING": building,
        "ENTRANCE_A": anchor,
        "ENTRANCE_B": secondary,
    }.items():
        encoded = encoded.replace("$" + key, value)
    records = json.loads(encoded)["records"]
    changes = [
        {"entity": e, "id": i, "data": row}
        for e, rows in records.items()
        for i, row in rows.items()
    ]
    return draft, path, ground, upper, h, changes


def project(db, draft):
    return public_projection(snapshot(db, db.get(Revision, UUID(draft["id"]))))


def test_two_floor_routes_costs_and_public_draft_isolation(
    client, db, bundle, identity, reviewer, seeded
):
    draft, path, ground, upper, h, changes = setup_two(client, db, bundle, identity, reviewer)
    before = current(client, path)
    preview = client.post(
        path + "/connections/preview", json={"changes": changes}, headers=version(h, before)
    )
    assert preview.status_code == 200, preview.text
    assert current(client, path) == before
    r = write(client, path, h, changes)
    assert r.status_code == 200, r.text
    assert r.json()["revision_version"] == before + 1
    assert write(client, path, h, changes, before).status_code == 409
    projected = project(db, draft)
    a, b, u = EXPECTED["ground_101"], EXPECTED["ground_102"], EXPECTED["upper_201"]
    for source, target in ((a, b), (b, a)):
        route = compute(projected, source, target)
        assert route["distance_m"] == 18
        assert all(s["kind"] == "indoor" and s["floor_id"] == ground for s in route["segments"])
    for source, target in ((a, u), (u, a)):
        route = compute(projected, source, target)
        assert route["distance_m"] == 36
        assert any(
            s["kind"] == "stairs" and s["geometry"] is None and s["polyline"] is None
            for s in route["segments"]
        )
        accessible = compute(projected, source, target, "step_free")
        assert accessible["distance_m"] == 57
        assert any(s["kind"] == "lift" for s in accessible["segments"])
        assert not any(s["kind"] == "stairs" for s in accessible["segments"])
        assert accessible["estimated_duration_s"] is not None
    gate = str(next(p.id for p in bundle.places if p.code == "GATE"))
    for start, end in ((gate, u), (u, gate)):
        route = compute(projected, start, end, "step_free")
        assert any(s["kind"] == "outdoor" for s in route["segments"])
        assert any(s["kind"] == "entrance_transition" for s in route["segments"])
        assert any(s["kind"] == "lift" for s in route["segments"])
    with pytest.raises(DomainError, match="No eligible route"):
        compute(projected, a, EXPECTED["isolated"])
    assert "PRIVATE-CONNECTION-NOTE" not in json.dumps(projected)
    assert all("R" not in r["code"] for r in projected["indoor_rooms"].values())
    release = client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()
    assert release["id"] == str(seeded.id)
    assert client.get(f"/api/v1/campuses/{bundle.campus.id}/floors").json()["floors"] == []
    audit = db.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "connections.patch", AuditEvent.revision_id == UUID(draft["id"])
        )
    )
    assert audit.actor_id == identity[0].id and audit.after["changes"]


def test_unavailable_unknown_direction_and_eta(client, db, bundle, identity, reviewer):
    draft, path, ground, upper, h, changes = setup_two(client, db, bundle, identity, reviewer)
    r = write(client, path, h, changes)
    assert r.status_code == 200, r.text
    p = project(db, draft)
    a, u = EXPECTED["ground_101"], EXPECTED["upper_201"]
    original = deepcopy(p)
    p["connectors"][EXPECTED["lift"]]["operational_status"] = "unavailable"
    with pytest.raises(DomainError) as e:
        compute(p, a, u, "step_free")
    assert e.value.code == "no_verified_step_free_route"
    assert compute(p, a, u)["distance_m"] == 36
    p = deepcopy(original)
    for row in p["connector_paths"].values():
        if row["connector_id"] == EXPECTED["lift"]:
            row["accessibility_status"] = "unknown"
    with pytest.raises(DomainError):
        compute(p, a, u, "step_free")
    p = deepcopy(original)
    for row in p["connector_paths"].values():
        row["distance_m"] = None
        row["distance_status"] = "unknown"
        row["baseline_traversal_s"] = None
        row["wait_estimate_s"] = None
    with pytest.raises(DomainError):
        compute(p, a, u)
    route = compute(p, a, u, mode="directions_only")
    assert route["distance_m"] is None and route["estimated_duration_s"] is None
    assert route["known_distance_m"] > 0 and route["cost_units"] == "traversals"
    with pytest.raises(DomainError):
        compute(p, a, u, "fastest")
    p = deepcopy(original)
    p["connector_paths"] = {
        i: e
        for i, e in p["connector_paths"].items()
        if p["connector_stops"][e["from_stop_id"]]["floor_id"] == ground
    }
    assert compute(p, a, u)["distance_m"] == 36
    with pytest.raises(DomainError):
        compute(p, u, a)


@pytest.mark.parametrize(
    "problem",
    [
        "missing_stop",
        "same_floor",
        "public_restricted",
        "false_step_free",
        "pair",
        "future",
        "missing_anchor",
        "foreign_building",
        "negative",
        "unknown_status",
    ],
)
def test_invalid_connection_batch_is_atomic(client, db, bundle, identity, reviewer, problem):
    draft, path, ground, upper, h, changes = setup_two(client, db, bundle, identity, reviewer)
    before = current(client, path)
    edge = next(c["data"] for c in changes if c["entity"] == "paths")
    if problem == "missing_stop":
        edge["to_stop_id"] = str(uuid4())
    elif problem == "same_floor":
        edge["to_stop_id"] = edge["from_stop_id"]
    elif problem == "public_restricted":
        next(c["data"] for c in changes if c["entity"] == "connectors")["visibility"] = "restricted"
    elif problem == "false_step_free":
        edge["accessibility_status"] = "verified_step_free"
    elif problem == "pair":
        edge["distance_m"] = 7
    elif problem == "future":
        edge["verified_on"] = "2099-01-01"
    elif problem == "missing_anchor":
        next(c["data"] for c in changes if c["entity"] == "transitions")["anchor_id"] = str(uuid4())
    elif problem == "foreign_building":
        next(c["data"] for c in changes if c["entity"] == "connectors")["building_id"] = str(
            uuid4()
        )
    elif problem == "negative":
        edge["baseline_traversal_s"] = -1
    elif problem == "unknown_status":
        edge["distance_status"] = "unknown"
    r = write(client, path, h, changes)
    assert r.status_code == 422, r.text
    assert current(client, path) == before
    assert (
        db.scalar(
            select(func.count())
            .select_from(Connector)
            .where(Connector.dataset_revision_id == UUID(draft["id"]))
        )
        == 0
    )
    assert (
        db.scalar(
            select(func.count())
            .select_from(FloorRouting)
            .where(FloorRouting.dataset_revision_id == UUID(draft["id"]))
        )
        == 0
    )


@pytest.mark.parametrize("role", ["editor", "reviewer_publisher", "operations", "system_admin"])
def test_connection_permissions_csrf_campus_and_readonly(
    client, db, bundle, identity, reviewer, role
):
    from sqlalchemy import delete

    from app.models.admin import RoleAssignment

    draft, path, ground, upper, h, changes = setup_two(client, db, bundle, identity, reviewer)
    checked_version = current(client, path)
    db.execute(delete(RoleAssignment).where(RoleAssignment.user_id == identity[0].id))
    db.add(RoleAssignment(user_id=identity[0].id, campus_id=bundle.campus.id, role=role))
    db.flush()
    assert client.get(path + "/connections").status_code == (403 if role == "operations" else 200)
    assert (
        client.get(path.replace(str(bundle.campus.id), str(uuid4())) + "/connections").status_code
        == 403
    )
    assert (
        client.patch(
            path + "/connections",
            json={"changes": changes},
            headers={"Origin": h["Origin"], "If-Match": f'"{checked_version}"'},
        ).status_code
        == 403
    )
    if role == "operations":
        assert (
            client.patch(
                path + "/connections", json={"changes": changes}, headers={**h, "If-Match": '"1"'}
            ).status_code
            == 403
        )
    else:
        result = write(client, path, h, changes)
        assert result.status_code == (200 if role in {"editor", "system_admin"} else 403), (
            result.text
        )


def test_dependencies_and_late_failure_rollback(
    client, db, bundle, identity, reviewer, monkeypatch
):
    from app.services import connections

    draft, path, ground, upper, h, changes = setup_two(client, db, bundle, identity, reviewer)
    before = current(client, path)
    real = connections.audit

    def fail(*args, **kwargs):
        raise DomainError("test_injected", "Injected audit failure", 503)

    monkeypatch.setattr(connections, "audit", fail)
    result = write(client, path, h, changes)
    assert result.status_code == 503
    assert current(client, path) == before
    assert (
        db.scalar(
            select(func.count())
            .select_from(Connector)
            .where(Connector.dataset_revision_id == UUID(draft["id"]))
        )
        == 0
    )
    monkeypatch.setattr(connections, "audit", real)
    assert write(client, path, h, changes).status_code == 200
    state = client.get(path + "/connections").json()
    stop_id, stop = next(iter(state["stops"].items()))
    result = write(client, path, h, [{"entity": "stops", "id": stop_id}])
    assert result.status_code == 422
    layer = state["floors"][stop["floor_id"]]["layer_id"]
    result = save(
        client,
        path,
        stop["floor_id"],
        h,
        {"layer_id": layer, "changes": [{"entity": "nodes", "id": stop["node_id"]}]},
    )
    assert result.status_code == 409 and result.json()["error"]["code"] == "routing_dependencies"
    graph = client.get(path + f"/floors/{stop['floor_id']}/indoor").json()
    moved_node = {
        **graph["nodes"][stop["node_id"]],
        "x_px": graph["nodes"][stop["node_id"]]["x_px"] + 1,
    }
    result = save(
        client,
        path,
        stop["floor_id"],
        h,
        {
            "layer_id": layer,
            "changes": [{"entity": "nodes", "id": stop["node_id"], "data": moved_node}],
        },
    )
    assert result.status_code == 409 and result.json()["error"]["code"] == "routing_dependencies"
    result = client.post(
        path + f"/floors/{ground}/calibration",
        json=measure(),
        headers=version(h, current(client, path)),
    )
    assert result.status_code == 409
    removed = [
        {"entity": "paths", "id": i}
        for i, r in state["paths"].items()
        if stop_id in (r["from_stop_id"], r["to_stop_id"])
    ]
    removed += [
        {"entity": "transitions", "id": i}
        for i, r in state["transitions"].items()
        if r["stop_id"] == stop_id
    ]
    removed += [{"entity": "stops", "id": stop_id}]
    assert write(client, path, h, removed).status_code == 200


def test_connection_release_review_public_contract_clone_frozen_and_rollback(
    client, db, bundle, identity, reviewer
):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from tests.integration.test_admin import make_draft
    from tests.integration.test_indoor import ack

    draft, path, ground, upper, h, changes = setup_two(client, db, bundle, identity, reviewer)
    old = client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()["id"]
    assert write(client, path, h, changes).status_code == 200
    a, b, u, v = (EXPECTED[k] for k in ("ground_101", "ground_102", "upper_201", "upper_202"))
    gate = str(next(p.id for p in bundle.places if p.code == "GATE"))
    pairs = [(a, b), (u, v), (a, u), (u, a), (gate, u), (u, gate)]
    routes = [
        {
            "source": start,
            "target": end,
            "profile": profile,
            "expected_found": True,
            "reason": "Invented two-floor, calibrated synthetic route acceptance; no real access assertion.",
        }
        for start, end in pairs
        for profile in ("shortest", "step_free")
    ]
    r = client.post(
        path + "/validations", json={"routes": routes}, headers=version(h, current(client, path))
    )
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["report"]["errors"] == 0, json.dumps(run["report"])
    r = client.post(
        path + "/submissions",
        json={"validation_id": run["id"], "acknowledgements": ack(run)},
        headers=version(h, current(client, path)),
    )
    assert r.status_code == 200, r.text
    sub = r.json()
    assert write(client, path, h, changes).status_code == 409
    rh = sign_in(client, reviewer)
    r = client.post(
        path + f"/submissions/{sub['id']}/decision",
        json={
            "decision": "approve",
            "notes": "Independent two-floor synthetic connector review and acceptance.",
            "acknowledgements": ack(run),
        },
        headers=version(rh, current(client, path)),
    )
    assert r.status_code == 200, r.text
    r = client.post(
        path + "/publish",
        json={"submission_id": sub["id"], "expected_release_id": old, "key": str(uuid4())},
        headers=version(rh, current(client, path)),
    )
    assert r.status_code == 200, r.text
    release = client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()
    artifact = client.get(release["artifact_url"]).json()
    assert "PRIVATE-CONNECTION-NOTE" not in json.dumps(artifact)
    assert "PRIVATE-INDOOR-NOTE" not in json.dumps(artifact)
    floors = client.get(
        f"/api/v1/campuses/{bundle.campus.id}/floors?expected_release_id={release['id']}"
    ).json()
    assert {f["id"] for f in floors["floors"]} == {ground, upper}
    images = [f["asset_url"] for f in floors["floors"]]
    assert all(client.get(url).content.startswith(b"\x89PNG") for url in images)
    for source, target in ((a, b), (a, u), (u, a), (gate, u), (u, gate)):
        for profile in ("shortest", "step_free", "fastest"):
            response = client.post(
                "/api/v1/routes",
                json={
                    "campus_id": str(bundle.campus.id),
                    "source": {"kind": "place", "place_id": source},
                    "destination": {"kind": "place", "place_id": target},
                    "profile": profile,
                    "expected_release_id": release["id"],
                },
            )
            assert response.status_code == 200, response.text
            route = response.json()
            assert route["release_id"] == release["id"]
            assert all(s["geometry"] is None for s in route["segments"] if s["kind"] != "outdoor")
            if source == a and target == u and profile == "step_free":
                assert route["distance_m"] == 57 and len(route["floors"]) == 2
                link = next(s for s in route["segments"] if s["kind"] == "lift")
                assert link["from_local_point"] and link["to_local_point"]
    details = client.get(
        f"/api/v1/campuses/{bundle.campus.id}/places/{a}?expected_release_id={release['id']}"
    )
    assert (
        details.status_code == 200
        and details.json()["routable"]
        and details.json()["point"] is None
    )
    assert (
        client.get(
            f"/api/v1/campuses/{bundle.campus.id}/places/{a}?expected_release_id={old}"
        ).status_code
        == 409
    )
    assert client.get(f"/api/v1/campuses/{uuid4()}/places/{a}").status_code == 404
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(
            text(
                "UPDATE connectors SET operational_status='unavailable' WHERE dataset_revision_id=:r"
            ),
            {"r": draft["id"]},
        )
    h = sign_in(client, identity)
    copied = make_draft(client, bundle, h)
    copied_path = path.rsplit("/", 1)[0] + "/" + copied["id"]
    assert (
        client.get(copied_path + "/connections").json()["paths"]
        == client.get(path + "/connections").json()["paths"]
    )
    rh = sign_in(client, reviewer)
    r = client.post(
        f"/api/v1/admin/campuses/{bundle.campus.id}/rollback",
        json={
            "target_release_id": old,
            "expected_release_id": release["id"],
            "key": str(uuid4()),
            "reason": "Synthetic rollback retaining immutable routing and plan artifacts.",
        },
        headers=rh,
    )
    assert r.status_code == 200, r.text
    assert client.get(f"/api/v1/campuses/{bundle.campus.id}/floors").json()["floors"] == []
    assert client.get(release["artifact_url"]).json() == artifact
    assert all(client.get(url).content.startswith(b"\x89PNG") for url in images)
