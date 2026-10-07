"""Exact-content review/publication on transactional isolated real PostGIS fixtures."""

import hashlib
import secrets
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.models import ActiveRelease, Release, Revision
from app.models.admin import AuditEvent, RoleAssignment, User
from app.models.publication import ReleaseArtifact, ReviewSubmission
from app.services import publication as service
from app.services.admin_auth import HASHER
from tests.integration.test_admin import (  # noqa: F401
    ORIGIN,
    make_draft,
    sign_in,
    version,
)
from tests.integration.test_admin import (
    identity as owner_identity,
)


@pytest.fixture
def identity(db, bundle, seeded):
    return owner_identity.__wrapped__(db, bundle, seeded)


pytestmark = pytest.mark.integration


@pytest.fixture
def reviewer(db, bundle):
    password = secrets.token_urlsafe(24)
    user = User(
        username="reviewer",
        display_name="Independent reviewer",
        password_hash=HASHER.hash(password),
    )
    db.add(user)
    db.flush()
    db.add(RoleAssignment(user_id=user.id, campus_id=bundle.campus.id, role="reviewer_publisher"))
    db.flush()
    return user, password


def path(bundle, draft):
    return f"/api/v1/admin/campuses/{bundle.campus.id}/drafts/{draft['id']}"


def expectations(bundle):
    gate = next(p.id for p in bundle.places if p.code == "GATE")
    lib = next(p.id for p in bundle.places if p.code == "LIB")
    return {
        "routes": [
            {
                "source": str(gate),
                "target": str(lib),
                "profile": profile,
                "expected_found": True,
                "maximum_distance_m": 1000,
                "reason": "Synthetic gate/library acceptance route, no field verification.",
            }
            for profile in ("shortest", "step_free")
        ]
    }


def ack(run):
    return {
        f["id"]: "Reviewed synthetic coverage/evidence limitation; no real navigation claim."
        for f in run["report"]["diagnostics"]
        if f["severity"] == "warning"
    }


def source_payload(overlay=False):
    return {
        "title": "Synthetic invented vectors",
        "rights": "synthetic",
        "provenance": "Invented campus fixture only; internal note PRIVATE-SOURCE-NOTE",
        "attribution": "Synthetic demonstration, no physical survey",
        "display_overlay": overlay,
        "original": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0.001, 0.001]},
                    "properties": {
                        "label": "Synthetic marker",
                        "private": "SECRET-ORIGINAL",
                        "public": True,
                    },
                }
            ],
        }
        if overlay
        else None,
    }


def ready(client, db, bundle, identity, reviewer, *, overlay=False):
    owner_headers = sign_in(client, identity)
    draft = make_draft(client, bundle, owner_headers)
    base = path(bundle, draft)
    source = client.post(
        base + "/sources", headers=version(owner_headers, 1), json=source_payload(overlay)
    )
    assert source.status_code == 201, source.text
    review_headers = sign_in(client, reviewer)
    approved_source = client.post(
        base + f"/sources/{source.json()['id']}/approve", headers=version(review_headers, 2)
    )
    assert approved_source.status_code == 200, approved_source.text
    owner_headers = sign_in(client, identity)
    run = client.post(
        base + "/validations", json=expectations(bundle), headers=version(owner_headers, 3)
    )
    assert run.status_code == 200, run.text
    assert run.json()["report"]["errors"] == 0, run.text
    submission = client.post(
        base + "/submissions",
        json={"validation_id": run.json()["id"], "acknowledgements": ack(run.json())},
        headers=version(owner_headers, 3),
    )
    assert submission.status_code == 200, submission.text
    return draft, run.json(), submission.json()


def approve(client, bundle, draft, run, submission, reviewer):
    headers = sign_in(client, reviewer)
    response = client.post(
        path(bundle, draft) + f"/submissions/{submission['id']}/decision",
        json={
            "decision": "approve",
            "notes": "Independent synthetic review; content, diff, source, routes inspected.",
            "acknowledgements": ack(run),
        },
        headers=version(headers, submission["edit_version"]),
    )
    assert response.status_code == 200, response.text
    return headers, response.json()["edit_version"]


