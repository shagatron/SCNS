"""Real PostGIS permission, isolation, transaction and session regression tests."""

import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import DBAPIError

from app.cli.admin import bootstrap
from app.core.config import get_settings
from app.models import Campus, Revision
from app.models.admin import AdminSession, AuditEvent, RoleAssignment
from app.services.admin_auth import COOKIE, HASHER, digest
from app.services.admin_catalog import create_draft

pytestmark = pytest.mark.integration
BASE = "/api/v1/admin"
ORIGIN = {"Origin": "http://127.0.0.1:5173"}


@pytest.fixture
def identity(db, bundle, seeded):
    password = secrets.token_urlsafe(24)
    user = bootstrap(db, "owner", "Test owner", password, bundle.campus.id)
    db.flush()
    return user, password


def sign_in(client, identity):
    response = client.post(
        BASE + "/login",
        json={"username": identity[0].username, "password": identity[1]},
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    return {**ORIGIN, "X-CSRF-Token": response.json()["csrf_token"]}


def campus_path(bundle):
    return f"{BASE}/campuses/{bundle.campus.id}"


def make_draft(client, bundle, headers):
    response = client.post(campus_path(bundle) + "/drafts", headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def catalog_path(bundle, draft, entity):
    return campus_path(bundle) + f"/drafts/{draft['id']}/catalog/{entity}"


def version(headers, number):
    return {**headers, "If-Match": f'"{number}"'}


def test_bootstrap_one_time_and_password_hash(db, bundle, identity):
    assert identity[0].password_hash.startswith("$argon2id$")
    assert HASHER.verify(identity[0].password_hash, identity[1])
    with pytest.raises(ValueError, match="already consumed"):
        bootstrap(db, "another", "Another", secrets.token_urlsafe(24), bundle.campus.id)
    for table in ["admin_bootstrap", "audit_events"]:
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(text(f"DELETE FROM {table}"))


def test_login_origin_csrf_session_rotation_logout_and_no_secrets(client, db, bundle, identity):
    assert client.get(campus_path(bundle) + "/dashboard").status_code == 401
    payload = {"username": "owner", "password": identity[1]}
    assert client.post(BASE + "/login", json=payload).status_code == 403
    assert (
        client.post(
            BASE + "/login", json=payload, headers={"Origin": "https://evil.test"}
        ).status_code
        == 403
    )
    response = client.post(BASE + "/login", json=payload, headers=ORIGIN)
    assert response.status_code == 200
    assert (
        "HttpOnly" in response.headers["set-cookie"]
        and "SameSite=strict" in response.headers["set-cookie"]
    )
    assert "Path=/api/v1/admin" in response.headers["set-cookie"]
    assert response.headers["cache-control"] == "no-store"
    token = client.cookies.get(COOKIE)
    assert db.scalar(select(AdminSession.token_hash)) == digest(token)
    csrf = response.json()["csrf_token"]
    assert client.post(campus_path(bundle) + "/drafts", headers=ORIGIN).status_code == 403
    assert (
        client.post(
            campus_path(bundle) + "/drafts",
            headers={"Origin": "https://evil.test", "X-CSRF-Token": csrf},
        ).status_code
        == 403
    )
    headers = sign_in(client, identity)
    assert client.cookies.get(COOKIE) != token
    assert db.scalar(
        select(AdminSession.revoked_at).where(AdminSession.token_hash == digest(token))
    )
    assert client.post(BASE + "/logout", headers=headers).status_code == 204
    assert client.get(BASE + "/session").status_code == 401
    client.cookies.set(COOKIE, token)
    assert client.get(BASE + "/session").status_code == 401
    events = repr(db.scalars(select(AuditEvent.after)).all())
    assert identity[1] not in events and token not in events and csrf not in events


@pytest.mark.parametrize("disabled", [False, True])
def test_expiry_and_disabled_account(client, db, identity, disabled):
    sign_in(client, identity)
    if disabled:
        identity[0].active = False
    else:
        db.scalar(select(AdminSession)).expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.flush()
    assert client.get(BASE + "/session").status_code == 401


def test_durable_login_throttle_and_generic_failures(client, db, identity, monkeypatch):
    monkeypatch.setenv("LOGIN_ACCOUNT_LIMIT", "2")
    get_settings.cache_clear()
    for username in ["owner", "unknown"]:
        for _ in range(2):
            response = client.post(
                BASE + "/login",
                json={"username": username, "password": "incorrect"},
                headers=ORIGIN,
            )
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "invalid_credentials"
        response = client.post(
            BASE + "/login", json={"username": username, "password": identity[1]}, headers=ORIGIN
        )
        assert response.status_code == 429 and response.headers["retry-after"] == "900"
    assert db.scalar(select(func.count()).select_from(AdminSession)) == 0


@pytest.mark.parametrize(
    "role,can_read,can_edit,can_audit,can_users",
    [
        ("editor", True, True, False, False),
        ("reviewer_publisher", True, False, True, False),
        ("operations", False, False, False, False),
        ("system_admin", True, True, True, True),
    ],
)
def test_role_matrix_and_live_revocation(
    client, db, bundle, identity, role, can_read, can_edit, can_audit, can_users
):
    draft = create_draft(db, bundle.campus.id, identity[0].id, "test")
    db.execute(delete(RoleAssignment))
    db.add(RoleAssignment(user_id=identity[0].id, campus_id=bundle.campus.id, role=role))
    db.flush()
    headers = sign_in(client, identity)
    path = campus_path(bundle)
    dashboard = client.get(path + "/dashboard")
    assert dashboard.status_code == 200
    assert bool(dashboard.json()["drafts"]) == can_read
    assert client.get(path + f"/drafts/{draft.id}/catalog/places").status_code == (
        200 if can_read else 403
    )
    assert client.post(path + "/drafts", headers=headers).status_code == (201 if can_edit else 403)
    payload = {"entity": "departments", "data": {"code": "NEW", "name": "New"}}
    assert client.post(
        path + f"/drafts/{draft.id}/catalog/departments", json=payload, headers=version(headers, 1)
    ).status_code == (201 if can_edit else 403)
    assert client.get(path + "/audit").status_code == (200 if can_audit else 403)
    assert client.get(path + "/users").status_code == (200 if can_users else 403)
    assert client.post(
        path + "/users",
        headers=headers,
        json={
            "username": "new-user",
            "display_name": "New user",
            "password": secrets.token_urlsafe(24),
            "role": "editor",
        },
    ).status_code == (201 if can_users else 403)
    db.execute(delete(RoleAssignment).where(RoleAssignment.user_id == identity[0].id))
    db.flush()
    assert client.get(path + "/dashboard").status_code == 403


def test_campus_isolation_even_system_admin(client, db, bundle, identity):
    first = db.get(Campus, bundle.campus.id)
    other = Campus(
        id=uuid4(),
        code="OTHER",
        name="Other campus",
        timezone="UTC",
        is_demo=True,
        center=first.center,
        boundary=first.boundary,
    )
    db.add(other)
    db.flush()
    draft = create_draft(db, other.id, identity[0].id, "test")
    headers = sign_in(client, identity)
    path = f"{BASE}/campuses/{other.id}"
    for suffix in [
        "/dashboard",
        "/users",
        "/audit",
        f"/drafts/{draft.id}/catalog/places",
        f"/drafts/{draft.id}/nodes",
    ]:
        assert client.get(path + suffix).status_code == 403
    assert client.post(path + "/drafts", headers=headers).status_code == 403
    assert client.get(campus_path(bundle) + f"/drafts/{draft.id}/catalog/places").status_code == 404
    assert (
        client.post(
            campus_path(bundle) + f"/drafts/{draft.id}/catalog/departments",
            json={"entity": "departments", "data": {"code": "X", "name": "X"}},
            headers=version(headers, 1),
        ).status_code
        == 404
    )


def test_crud_all_entities_concurrency_audit_and_public_unchanged(
    client, db, bundle, identity, seeded
):
    headers = sign_in(client, identity)
    public = f"/api/v1/campuses/{bundle.campus.id}"
    search_before = client.get(public + "/search").json()
    map_before = client.get(public + "/map?bbox=-.001,-.001,.004,.004").json()
    places = {p.code: str(p.id) for p in bundle.places}
    route_body = {
        "campus_id": str(bundle.campus.id),
        "source": {"kind": "place", "place_id": places["GATE"]},
        "destination": {"kind": "place", "place_id": places["LIB"]},
    }
    route_before = client.post("/api/v1/routes", json=route_body).json()
    draft = make_draft(client, bundle, headers)
    assert db.get(Revision, draft["id"]).checksum is None
    number = 1
    created = {}
    fields = {
        "buildings": {
            "code": "NEW",
            "name": "Draft building",
            "footprint": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [0.001, 0], [0.001, 0.001], [0, 0]]],
            },
        },
        "places": {
            "code": "NEW",
            "name": "Draft place",
            "kind": "help",
            "point": {"type": "Point", "coordinates": [0, 0]},
        },
        "departments": {"code": "NEW", "name": "Draft department"},
        "aliases": {"value": "Unpublished alias", "language": "en"},
        "anchors": {
            "node_id": str(next(n.id for n in bundle.nodes if n.visibility == "public")),
            "accessibility_status": "unknown",
            "is_open": True,
        },
    }
    for entity, data in fields.items():
        if entity == "places":
            data["building_id"] = created["buildings"]
        if entity == "departments":
            data["place_ids"] = [created["places"]]
        if entity in {"aliases", "anchors"}:
            data["place_id"] = created["places"]
        path = catalog_path(bundle, draft, entity)
        payload = {"entity": entity, "data": data}
        assert client.post(path, json=payload, headers=headers).status_code == 428
        response = client.post(path, json=payload, headers=version(headers, number))
        assert response.status_code == 201, response.text
        created[entity] = response.json()["id"]
        assert response.json()["revision_version"] == number + 1
        # Same optimistic version cannot overwrite a successful change.
        assert (
            client.put(
                path + "/" + created[entity], json=payload, headers=version(headers, number)
            ).status_code
            == 409
        )
        number += 1
        if "name" in data:
            data["name"] += " revised"
        elif entity == "aliases":
            data["value"] += " revised"
        else:
            data["is_open"] = False
        response = client.put(
            path + "/" + created[entity], json=payload, headers=version(headers, number)
        )
        assert response.status_code == 200, response.text
        number += 1
        read = client.get(path)
        assert read.headers["etag"] == f'"{number}"'
        assert any(item["id"] == created[entity] for item in read.json()["items"])
    assert client.get(public + "/search").json() == search_before
    assert client.get(public + "/map?bbox=-.001,-.001,.004,.004").json() == map_before
    route_after = client.post("/api/v1/routes", json=route_body).json()
    for volatile in ["id", "generated_at", "departure_at"]:
        route_before.pop(volatile)
        route_after.pop(volatile)
    assert route_after == route_before
    assert client.get(f"/api/v1/places/{created['places']}").status_code == 404
    # Referenced parents cannot be deleted. Failed writes do not consume versions/audit.
    assert (
        client.delete(
            catalog_path(bundle, draft, "places") + "/" + created["places"],
            headers=version(headers, number),
        ).status_code
        == 409
    )
    for entity in ["anchors", "aliases", "departments", "places", "buildings"]:
        response = client.delete(
            catalog_path(bundle, draft, entity) + "/" + created[entity],
            headers=version(headers, number),
        )
        assert response.status_code == 200, response.text
        number += 1
    events = client.get(campus_path(bundle) + "/audit").json()
    writes = [e for e in events if e["action"].startswith("catalog.")]
    assert len(writes) == 15
    assert all(
        e["actor_id"] == str(identity[0].id) and e["revision_id"] == draft["id"] and e["request_id"]
        for e in writes
    )
    assert all(e["before"] and e["after"] for e in writes if e["action"].endswith("update"))
    assert (
        client.get(
            campus_path(bundle) + f"/drafts/{seeded.dataset_revision_id}/catalog/places"
        ).status_code
        == 404
    )


