"""Live operational restrictions use real PostGIS, current grants and normal releases."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import DBAPIError

from app.core.errors import DomainError
from app.models.admin import AuditEvent, RoleAssignment
from app.models.closures import Closure, ClosureAction
from app.services import closures
from tests.integration.test_admin import identity as identity_fixture
from tests.integration.test_admin import sign_in, version
from tests.integration.test_publication import reviewer as reviewer_fixture

pytestmark = pytest.mark.integration


@pytest.fixture
def identity(db, bundle, seeded):
    return identity_fixture.__wrapped__(db, bundle, seeded)


@pytest.fixture
def reviewer(db, bundle):
    return reviewer_fixture.__wrapped__(db, bundle)


def endpoint(bundle):
    return f"/api/v1/admin/campuses/{bundle.campus.id}/closures"


def route(client, bundle, **kwargs):
    values = {
        "campus_id": str(bundle.campus.id),
        "source": {"place_id": str(next(p.id for p in bundle.places if p.code == "GATE"))},
        "destination": {"place_id": str(next(p.id for p in bundle.places if p.code == "LIB"))},
        **kwargs,
    }
    return client.post("/api/v1/routes", json=values)


def payload(client, bundle, kind="outdoor_edge", target_id=None, **kwargs):
    choice = next(
        t
        for t in client.get(endpoint(bundle)).json()["targets"]
        if t["kind"] == kind and (target_id is None or t["id"] == str(target_id))
    )
    return {
        "key": str(uuid4()),
        "target_kind": choice["kind"],
        "target_id": choice["id"],
        "reason": "Synthetic restriction, software exercise only.",
        "starts_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        **kwargs,
    }


def create(client, bundle, h, body, v=0):
    r = client.post(endpoint(bundle), json=body, headers=version(h, v))
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.parametrize("role", ["editor", "reviewer_publisher", "operations", "system_admin"])
def test_live_roles_csrf_and_campus_isolation(client, db, bundle, identity, role):
    assert client.get(endpoint(bundle)).status_code == 401
    h = sign_in(client, identity)
    data = payload(client, bundle)
    db.execute(delete(RoleAssignment).where(RoleAssignment.user_id == identity[0].id))
    db.add(RoleAssignment(user_id=identity[0].id, campus_id=bundle.campus.id, role=role))
    db.flush()
    assert client.get(endpoint(bundle)).status_code == 200
    assert (
        client.get(endpoint(bundle).replace(str(bundle.campus.id), str(uuid4()))).status_code == 403
    )
    assert (
        client.post(
            endpoint(bundle), json=data, headers=version({"Origin": h["Origin"]}, 0)
        ).status_code
        == 403
    )
    r = client.post(endpoint(bundle), json=data, headers=version(h, 0))
    assert r.status_code == (201 if role in {"operations", "system_admin"} else 403), r.text
    db.execute(delete(RoleAssignment).where(RoleAssignment.user_id == identity[0].id))
    db.flush()
    assert client.post(endpoint(bundle), json=data, headers=version(h, 0)).status_code == 403


def test_directed_and_paired_closures_route_versions_retries_and_verified_reopen(
    client, db, bundle, identity, seeded
):
    h = sign_in(client, identity)
    before = route(client, bundle).json()
    assert before["distance_m"] == 256.88 and len(before["segments"]) == 3
    edge = before["segments"][1]["edge_id"]
    body = payload(
        client,
        bundle,
        target_id=edge,
        estimated_end_at=(datetime.now(UTC) - timedelta(seconds=10)).isoformat(),
    )
    first = create(client, bundle, h, body)
    assert first["closure_overlay_version"] == 1
    assert create(client, bundle, h, body) == first
    assert (
        client.post(
            endpoint(bundle),
            json={**body, "reason": "Different retry must fail"},
            headers=version(h, 1),
        ).status_code
        == 409
    )
    stale = route(client, bundle, expected_closure_overlay_version=0)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale_closures"
    after = route(client, bundle, expected_closure_overlay_version=1)
    assert after.status_code == 200, after.text
    assert after.json()["release_id"] == str(seeded.id) and all(
        s["edge_id"] != edge for s in after.json()["segments"]
    )
    assert after.json()["distance_m"] > before["distance_m"]
    status = client.get(f"/api/v1/campuses/{bundle.campus.id}/closures")
    assert status.headers["cache-control"] == "no-store"
    assert status.json()["items"][0]["state"] == "active"  # estimated end does not expire
    decision = {
        "key": str(uuid4()),
        "evidence": "Synthetic inspected path, simulated verification only. PRIVATE-REOPEN",
        "confirmed": True,
    }
    url = endpoint(bundle) + f"/{first['id']}/reopen"
    assert client.post(url, json=decision, headers=version(h, 0)).status_code == 409
    reopened = client.post(url, json=decision, headers=version(h, 1))
    assert reopened.status_code == 200
    assert client.post(url, json=decision, headers=version(h, 1)).json() == reopened.json()
    assert route(client, bundle).json()["distance_m"] == 256.88
    assert "PRIVATE-REOPEN" not in client.get(f"/api/v1/campuses/{bundle.campus.id}/closures").text
    pair = next(e.physical_path_id for e in bundle.edges if str(e.id) == edge)
    second = create(client, bundle, h, payload(client, bundle, "outdoor_path", pair), 2)
    blocked = {str(e.id) for e in bundle.edges if e.physical_path_id == pair}
    result = route(client, bundle).json()
    assert not blocked.intersection(s["edge_id"] for s in result["segments"])
    assert second["closure_overlay_version"] == 3
    assert db.scalar(select(func.count()).select_from(Closure)) == 2
    assert {a.action for a in db.scalars(select(AuditEvent))} >= {
        "closure.create",
        "closure.reopen",
    }
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(text("DELETE FROM closures"))


def test_validation_stale_creation_and_atomic_audit_failure(
    client, db, bundle, identity, monkeypatch
):
    h = sign_in(client, identity)
    data = payload(client, bundle)
    assert client.post(endpoint(bundle), json=data, headers=h).status_code == 428
    for change in (
        {"target_id": str(uuid4())},
        {"starts_at": "2026-10-08T10:00:00"},
        {"estimated_end_at": "2000-01-01T00:00:00Z"},
        {"reason": "          "},
        {"reopening_policy": "automatic"},
    ):
        assert (
            client.post(
                endpoint(bundle), json={**data, **change}, headers=version(h, 0)
            ).status_code
            == 422
        )
    first = create(client, bundle, h, data)
    assert (
        client.post(
            endpoint(bundle), json={**data, "key": str(uuid4())}, headers=version(h, 0)
        ).status_code
        == 409
    )

    def fail(*args, **kwargs):
        raise DomainError("injected", "Injected closure audit failure", 503)

    monkeypatch.setattr(closures, "audit", fail)
    r = client.post(
        endpoint(bundle) + f"/{first['id']}/reopen",
        json={
            "key": str(uuid4()),
            "confirmed": True,
            "evidence": "Must roll back the complete reopening",
        },
        headers=version(h, 1),
    )
    assert r.status_code == 503
    assert closures.version(db, bundle.campus.id) == 1
    assert db.get(Closure, UUID(first["id"])).state == "closed"
    assert db.scalar(select(func.count()).select_from(ClosureAction)) == 1


def test_scheduled_restriction_intersects_conservative_route_window(client, bundle, identity):
    h = sign_in(client, identity)
    baseline = route(client, bundle).json()
    edge = baseline["segments"][1]["edge_id"]
    starts = datetime.now(UTC) + timedelta(hours=2)
    create(client, bundle, h, payload(client, bundle, target_id=edge, starts_at=starts.isoformat()))
    assert route(client, bundle).json()["distance_m"] == 256.88
    assert (
        route(client, bundle, departure_at=(starts - timedelta(minutes=30)).isoformat()).json()[
            "distance_m"
        ]
        > 256.88
    )
    public = client.get(f"/api/v1/campuses/{bundle.campus.id}/closures").json()
    assert public["items"][0]["state"] == "scheduled" and public["next_change_at"]


def publish_draft(client, bundle, identity, reviewer, draft, path, old):
    from tests.integration.test_connections import EXPECTED
    from tests.integration.test_floorplans import current
    from tests.integration.test_indoor import ack
    from tests.integration.test_publication import approve

    h = sign_in(client, identity)
    a, b, u, v = (EXPECTED[k] for k in ("ground_101", "ground_102", "upper_201", "upper_202"))
    gate = str(next(p.id for p in bundle.places if p.code == "GATE"))
    routes = [
        {
            "source": x,
            "target": y,
            "profile": p,
            "expected_found": True,
            "reason": "Invented two-floor acceptance only; not real navigation.",
        }
        for x, y in ((a, b), (u, v), (a, u), (u, a), (gate, u), (u, gate))
        for p in ("shortest", "step_free")
    ]
    r = client.post(
        path + "/validations", json={"routes": routes}, headers=version(h, current(client, path))
    )
    assert r.status_code == 200 and r.json()["report"]["errors"] == 0, r.text
    run = r.json()
    r = client.post(
        path + "/submissions",
        json={"validation_id": run["id"], "acknowledgements": ack(run)},
        headers=version(h, current(client, path)),
    )
    assert r.status_code == 200, r.text
    sub = r.json()
    rh, edit = approve(client, bundle, draft, run, sub, reviewer)
    r = client.post(
        path + "/publish",
        json={"submission_id": sub["id"], "expected_release_id": old, "key": str(uuid4())},
        headers=version(rh, edit),
    )
    assert r.status_code == 200, r.text
    return r.json()["release_id"]


def test_lift_outage_no_stairs_fallback_publication_rollback_and_unresolved_review(
    client, db, bundle, identity, reviewer, monkeypatch
):
    from tests.integration.test_admin import make_draft
    from tests.integration.test_connections import EXPECTED, setup_two, write

    original = client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()["id"]
    draft, path, _, _, h, changes = setup_two(client, db, bundle, identity, reviewer)
    assert write(client, path, h, changes).status_code == 200
    published = publish_draft(client, bundle, identity, reviewer, draft, path, original)
    source = {"place_id": EXPECTED["ground_101"]}
    destination = {"place_id": EXPECTED["upper_201"]}
    assert (
        route(client, bundle, source=source, destination=destination, profile="step_free").json()[
            "distance_m"
        ]
        == 57
    )
    h = sign_in(client, identity)
    lift = next(
        t
        for t in client.get(endpoint(bundle)).json()["targets"]
        if t["kind"] == "connector" and t["label"].startswith("lift ·")
    )
    closed = create(client, bundle, h, payload(client, bundle, "connector", lift["id"]))
    blocked = route(client, bundle, source=source, destination=destination, profile="step_free")
    assert (
        blocked.status_code == 422
        and blocked.json()["error"]["code"] == "no_verified_step_free_route"
    )
    assert route(client, bundle, source=source, destination=destination).json()["distance_m"] == 36
    assert (
        route(
            client, bundle, source=source, destination={"place_id": EXPECTED["ground_102"]}
        ).json()["distance_m"]
        == 18
    )
    # Draft validation still assesses the immutable map, independently of live outages.
    cloned = make_draft(client, bundle, h)
    clone_path = f"/api/v1/admin/campuses/{bundle.campus.id}/drafts/{cloned['id']}"
    next_release = publish_draft(client, bundle, identity, reviewer, cloned, clone_path, published)
    assert closures.version(db, bundle.campus.id) == 1
    assert db.get(Closure, UUID(closed["id"])).state == "closed"
    rh = sign_in(client, reviewer)
    url = f"/api/v1/admin/campuses/{bundle.campus.id}/rollback"
    r = client.post(
        url,
        json={
            "target_release_id": published,
            "expected_release_id": next_release,
            "key": str(uuid4()),
            "reason": "Earlier indoor release must preserve live lift outage.",
        },
        headers=rh,
    )
    assert r.status_code == 200 and r.json()["closure_overlay_version"] == 1, r.text
    assert (
        route(client, bundle, source=source, destination=destination, profile="step_free").json()[
            "error"
        ]["code"]
        == "no_verified_step_free_route"
    )
    removal = {
        "target_release_id": original,
        "expected_release_id": published,
        "key": str(uuid4()),
        "reason": "Outdoor historical rollback must retain missing lift restriction.",
    }
    original_audit = closures.audit

    def fail(*args, **kwargs):
        raise DomainError("injected", "Rollback reconciliation audit fails", 503)

    monkeypatch.setattr(closures, "audit", fail)
    assert client.post(url, json=removal, headers=rh).status_code == 503
    assert client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()["id"] == published
    assert closures.version(db, bundle.campus.id) == 1
    assert db.get(Closure, UUID(closed["id"])).state == "closed"
    monkeypatch.setattr(closures, "audit", original_audit)
    r = client.post(url, json=removal, headers=rh)
    assert r.status_code == 200 and r.json()["closure_overlay_version"] == 2, r.text
    public = client.get(f"/api/v1/campuses/{bundle.campus.id}/closures").json()
    assert public["unresolved_count"] == 1 and public["items"][0]["target_id"] is None
    assert route(client, bundle).json()["error"]["code"] == "closure_unresolved"
    h = sign_in(client, identity)
    current_target = next(
        t for t in client.get(endpoint(bundle)).json()["targets"] if t["kind"] == "outdoor_path"
    )
    rebind = {
        "key": str(uuid4()),
        "target_kind": current_target["kind"],
        "target_id": current_target["id"],
        "confirmed": True,
        "evidence": "Synthetic operator explicitly reconciles physical restriction; no real field claim.",
    }
    r = client.post(
        endpoint(bundle) + f"/{closed['id']}/rebind", json=rebind, headers=version(h, 2)
    )
    assert r.status_code == 200 and r.json()["state"] == "closed", r.text
    assert (
        client.get(f"/api/v1/campuses/{bundle.campus.id}/closures").json()["unresolved_count"] == 0
    )
    assert db.get(Closure, UUID(closed["id"])).state == "closed"


def test_overlapping_incidents_reopening_one_never_reopens_other(client, bundle, identity):
    h = sign_in(client, identity)
    base = route(client, bundle).json()
    edge = base["segments"][1]["edge_id"]
    first = create(client, bundle, h, payload(client, bundle, target_id=edge))
    second = create(client, bundle, h, payload(client, bundle, target_id=edge), 1)
    decision = {
        "key": str(uuid4()),
        "confirmed": True,
        "evidence": "Only first incident resolved in synthetic software test.",
    }
    r = client.post(
        endpoint(bundle) + f"/{first['id']}/reopen", json=decision, headers=version(h, 2)
    )
    assert r.status_code == 200
    result = route(client, bundle).json()
    assert result["closure_overlay_version"] == 3 and all(
        s["edge_id"] != edge for s in result["segments"]
    )
    public = client.get(f"/api/v1/campuses/{bundle.campus.id}/closures").json()
    assert len(public["items"]) == 1 and public["items"][0]["id"] == second["id"]


def test_two_granted_campuses_cannot_mix_incident_or_target_identifiers(
    client, db, bundle, seeded, identity
):
    from tests.publication_fixtures import create_fixture

    foreign = create_fixture(db, seeded.dataset_revision_id, bundle, "foreign", "closure isolation")
    db.add(RoleAssignment(user_id=identity[0].id, campus_id=foreign, role="system_admin"))
    db.flush()
    h = sign_in(client, identity)
    own_data = payload(client, bundle)
    own = create(client, bundle, h, own_data)
    foreign_url = endpoint(bundle).replace(str(bundle.campus.id), str(foreign))
    foreign_target = client.get(foreign_url).json()["targets"][0]
    wrong = {
        **own_data,
        "key": str(uuid4()),
        "target_kind": foreign_target["kind"],
        "target_id": foreign_target["id"],
    }
    assert client.post(endpoint(bundle), json=wrong, headers=version(h, 1)).status_code == 422
    decision = {
        "key": str(uuid4()),
        "confirmed": True,
        "evidence": "Must not resolve a restriction from another campus.",
    }
    assert (
        client.post(
            foreign_url + f"/{own['id']}/reopen", json=decision, headers=version(h, 0)
        ).status_code
        == 404
    )
    assert closures.version(db, foreign) == 0 and closures.version(db, bundle.campus.id) == 1


def test_changed_physical_target_stays_unresolved_until_explicit_rebind(
    client, db, bundle, seeded, identity
):
    from copy import deepcopy

    from app.services.catalog import active_release
    from app.services.mixed_routes import release_projection

    h = sign_in(client, identity)
    data = payload(client, bundle)
    entry = create(client, bundle, h, data)
    release = active_release(db, bundle.campus.id)
    projection = release_projection(db, release)
    changed = deepcopy(projection)
    changed["edges"][data["target_id"]]["geometry"]["coordinates"][0][0] += 0.00001
    assert closures.reconcile(db, release, changed, identity[0], "synthetic-physical-change") == 2
    assert closures.public_status(db, bundle.campus.id, release, changed)["unresolved_count"] == 1
    assert closures.reconcile(db, release, projection, identity[0], "synthetic-restore") == 2
    assert (
        closures.public_status(db, bundle.campus.id, release, projection)["unresolved_count"] == 1
    )
    assert route(client, bundle).status_code == 503
    rebound = client.post(
        endpoint(bundle) + f"/{entry['id']}/rebind",
        json={
            "key": str(uuid4()),
            "target_kind": data["target_kind"],
            "target_id": data["target_id"],
            "confirmed": True,
            "evidence": "Synthetic explicit physical-target reconciliation, keep closed.",
        },
        headers=version(h, 2),
    )
    assert rebound.status_code == 200 and rebound.json()["closure_overlay_version"] == 3
    assert db.get(Closure, UUID(entry["id"])).state == "closed"