def test_review_publish_projection_retry_rollback_and_immutability(
    client, db, bundle, identity, reviewer
):
    old = client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()
    draft, run, submission = ready(client, db, bundle, identity, reviewer, overlay=True)
    assert client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()["id"] == old["id"]
    headers, edit = approve(client, bundle, draft, run, submission, reviewer)
    payload = {
        "submission_id": submission["id"],
        "expected_release_id": old["id"],
        "key": "publish-test-unique",
    }
    published = client.post(
        path(bundle, draft) + "/publish", json=payload, headers=version(headers, edit)
    )
    assert published.status_code == 200, published.text
    result = published.json()
    assert result["release_id"] != old["id"]
    assert (
        client.post(
            path(bundle, draft) + "/publish", json=payload, headers=version(headers, edit)
        ).json()
        == result
    )
    assert (
        client.post(
            path(bundle, draft) + "/publish",
            json={**payload, "expected_release_id": None},
            headers=version(headers, edit),
        ).status_code
        == 409
    )
    assert db.scalar(select(func.count()).select_from(ReleaseArtifact)) == 1
    artifact = db.get(ReleaseArtifact, result["release_id"])
    public = artifact.content
    assert artifact.checksum == service.checksum(public)
    assert public["assets"] and "private" not in service.canonical(public).decode()
    assert "PRIVATE-SOURCE-NOTE" not in service.canonical(public).decode()
    assert "SECRET-ORIGINAL" not in service.canonical(public).decode()
    restricted = {str(p.id) for p in bundle.places if p.visibility == "restricted"}
    assert restricted.isdisjoint(public["places"])
    for table in (
        "release_artifacts",
        "validation_runs",
        "review_decisions",
        "release_actions",
        "releases",
    ):
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(text(f"DELETE FROM {table}"))
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(
            text("UPDATE places SET name='tampered' WHERE dataset_revision_id=:id"),
            {"id": draft["id"]},
        )
    rollback = {
        "target_release_id": old["id"],
        "expected_release_id": result["release_id"],
        "key": "rollback-test-unique",
        "reason": "Return to earlier known synthetic map release.",
    }
    endpoint = f"/api/v1/admin/campuses/{bundle.campus.id}/rollback"
    rolled = client.post(endpoint, json=rollback, headers=headers)
    assert rolled.status_code == 200, rolled.text
    assert client.post(endpoint, json=rollback, headers=headers).json() == rolled.json()
    assert client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()["id"] == old["id"]
    assert db.scalar(select(func.count()).select_from(Release)) == 2
    assert (
        db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "release.publish")
        )
        == 1
    )
    assert (
        db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "release.rollback")
        )
        == 1
    )


def test_separation_return_to_draft_and_stale_validation(client, db, bundle, identity, reviewer):
    draft, run, submission = ready(client, db, bundle, identity, reviewer)
    base = path(bundle, draft)
    headers = sign_in(client, identity)
    self_review = client.post(
        base + f"/submissions/{submission['id']}/decision",
        headers=version(headers, 4),
        json={
            "decision": "approve",
            "notes": "I am a system administrator but submitted this change.",
            "acknowledgements": ack(run),
        },
    )
    assert self_review.status_code == 403
    assert self_review.json()["error"]["code"] == "separation_of_duties"
    assert (
        client.post(
            base + "/graph",
            headers=version(headers, 4),
            json={
                "changes": [
                    {
                        "entity": "nodes",
                        "id": str(uuid4()),
                        "data": {
                            "frame_id": str(bundle.frames[0].id),
                            "label": "Attempt review mutation",
                            "point": {"type": "Point", "coordinates": [0.001, 0.001]},
                        },
                    }
                ]
            },
        ).status_code
        == 404
    )
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(
            text("UPDATE places SET name='review tamper' WHERE dataset_revision_id=:id"),
            {"id": draft["id"]},
        )
    withdrawn = client.post(
        base + f"/submissions/{submission['id']}/decision",
        headers=version(headers, 4),
        json={
            "decision": "withdraw",
            "notes": "Need to correct the proposed dataset before independent review.",
        },
    )
    assert withdrawn.status_code == 200
    assert (
        client.post(
            base + "/submissions",
            headers=version(headers, 5),
            json={"validation_id": run["id"], "acknowledgements": ack(run)},
        ).status_code
        == 409
    )
    assert db.get(Revision, draft["id"]).status == "draft"
    assert db.get(ReviewSubmission, submission["id"]).status == "withdrawn"


