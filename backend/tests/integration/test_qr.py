"""Operational QR permissions, transactional lifecycle and published routing isolation."""

from copy import deepcopy
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import DBAPIError

from app.core.errors import DomainError
from app.models.admin import AuditEvent, RoleAssignment
from app.models.qr import QRMarker
from app.services import qr
from app.services.mixed_routes import release_projection
from tests.integration.test_admin import identity as owner_identity
from tests.integration.test_admin import sign_in, version
from tests.integration.test_publication import reviewer as reviewer_identity


@pytest.fixture
def identity(db, bundle, seeded):
    return owner_identity.__wrapped__(db, bundle, seeded)


@pytest.fixture
def reviewer(db, bundle):
    return reviewer_identity.__wrapped__(db, bundle)


pytestmark = pytest.mark.integration


def endpoint(bundle):
    return f"/api/v1/admin/campuses/{bundle.campus.id}/qr-markers"


def payload(client, bundle):
    targets = client.get(endpoint(bundle)).json()["targets"]
    node = next(t for t in targets if t["label"] == "Gate")
    return {
        "key": str(uuid4()),
        "label": "Synthetic Main Gate sign",
        "node_kind": node["kind"],
        "node_id": node["id"],
        "intended_position": "Simulated sign at invented Main Gate node. PRIVATE-INTENDED",
    }


def installation():
    return {
        "installer": "Synthetic test operator",
        "actual_position": "Simulated sign position; not a physical installation. PRIVATE-ACTUAL",
        "installed_on": date.today().isoformat(),
        "verified_on": date.today().isoformat(),
        "evidence": "Invented synthetic evidence only. PRIVATE-INSTALLATION",
    }


def create(client, bundle, identity, *, active=True):
    headers = sign_in(client, identity)
    data = payload(client, bundle)
    result = client.post(endpoint(bundle), json=data, headers=headers)
    assert result.status_code == 201, result.text
    marker = result.json()
    if active:
        result = client.post(
            endpoint(bundle) + f"/{marker['id']}/activate",
            json=installation(),
            headers=version(headers, marker["version"]),
        )
        assert result.status_code == 200, result.text
        marker = result.json()
    return headers, data, marker


def route(client, bundle, marker, **source_changes):
    lib = next(p.id for p in bundle.places if p.code == "LIB")
    return client.post(
        "/api/v1/routes",
        json={
            "campus_id": str(bundle.campus.id),
            "source": {
                "kind": "qr",
                "marker_id": marker["id"],
                "expected_marker_version": marker["version"],
                "confirmed": True,
                **source_changes,
            },
            "destination": {"kind": "place", "place_id": str(lib)},
        },
    )


def test_lifecycle_route_revocation_reassignment_and_private_redaction(
    client, db, bundle, identity, seeded
):
    h, data, marker = create(client, bundle, identity, active=False)
    assert route(client, bundle, marker).status_code == 410
    assert client.get(f"/api/v1/qr/{marker['id']}").json()["label"] is None
    activated = client.post(
        endpoint(bundle) + f"/{marker['id']}/activate", json=installation(), headers=version(h, 1)
    ).json()
    response = client.get(f"/api/v1/qr/{marker['id']}")
    assert response.headers["cache-control"] == "no-store"
    assert "PRIVATE-" not in response.text
    assert response.json()["node_id"] == data["node_id"]
    assert route(client, bundle, activated).status_code == 200
    result = route(client, bundle, activated).json()
    assert result["distance_m"] == 256.88 and len(result["segments"]) == 3
    assert result["source_place_id"] is None and result["source_anchor_id"] is None
    assert (
        result["source_node_id"] == data["node_id"] and result["source_marker_id"] == marker["id"]
    )
    assert result["release_id"] == str(seeded.id)
    assert route(client, bundle, marker).status_code == 409
    assert route(client, bundle, activated, confirmed=False).status_code == 422
    for format in ("svg", "png", "pdf"):
        response = client.get(endpoint(bundle) + f"/{marker['id']}/sign.{format}")
        assert response.status_code == 200 and len(response.content) > 1000
        assert response.headers["cache-control"] == "no-store"
    revoked = client.post(
        endpoint(bundle) + f"/{marker['id']}/revoke",
        json={"reason": "Synthetic sign intentionally removed."},
        headers=version(h, 2),
    ).json()
    assert route(client, bundle, revoked).status_code == 410
    assert client.get(f"/api/v1/qr/{marker['id']}").json()["node_id"] is None
    assert (
        client.post(
            endpoint(bundle) + f"/{marker['id']}/activate",
            json=installation(),
            headers=version(h, 3),
        ).status_code
        == 409
    )
    changed = client.put(
        endpoint(bundle) + f"/{marker['id']}",
        json={k: v for k, v in data.items() if k != "key"},
        headers=version(h, 3),
    ).json()
    assert (
        changed["id"] == marker["id"]
        and changed["state"] == "planned"
        and changed["installation"] == {}
    )
    assert db.scalar(select(func.count()).select_from(QRMarker)) == 1
    assert {e.action for e in db.scalars(select(AuditEvent))} >= {
        "qr.create",
        "qr.activate",
        "qr.revoke",
        "qr.reassign",
    }
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(text("DELETE FROM qr_markers"))