def test_invalid_references_visibility_and_conflict_rollback(client, db, bundle, identity):
    headers = sign_in(client, identity)
    draft = make_draft(client, bundle, headers)
    path = catalog_path(bundle, draft, "aliases")
    data = {"entity": "aliases", "data": {"place_id": str(uuid4()), "value": "Missing"}}
    assert client.post(path, json=data, headers=version(headers, 1)).status_code == 422
    data = {
        "entity": "anchors",
        "data": {
            "place_id": str(next(p.id for p in bundle.places if p.visibility == "public")),
            "node_id": str(next(n.id for n in bundle.nodes if n.visibility == "restricted")),
        },
    }
    assert (
        client.post(
            catalog_path(bundle, draft, "anchors"), json=data, headers=version(headers, 1)
        ).status_code
        == 422
    )
    assert client.get(path).json()["revision_version"] == 1
    # Invalid geometry and duplicate codes are atomic failures too.
    data = {
        "entity": "places",
        "data": {
            "code": "GATE",
            "name": "Duplicate",
            "kind": "help",
            "point": {"type": "Point", "coordinates": [0, 0]},
        },
    }
    assert (
        client.post(
            catalog_path(bundle, draft, "places"), json=data, headers=version(headers, 1)
        ).status_code
        == 409
    )
    assert client.get(path).json()["revision_version"] == 1


def test_user_management_last_admin_and_cross_campus_user(client, db, bundle, identity):
    headers = sign_in(client, identity)
    path = campus_path(bundle) + "/users"
    assert (
        client.put(
            path + f"/{identity[0].id}/role", json={"role": "editor"}, headers=headers
        ).status_code
        == 409
    )
    password = secrets.token_urlsafe(24)
    response = client.post(
        path,
        json={
            "username": "second",
            "display_name": "Second",
            "password": password,
            "role": "system_admin",
        },
        headers=headers,
    )
    assert response.status_code == 201
    assert password not in response.text and "password_hash" not in response.text
    assert (
        client.put(path + f"/{uuid4()}/role", json={"role": "editor"}, headers=headers).status_code
        == 404
    )
    assert (
        client.put(
            path + f"/{identity[0].id}/role", json={"role": "editor"}, headers=headers
        ).status_code
        == 200
    )
    assert client.get(path).status_code == 403