@pytest.mark.parametrize("failure", ["artifact", "audit"])
def test_failed_publication_is_atomic(client, db, bundle, identity, reviewer, monkeypatch, failure):
    draft, run, submission = ready(client, db, bundle, identity, reviewer)
    headers, edit = approve(client, bundle, draft, run, submission, reviewer)
    old = client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()["id"]

    def fail(*args, **kwargs):
        raise RuntimeError("Injected bounded artifact/audit failure")

    monkeypatch.setattr(service, "generate_artifact" if failure == "artifact" else "audit", fail)
    with pytest.raises(RuntimeError, match="Injected"):
        client.post(
            path(bundle, draft) + "/publish",
            headers=version(headers, edit),
            json={
                "submission_id": submission["id"],
                "expected_release_id": old,
                "key": "failure-test-publish",
            },
        )
    db.expire_all()
    assert db.get(Revision, draft["id"]).status == "review"
    assert db.get(Revision, draft["id"]).edit_version == edit
    assert db.get(ReviewSubmission, submission["id"]).status == "approved"
    assert db.get(ActiveRelease, (bundle.campus.id, "public")).release_id == UUID(old)
    assert db.scalar(select(func.count()).select_from(ReleaseArtifact)) == 0
    assert db.scalar(select(func.count()).select_from(Release)) == 1


def test_validation_blocks_source_routes_and_unacknowledged_warnings(
    client, db, bundle, identity, reviewer
):
    headers = sign_in(client, identity)
    draft = make_draft(client, bundle, headers)
    base = path(bundle, draft)
    wrong = expectations(bundle)
    wrong["routes"][0]["expected_found"] = False
    result = client.post(base + "/validations", json=wrong, headers=version(headers, 1))
    assert result.status_code == 200, result.text
    codes = {f["code"] for f in result.json()["report"]["diagnostics"] if f["severity"] == "error"}
    assert {"source_approval", "route_expectation"} <= codes
    assert (
        client.post(
            base + "/submissions",
            json={"validation_id": result.json()["id"], "acknowledgements": ack(result.json())},
            headers=version(headers, 1),
        ).status_code
        == 422
    )
    draft, run, submission = ready(client, db, bundle, identity, reviewer)
    headers = sign_in(client, reviewer)
    rejected_ack = client.post(
        path(bundle, draft) + f"/submissions/{submission['id']}/decision",
        json={
            "decision": "approve",
            "notes": "Attempt without acknowledging all material warnings.",
        },
        headers=version(headers, 4),
    )
    assert rejected_ack.status_code == 422
    assert db.get(ReviewSubmission, submission["id"]).status == "submitted"


@pytest.mark.parametrize("role", ["editor", "reviewer_publisher", "operations", "system_admin"])
def test_permission_matrix_campus_csrf_and_source_review(
    client, db, bundle, identity, reviewer, role
):
    headers = sign_in(client, identity)
    draft = make_draft(client, bundle, headers)
    base = path(bundle, draft)
    source = client.post(
        base + "/sources", json=source_payload(), headers=version(headers, 1)
    ).json()
    own = client.post(base + f"/sources/{source['id']}/approve", headers=version(headers, 2))
    assert own.status_code == 403
    db.add(
        RoleAssignment(user_id=reviewer[0].id, campus_id=bundle.campus.id, role=role)
    ) if role != "reviewer_publisher" else None
    if role != "reviewer_publisher":
        db.execute(
            text("DELETE FROM role_assignments WHERE user_id=:user AND role='reviewer_publisher'"),
            {"user": reviewer[0].id},
        )
    db.flush()
    headers = sign_in(client, reviewer)
    assert client.get(base + "/review").status_code == (403 if role == "operations" else 200)
    assert client.post(
        base + "/validations", headers=version(headers, 2), json=expectations(bundle)
    ).status_code == (200 if role in {"editor", "system_admin"} else 403)
    assert client.post(
        base + f"/sources/{source['id']}/approve", headers=version(headers, 2)
    ).status_code == (200 if role in {"reviewer_publisher", "system_admin"} else 403)
    current_version = db.get(Revision, draft["id"]).edit_version
    publisher_allowed = role in {"reviewer_publisher", "system_admin"}
    assert client.post(
        base + "/publish",
        headers=version(headers, current_version),
        json={
            "submission_id": str(uuid4()),
            "expected_release_id": None,
            "key": "permission-matrix-publish",
        },
    ).status_code == (404 if publisher_allowed else 403)
    assert client.post(
        base + f"/submissions/{uuid4()}/decision",
        headers=version(headers, current_version),
        json={"decision": "reject", "notes": "Permission matrix rejects a nonexistent submission."},
    ).status_code == (404 if publisher_allowed else 403)
    old = client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()["id"]
    assert client.post(
        f"/api/v1/admin/campuses/{bundle.campus.id}/rollback",
        headers=headers,
        json={
            "target_release_id": str(uuid4()),
            "expected_release_id": old,
            "key": "permission-matrix-rollback",
            "reason": "Permission matrix refuses a foreign/unknown release.",
        },
    ).status_code == (422 if publisher_allowed else 403)
    foreign = base.replace(str(bundle.campus.id), str(uuid4()))
    assert client.get(foreign + "/review").status_code == 403
    assert client.get(base.replace(draft["id"], str(uuid4())) + "/review").status_code == (
        403 if role == "operations" else 404
    )
    assert (
        client.post(base + "/validations", headers=ORIGIN, json=expectations(bundle)).status_code
        == 403
    )


