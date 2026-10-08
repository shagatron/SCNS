from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.models import Revision
from app.models.admin import AuditEvent, RoleAssignment, User
from app.services.admin_auth import HASHER
from tests.integration.test_admin import identity as identity_fixture
from tests.integration.test_admin import sign_in

pytestmark = pytest.mark.integration


@pytest.fixture
def identity(db, bundle, seeded):
    return identity_fixture.__wrapped__(db, bundle, seeded)


def test_draft_creation_retry_is_actor_campus_scoped_and_audited_once(client, db, bundle, identity):
    h = sign_in(client, identity)
    path = f"/api/v1/admin/campuses/{bundle.campus.id}/drafts"
    key = str(uuid4())
    h["Idempotency-Key"] = key
    first = client.post(path, headers=h)
    again = client.post(path, headers=h)
    assert first.status_code == again.status_code == 201
    assert first.json() == again.json()
    revision = UUID(first.json()["id"])
    assert (
        db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "draft.create", AuditEvent.revision_id == revision)
        )
        == 1
    )
    assert client.post(path, headers={**h, "Idempotency-Key": "bad key!"}).status_code == 422
    assert client.post(path, headers={**h, "X-CSRF-Token": "invalid"}).status_code == 403
    assert client.post(f"/api/v1/admin/campuses/{uuid4()}/drafts", headers=h).status_code in (
        403,
        404,
    )
    db.get(Revision, revision).status = "review"
    db.flush()
    assert client.post(path, headers=h).status_code == 409


def test_new_actor_cannot_adopt_another_actors_retry_key(client, db, bundle, identity):
    h = sign_in(client, identity)
    path = f"/api/v1/admin/campuses/{bundle.campus.id}/drafts"
    key = str(uuid4())
    first = client.post(path, headers={**h, "Idempotency-Key": key}).json()
    user = User(
        username="another-editor", display_name="Another", password_hash=HASHER.hash(identity[1])
    )
    db.add(user)
    db.flush()
    db.add(RoleAssignment(user_id=user.id, campus_id=bundle.campus.id, role="editor"))
    db.flush()
    h = sign_in(client, (user, identity[1]))
    second = client.post(path, headers={**h, "Idempotency-Key": key})
    assert second.status_code == 201 and second.json()["id"] != first["id"]
