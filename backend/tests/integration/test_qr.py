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


@pytest.fixture
def identity(db, bundle, seeded):
    return owner_identity.__wrapped__(db, bundle, seeded)


pytestmark = pytest.mark.integration


def endpoint(bundle):
    return f"/api/v1/admin/campuses/{bundle.campus.id}/qr-markers"


def payload(client, bundle):
    targets = client.get(endpoint(bundle)).json()["targets"]
    node = next(t for t in targets if t["label"] == "Main Gate")
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