def test_edits_invalidate_validation_and_public_api_switches_coherently(
    client, db, bundle, identity, reviewer
):
    headers = sign_in(client, identity)
    draft = make_draft(client, bundle, headers)
    base = path(bundle, draft)
    source = client.post(
        base + "/sources", json=source_payload(), headers=version(headers, 1)
    ).json()
    rev_headers = sign_in(client, reviewer)
    assert (
        client.post(
            base + f"/sources/{source['id']}/approve", headers=version(rev_headers, 2)
        ).status_code
        == 200
    )
    headers = sign_in(client, identity)
    run = client.post(
        base + "/validations", json=expectations(bundle), headers=version(headers, 3)
    ).json()
    library = next(p for p in bundle.places if p.code == "LIB")
    change = library.model_dump(mode="json", exclude={"id", "aliases"})
    change["name"] = "Synthetic Reviewed Library"
    response = client.put(
        base + f"/catalog/places/{library.id}",
        json={"entity": "places", "data": change},
        headers=version(headers, 3),
    )
    assert response.status_code == 200, response.text
    assert (
        client.post(
            base + "/submissions",
            json={"validation_id": run["id"], "acknowledgements": ack(run)},
            headers=version(headers, 4),
        ).status_code
        == 409
    )
    old = client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()["id"]
    assert client.get(f"/api/v1/campuses/{bundle.campus.id}/search?q=Reviewed").json()["total"] == 0
    fresh = client.post(
        base + "/validations", json=expectations(bundle), headers=version(headers, 4)
    ).json()
    submitted = client.post(
        base + "/submissions",
        json={"validation_id": fresh["id"], "acknowledgements": ack(fresh)},
        headers=version(headers, 4),
    ).json()
    rev_headers, edit = approve(client, bundle, draft, fresh, submitted, reviewer)
    assert (
        client.post(
            base + "/publish",
            json={
                "submission_id": submitted["id"],
                "expected_release_id": str(uuid4()),
                "key": "incorrect-pointer",
            },
            headers=version(rev_headers, edit),
        ).status_code
        == 409
    )
    published = client.post(
        base + "/publish",
        json={
            "submission_id": submitted["id"],
            "expected_release_id": old,
            "key": "correct-pointer-new",
        },
        headers=version(rev_headers, edit),
    )
    assert published.status_code == 200, published.text
    new = published.json()["release_id"]
    for suffix in (
        f"search?expected_release_id={old}",
        f"map?bbox=-0.001,-0.001,0.004,0.004&expected_release_id={old}",
        f"directory?expected_release_id={old}",
    ):
        stale = client.get(f"/api/v1/campuses/{bundle.campus.id}/{suffix}")
        assert stale.status_code == 409
        assert stale.json()["error"]["code"] == "stale_release"
    search = client.get(
        f"/api/v1/campuses/{bundle.campus.id}/search?q=Reviewed&expected_release_id={new}"
    ).json()
    assert (
        search["release_id"] == new and search["items"][0]["name"] == "Synthetic Reviewed Library"
    )
    assert (
        client.get(
            f"/api/v1/campuses/{bundle.campus.id}/map?bbox=-0.001,-0.001,0.004,0.004&expected_release_id={new}"
        ).json()["release_id"]
        == new
    )
    request = {
        "campus_id": str(bundle.campus.id),
        "source": {
            "kind": "place",
            "place_id": str(next(p.id for p in bundle.places if p.code == "GATE")),
        },
        "destination": {"kind": "place", "place_id": str(library.id)},
        "expected_release_id": new,
    }
    route = client.post("/api/v1/routes", json=request).json()
    assert route["release_id"] == new and route["distance_m"] == 256.88
    assert route["arrival_instruction"] == "Arrive at Synthetic Reviewed Library."
    metadata = client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()
    artifact = client.get(metadata["artifact_url"])
    assert artifact.status_code == 200
    assert "immutable" in artifact.headers["cache-control"]
    assert hashlib.sha256(artifact.content).hexdigest() == metadata["artifact_checksum"]
    assert (
        client.get(
            metadata["artifact_url"].replace(str(bundle.campus.id), str(uuid4()))
        ).status_code
        == 404
    )