@pytest.mark.parametrize("role", ["editor", "reviewer_publisher", "operations", "system_admin"])
def test_live_permissions_csrf_and_campus_isolation(client, db, bundle, identity, role):
    h, data, marker = create(client, bundle, identity, active=False)
    db.execute(delete(RoleAssignment).where(RoleAssignment.user_id == identity[0].id))
    db.add(RoleAssignment(user_id=identity[0].id, campus_id=bundle.campus.id, role=role))
    db.flush()
    assert client.get(endpoint(bundle)).status_code == 200
    foreign = endpoint(bundle).replace(str(bundle.campus.id), str(uuid4()))
    assert client.get(foreign).status_code == 403
    assert (
        client.post(
            endpoint(bundle), json={**data, "key": str(uuid4())}, headers={"Origin": h["Origin"]}
        ).status_code
        == 403
    )
    response = client.post(endpoint(bundle), json={**data, "key": str(uuid4())}, headers=h)
    assert response.status_code == (201 if role in {"operations", "system_admin"} else 403)
    db.execute(delete(RoleAssignment).where(RoleAssignment.user_id == identity[0].id))
    db.flush()
    assert client.get(endpoint(bundle)).status_code == 403


def test_creation_retries_stale_versions_invalid_inputs_and_late_failure_rollback(
    client, db, bundle, identity, monkeypatch
):
    h, data, marker = create(client, bundle, identity, active=False)
    assert client.post(endpoint(bundle), json=data, headers=h).json()["id"] == marker["id"]
    assert (
        client.post(
            endpoint(bundle), json={**data, "label": "Different label"}, headers=h
        ).status_code
        == 409
    )
    assert (
        client.post(
            endpoint(bundle), json={**data, "key": str(uuid4()), "node_id": str(uuid4())}, headers=h
        ).status_code
        == 422
    )
    url = endpoint(bundle) + f"/{marker['id']}"
    update = {k: v for k, v in data.items() if k != "key"}
    assert client.put(url, json=update, headers=h).status_code == 428
    changed = client.put(
        url, json={**update, "label": "New synthetic label"}, headers=version(h, 1)
    ).json()
    assert changed["version"] == 2
    assert client.put(url, json=update, headers=version(h, 1)).status_code == 409
    count = db.scalar(select(func.count()).select_from(AuditEvent))

    def fail(*args, **kwargs):
        raise DomainError("test_injected", "Injected audit failure", 503)

    monkeypatch.setattr(qr, "audit", fail)
    assert (
        client.put(
            url, json={**update, "label": "Must roll back"}, headers=version(h, 2)
        ).status_code
        == 503
    )
    latest = client.get(endpoint(bundle)).json()["items"][0]
    assert latest["label"] == "New synthetic label" and latest["version"] == 2
    assert db.scalar(select(func.count()).select_from(AuditEvent)) == count