def test_reject_reapprove_and_revoked_reviewer(client, db, bundle, identity, reviewer):
    draft, run, submitted = ready(client, db, bundle, identity, reviewer)
    headers = sign_in(client, reviewer)
    rejected = client.post(
        path(bundle, draft) + f"/submissions/{submitted['id']}/decision",
        headers=version(headers, 4),
        json={
            "decision": "reject",
            "notes": "Source coverage needs correction before this can publish.",
        },
    )
    assert rejected.status_code == 200
    assert db.get(Revision, draft["id"]).status == "draft"
    assert db.get(ReviewSubmission, submitted["id"]).status == "rejected"
    draft, run, submitted = ready(client, db, bundle, identity, reviewer)
    headers, edit = approve(client, bundle, draft, run, submitted, reviewer)
    old = client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()["id"]
    # Account remains active but its campus reviewer grant is revoked.
    db.execute(text("DELETE FROM role_assignments WHERE user_id=:id"), {"id": reviewer[0].id})
    db.flush()
    assert (
        client.post(
            path(bundle, draft) + "/publish",
            json={
                "submission_id": submitted["id"],
                "expected_release_id": old,
                "key": "revoked-publish-role",
            },
            headers=version(headers, edit),
        ).status_code
        == 403
    )
    assert client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()["id"] == old


@pytest.mark.parametrize(
    "case", ["restricted", "invalid_geometry", "no_public", "oversized", "malformed"]
)
def test_source_errors_cannot_change_version_or_audit(client, db, bundle, identity, case):
    headers = sign_in(client, identity)
    draft = make_draft(client, bundle, headers)
    payload = source_payload(True)
    if case == "restricted":
        payload["rights"] = "restricted"
    elif case == "invalid_geometry":
        payload["original"]["features"][0]["geometry"]["coordinates"] = [181, 0]
    elif case == "no_public":
        payload["original"]["features"][0]["properties"]["public"] = False
    elif case == "oversized":
        payload["original"]["padding"] = "X" * (5 * 1024 * 1024)
    audits = db.scalar(select(func.count()).select_from(AuditEvent))
    response = (
        client.post(path(bundle, draft) + "/sources", headers=version(headers, 1), json=payload)
        if case != "malformed"
        else client.post(
            path(bundle, draft) + "/sources", headers=version(headers, 1), content=b'{"title":'
        )
    )
    assert response.status_code == (413 if case == "oversized" else 422)
    assert db.get(Revision, draft["id"]).edit_version == 1
    assert db.scalar(select(func.count()).select_from(AuditEvent)) == audits


def test_rollback_failure_retains_pointer_and_audit(
    client, db, bundle, identity, reviewer, monkeypatch
):
    draft, run, submission = ready(client, db, bundle, identity, reviewer)
    headers, edit = approve(client, bundle, draft, run, submission, reviewer)
    old = client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()["id"]
    current = client.post(
        path(bundle, draft) + "/publish",
        json={
            "submission_id": submission["id"],
            "expected_release_id": old,
            "key": "rollback-failure-setup",
        },
        headers=version(headers, edit),
    ).json()["release_id"]
    audits = db.scalar(select(func.count()).select_from(AuditEvent))

    def fail(*args, **kwargs):
        raise RuntimeError("Rollback audit failure")

    monkeypatch.setattr(service, "audit", fail)
    with pytest.raises(RuntimeError, match="Rollback audit"):
        client.post(
            f"/api/v1/admin/campuses/{bundle.campus.id}/rollback",
            json={
                "target_release_id": old,
                "expected_release_id": current,
                "key": "rollback-failure-key",
                "reason": "Injected rollback failure should preserve current release.",
            },
            headers=headers,
        )
    db.expire_all()
    assert client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()["id"] == current
    assert db.scalar(select(func.count()).select_from(AuditEvent)) == audits