def test_release_revalidation_never_resurrects_retired_revoked_or_moved_signs(
    client, db, bundle, identity, seeded
):
    h, data, marker = create(client, bundle, identity)
    projected = deepcopy(release_projection(db, seeded))
    node = projected["nodes"][data["node_id"]]
    node["point"]["coordinates"][0] += 0.001
    qr.reconcile(db, seeded, projected, identity[0], "moved-test")
    obj = db.get(QRMarker, marker["id"])
    assert obj.state == "needs_verification"
    qr.reconcile(db, seeded, release_projection(db, seeded), identity[0], "rollback-test")
    assert obj.state == "needs_verification"
    from app.schemas.qr import Installation

    qr.verify(db, obj, identity[0], Installation.model_validate(installation()), "reverified-test")
    del projected["nodes"][data["node_id"]]
    qr.reconcile(db, seeded, projected, identity[0], "removed-test")
    assert obj.state == "retired"
    qr.reconcile(db, seeded, release_projection(db, seeded), identity[0], "rollback-test")
    assert obj.state == "retired"
    assert route(client, bundle, marker).status_code == 410
    assert client.get(f"/api/v1/qr/{uuid4()}").status_code == 404


def test_qr_survives_real_independent_publication_and_removed_indoor_target_rollback(
    client, db, bundle, identity, reviewer
):
    from tests.integration.test_connections import EXPECTED, setup_two, write
    from tests.integration.test_floorplans import current
    from tests.integration.test_indoor import ack
    from tests.integration.test_publication import approve

    draft, path, ground, upper, h, changes = setup_two(client, db, bundle, identity, reviewer)
    old = client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()["id"]
    assert write(client, path, h, changes).status_code == 200
    a, b, u, v = (EXPECTED[k] for k in ("ground_101", "ground_102", "upper_201", "upper_202"))
    routes = [
        {
            "source": x,
            "target": y,
            "profile": p,
            "expected_found": True,
            "reason": "Invented calibrated two-floor acceptance, not real navigation.",
        }
        for x, y in (
            (a, b),
            (u, v),
            (a, u),
            (u, a),
            (str(next(p.id for p in bundle.places if p.code == "GATE")), u),
            (u, str(next(p.id for p in bundle.places if p.code == "GATE"))),
        )
        for p in ("shortest", "step_free")
    ]
    r = client.post(
        path + "/validations", json={"routes": routes}, headers=version(h, current(client, path))
    )
    assert r.status_code == 200 and r.json()["report"]["errors"] == 0, r.text
    run = r.json()
    sub = client.post(
        path + "/submissions",
        json={"validation_id": run["id"], "acknowledgements": ack(run)},
        headers=version(h, current(client, path)),
    ).json()
    rh, edit = approve(client, bundle, draft, run, sub, reviewer)
    published = client.post(
        path + "/publish",
        json={"submission_id": sub["id"], "expected_release_id": old, "key": str(uuid4())},
        headers=version(rh, edit),
    )
    assert published.status_code == 200, published.text
    release = client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()
    h = sign_in(client, identity)
    inventory = client.get(endpoint(bundle)).json()
    start = next(
        t
        for t in inventory["targets"]
        if t["kind"] == "indoor"
        and t["label"] == "Synthetic door101"
        and t["floor_label"] == "Synthetic ground floor"
    )
    created = client.post(
        endpoint(bundle),
        json={
            "key": str(uuid4()),
            "label": "Synthetic ground QR",
            "node_kind": "indoor",
            "node_id": start["id"],
            "intended_position": "Simulated synthetic ground node sign.",
        },
        headers=h,
    )
    assert created.status_code == 201, created.text
    marker = created.json()
    r = client.post(
        endpoint(bundle) + f"/{marker['id']}/activate", json=installation(), headers=version(h, 1)
    )
    assert r.status_code == 200, r.text
    marker = r.json()
    resolved = client.get(f"/api/v1/qr/{marker['id']}").json()
    assert resolved["floor_id"] == ground and resolved["floor_label"] == "Synthetic ground floor"
    for destination, profile in ((b, "shortest"), (u, "shortest"), (u, "step_free")):
        r = client.post(
            "/api/v1/routes",
            json={
                "campus_id": str(bundle.campus.id),
                "source": {
                    "kind": "qr",
                    "marker_id": marker["id"],
                    "expected_marker_version": marker["version"],
                    "confirmed": True,
                },
                "destination": {"place_id": destination},
                "profile": profile,
                "expected_release_id": release["id"],
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["floors"] and r.json()["source_node_id"] == start["id"]
        assert r.json()["distance_m"] == (
            18 if destination == b else 57 if profile == "step_free" else 36
        )
        if profile == "step_free":
            assert any(s["kind"] == "lift" for s in r.json()["segments"])
    rh = sign_in(client, reviewer)
    rollback = client.post(
        f"/api/v1/admin/campuses/{bundle.campus.id}/rollback",
        json={
            "target_release_id": old,
            "expected_release_id": release["id"],
            "key": str(uuid4()),
            "reason": "Synthetic rollback removes the published floor and its QR node.",
        },
        headers=rh,
    )
    assert rollback.status_code == 200, rollback.text
    assert client.get(f"/api/v1/qr/{marker['id']}").json()["state"] == "retired"
    # Forward rollback is deliberately disallowed. Publish another independently
    # reviewed outdoor draft, then restore the earlier indoor release normally.
    from tests.integration.test_publication import ready

    next_draft, next_run, next_sub = ready(client, db, bundle, identity, reviewer)
    next_headers, next_edit = approve(client, bundle, next_draft, next_run, next_sub, reviewer)
    next_path = f"/api/v1/admin/campuses/{bundle.campus.id}/drafts/{next_draft['id']}"
    next_release = client.post(
        next_path + "/publish",
        json={"submission_id": next_sub["id"], "expected_release_id": old, "key": str(uuid4())},
        headers=version(next_headers, next_edit),
    )
    assert next_release.status_code == 200, next_release.text
    returned = client.post(
        f"/api/v1/admin/campuses/{bundle.campus.id}/rollback",
        json={
            "target_release_id": release["id"],
            "expected_release_id": next_release.json()["release_id"],
            "key": str(uuid4()),
            "reason": "Synthetic return must not resurrect a retired QR marker.",
        },
        headers=next_headers,
    )
    assert returned.status_code == 200, returned.text
    assert client.get(f"/api/v1/qr/{marker['id']}").json()["state"] == "retired"
    assert db.get(QRMarker, marker["id"]).version == 5


def test_unpublished_graph_and_floor_nodes_cannot_change_qr_inventory_or_public_route(
    client, db, bundle, identity
):
    from tests.integration.test_admin import make_draft
    from tests.integration.test_admin_graph import node_data

    h, data, marker = create(client, bundle, identity)
    draft = make_draft(client, bundle, h)
    path = f"/api/v1/admin/campuses/{bundle.campus.id}/drafts/{draft['id']}/graph"
    state = client.get(path).json()
    changed = node_data(state, data["node_id"])
    changed["label"] = "Unpublished gate label"
    new_id = str(uuid4())
    added = {**changed, "label": "Unpublished new QR node"}
    saved = client.post(
        path,
        json={
            "changes": [
                {"entity": "nodes", "id": data["node_id"], "data": changed},
                {"entity": "nodes", "id": new_id, "data": added},
            ]
        },
        headers=version(h, 1),
    )
    assert saved.status_code == 200, saved.text
    assert client.get(f"/api/v1/qr/{marker['id']}").json()["node_label"] == "Gate"
    targets = client.get(endpoint(bundle)).json()["targets"]
    assert all(t["id"] != new_id for t in targets)
    r = client.post(
        endpoint(bundle), json={**data, "key": str(uuid4()), "node_id": new_id}, headers=h
    )
    assert r.status_code == 422
    assert route(client, bundle, marker).json()["distance_m"] == 256.88
