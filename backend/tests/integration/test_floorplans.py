"""Draft/reference/security/calibration/release boundaries on isolated real PostGIS."""

import hashlib
import json
import secrets
from pathlib import Path
from urllib.parse import quote
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import DBAPIError

from app.core.errors import DomainError
from app.models import Node, Revision
from app.models.admin import AuditEvent, RoleAssignment, User
from app.models.floorplans import Floor, FloorplanJob, MapLayer
from app.models.publication import SourceAsset
from app.services import floorplans as service
from app.services.admin_auth import HASHER
from tests.integration.test_admin import identity as identity_fixture
from tests.integration.test_admin import make_draft, sign_in, version
from tests.integration.test_publication import ack, expectations
from tests.integration.test_publication import reviewer as reviewer_fixture
from tests.unit.test_floorplan_contract import measure

pytestmark = pytest.mark.integration


@pytest.fixture
def identity(db, bundle, seeded):
    return identity_fixture.__wrapped__(db, bundle, seeded)


@pytest.fixture
def reviewer(db, bundle):
    return reviewer_fixture.__wrapped__(db, bundle)


FIXTURES = Path(__file__).resolve().parents[3] / "data/demo/floorplans"


def base(bundle, draft):
    return f"/api/v1/admin/campuses/{bundle.campus.id}/drafts/{draft['id']}"


def current(client, path):
    return client.get(path + "/floors").json()["edit_version"]


def floor_payload(bundle, code="G"):
    return {
        "building_id": str(bundle.buildings[0].id),
        "code": code,
        "label": "Synthetic ground floor" if code == "G" else "Synthetic basement B1",
        "ordering": 0 if code == "G" else -1,
        "elevation_m": None,
        "visibility": "public",
    }


def create(client, bundle, headers):
    draft = make_draft(client, bundle, headers)
    path = base(bundle, draft)
    result = client.post(path + "/floors", json=floor_payload(bundle), headers=version(headers, 1))
    assert result.status_code == 201, result.text
    return draft, path, result.json()["id"]


def options(floor, name="synthetic-ground.png", page=1, key=None):
    return {
        "floor_id": floor,
        "key": key or str(uuid4()),
        "filename": name,
        "page": page,
        "title": "Synthetic floorplan only",
        "rights": "synthetic",
        "provenance": "Invented floorplan PRIVATE-PLAN-NOTES, no institutional source.",
        "attribution": "Synthetic test drawing only",
        "redactions": [{"x": 480, "y": 320, "width": 100, "height": 60}],
    }


def upload(client, path, headers, opts, raw=None):
    content = raw if raw is not None else (FIXTURES / opts["filename"]).read_bytes()
    return client.post(
        path + "/floorplan-jobs",
        content=content,
        headers={
            **version(headers, current(client, path)),
            "Content-Type": "application/octet-stream",
            "X-Floorplan-Metadata": quote(json.dumps(opts)),
        },
    )


def ready(client, db, path, headers, floor, name="synthetic-ground.png", page=1):
    result = upload(client, path, headers, options(floor, name, page))
    assert result.status_code == 201, result.text
    job = db.get(FloorplanJob, UUID(result.json()["id"]))
    service.process_owned(db, job)
    return job


def apply(client, path, headers, job, replace=None, reset=False):
    return client.post(
        path + f"/floorplan-jobs/{job.id}/apply",
        json={"replace_layer_id": replace, "reset_calibration": reset},
        headers=version(headers, current(client, path)),
    )


def test_floor_basement_ground_stable_metadata_references_and_versions(
    client, db, bundle, identity
):
    headers = sign_in(client, identity)
    draft, path, floor = create(client, bundle, headers)
    payload = floor_payload(bundle, "B1")
    payload["id"] = str(uuid4())
    created = client.post(path + "/floors", json=payload, headers=version(headers, 2))
    assert created.status_code == 201
    data = client.get(path + "/floors").json()
    assert [f["ordering"] for f in data["floors"]] == [-1, 0]
    assert data["floors"][0]["id"] == payload["id"] and data["floors"][0]["elevation_m"] is None
    stale = client.put(
        path + "/floors/" + floor,
        json={**floor_payload(bundle), "label": "Keep this unsaved label"},
        headers=version(headers, 2),
    )
    assert stale.status_code == 409
    edited = client.put(
        path + "/floors/" + floor,
        json={**floor_payload(bundle), "label": "Synthetic ground zero", "elevation_m": 0},
        headers=version(headers, 3),
    )
    assert edited.status_code == 200
    assert (
        client.post(
            path + "/floors", json=floor_payload(bundle), headers=version(headers, 4)
        ).status_code
        == 409
    )
    assert (
        client.post(
            path + "/floors",
            json={**floor_payload(bundle, "BAD"), "building_id": str(uuid4())},
            headers=version(headers, 4),
        ).status_code
        == 404
    )
    assert (
        client.put(
            path + "/floors/" + floor,
            json=floor_payload(bundle),
            headers={"Origin": "http://testserver", "If-Match": '"4"'},
        ).status_code
        == 403
    )
    active = client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()
    assert active["dataset_revision_id"] != draft["id"]
    assert db.get(Revision, UUID(draft["id"])).status == "draft"


@pytest.mark.parametrize(
    "role,read,write",
    [
        ("editor", 200, 201),
        ("reviewer_publisher", 200, 403),
        ("operations", 403, 403),
        ("system_admin", 200, 201),
    ],
)
def test_floor_roles_enforced_server_side(client, db, bundle, identity, role, read, write):
    owner_headers = sign_in(client, identity)
    draft = make_draft(client, bundle, owner_headers)
    path = base(bundle, draft)
    password = secrets.token_urlsafe(24)
    user = User(
        username="floor-role", display_name="Floor role", password_hash=HASHER.hash(password)
    )
    db.add(user)
    db.flush()
    db.add(RoleAssignment(user_id=user.id, campus_id=bundle.campus.id, role=role))
    db.flush()
    headers = sign_in(client, (user, password))
    assert client.get(path + "/floors").status_code == read
    assert (
        client.post(
            path + "/floors", json=floor_payload(bundle), headers=version(headers, 1)
        ).status_code
        == write
    )


def test_private_jobs_campus_revision_isolation_and_invalid_files(client, db, bundle, identity):
    headers = sign_in(client, identity)
    draft, path, floor = create(client, bundle, headers)
    job = ready(client, db, path, headers, floor)
    url = path + f"/floorplan-jobs/{job.id}"
    original = client.get(url + "/original")
    assert original.content == (FIXTURES / "synthetic-ground.png").read_bytes()
    assert original.headers["cache-control"] == "no-store"
    assert client.get(url + "/preview").headers["content-type"] == "image/png"
    assert client.get(path + f"/floorplan-jobs/{uuid4()}/original").status_code == 404
    other = make_draft(client, bundle, headers)
    assert client.get(base(bundle, other) + f"/floorplan-jobs/{job.id}/original").status_code == 404
    assert (
        client.get(url.replace(str(bundle.campus.id), str(uuid4())) + "/original").status_code
        == 403
    )
    assert upload(client, path, headers, options(floor), b"<svg/>").status_code == 422
    assert (
        upload(client, path, headers, options(floor), b"x" * (10 * 1024**2 + 1)).status_code == 413
    )
    client.cookies.clear()
    assert (
        client.get(url + "/original").status_code == 401
        and client.get(url + "/preview").status_code == 401
    )
    assert client.get("/storage/derived/plan.png").status_code == 404


def test_staging_keys_cancel_retry_and_no_implicit_apply(client, db, bundle, identity):
    headers = sign_in(client, identity)
    draft, path, floor = create(client, bundle, headers)
    opts = options(floor)
    a = upload(client, path, headers, opts)
    b = upload(client, path, headers, opts)
    assert a.status_code == 201 and a.json()["id"] == b.json()["id"]
    assert upload(client, path, headers, {**opts, "page": 2}).status_code == 409
    job = db.get(FloorplanJob, UUID(a.json()["id"]))
    assert db.get(Floor, (UUID(draft["id"]), UUID(floor))).layer_id is None
    assert current(client, path) == 2
    # Malformed contents with a correct signature are rejected by actual decoding.
    bad = upload(client, path, headers, options(floor, "bad.pdf"), b"%PDF-broken")
    assert bad.status_code == 201
    bad_job = db.get(FloorplanJob, UUID(bad.json()["id"]))
    with pytest.raises(ValueError):
        service.process_owned(db, bad_job)
    bad_job.state = "failed"
    bad_job.attempts = 1
    db.flush()
    assert (
        client.post(
            path + f"/floorplan-jobs/{bad_job.id}/control/retry", headers=version(headers, 2)
        ).status_code
        == 200
    )
    assert (
        client.post(
            path + f"/floorplan-jobs/{job.id}/control/cancel", headers=version(headers, 2)
        ).json()["state"]
        == "cancelled"
    )
    assert apply(client, path, headers, job).status_code == 409
    bad_job.state = "failed"
    bad_job.attempts = 3
    db.flush()
    assert (
        client.post(
            path + f"/floorplan-jobs/{bad_job.id}/control/retry", headers=version(headers, 2)
        ).status_code
        == 409
    )


def test_apply_calibrate_independent_projection_publish_rollback_and_clone(
    client, db, bundle, identity, reviewer
):
    owner = sign_in(client, identity)
    draft, path, floor = create(client, bundle, owner)
    old_release = client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()["id"]
    job = ready(client, db, path, owner, floor, "synthetic-two-pages.pdf", 2)
    response = apply(client, path, owner, job)
    assert response.status_code == 200, response.text
    layer_id = response.json()["layer_id"]
    floor_data = client.get(path + "/floors").json()["floors"][0]
    source = floor_data["layer"]["source_id"]
    assert floor_data["frame"]["metres_per_pixel"] is None
    assert (
        client.post(
            path + f"/sources/{source}/approve", headers=version(owner, current(client, path))
        ).status_code
        == 403
    )
    calibrated = client.post(
        path + f"/floors/{floor}/calibration",
        json=measure(),
        headers=version(owner, current(client, path)),
    )
    assert calibrated.status_code == 200, calibrated.text
    assert (
        client.post(
            path + f"/floors/{floor}/calibration/approve",
            headers=version(owner, current(client, path)),
        ).status_code
        == 403
    )
    reviewer_headers = sign_in(client, reviewer)
    assert (
        client.post(
            path + f"/sources/{source}/approve",
            headers=version(reviewer_headers, current(client, path)),
        ).status_code
        == 200
    )
    calibration_password = secrets.token_urlsafe(24)
    calibration_reviewer = User(
        username="calibration-reviewer",
        display_name="Independent calibration reviewer",
        password_hash=HASHER.hash(calibration_password),
    )
    db.add(calibration_reviewer)
    db.flush()
    db.add(
        RoleAssignment(
            user_id=calibration_reviewer.id, campus_id=bundle.campus.id, role="reviewer_publisher"
        )
    )
    db.flush()
    calibration_headers = sign_in(client, (calibration_reviewer, calibration_password))
    assert (
        client.post(
            path + f"/floors/{floor}/calibration/approve",
            headers=version(calibration_headers, current(client, path)),
        ).status_code
        == 200
    )
    owner = sign_in(client, identity)
    validated = client.post(
        path + "/validations",
        json=expectations(bundle),
        headers=version(owner, current(client, path)),
    )
    assert validated.status_code == 200, validated.text
    run = validated.json()
    assert run["report"]["errors"] == 0, run
    assert any(d["code"] == "indoor_display_only" for d in run["report"]["diagnostics"])
    submitted = client.post(
        path + "/submissions",
        json={"validation_id": run["id"], "acknowledgements": ack(run)},
        headers=version(owner, current(client, path)),
    )
    assert submitted.status_code == 200, submitted.text
    assert (
        client.post(
            path + "/floors",
            json=floor_payload(bundle, "B1"),
            headers=version(owner, current(client, path)),
        ).status_code
        == 409
    )
    reviewer_headers = sign_in(client, reviewer)
    v = current(client, path)
    decision = client.post(
        path + f"/submissions/{submitted.json()['id']}/decision",
        json={
            "decision": "approve",
            "notes": "Independent review of sanitized floor and uniform measurements; outdoor-only navigation.",
            "acknowledgements": ack(run),
        },
        headers=version(reviewer_headers, v),
    )
    assert decision.status_code == 200, decision.text
    # Revoke only the measurement reviewer, keeping source and overall approval live.
    db.execute(
        delete(RoleAssignment).where(
            RoleAssignment.user_id == calibration_reviewer.id,
            RoleAssignment.campus_id == bundle.campus.id,
        )
    )
    db.flush()
    refused = client.post(
        path + "/publish",
        json={
            "submission_id": submitted.json()["id"],
            "expected_release_id": old_release,
            "key": str(uuid4()),
        },
        headers=version(reviewer_headers, current(client, path)),
    )
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "approval_revoked"
    assert client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()["id"] == old_release
    db.add(
        RoleAssignment(
            user_id=calibration_reviewer.id, campus_id=bundle.campus.id, role="reviewer_publisher"
        )
    )
    db.flush()
    published = client.post(
        path + "/publish",
        json={
            "submission_id": submitted.json()["id"],
            "expected_release_id": old_release,
            "key": str(uuid4()),
        },
        headers=version(reviewer_headers, current(client, path)),
    )
    assert published.status_code == 200, published.text
    release = client.get(f"/api/v1/campuses/{bundle.campus.id}/release").json()
    artifact = client.get(release["artifact_url"]).json()
    descriptor = artifact["floorplans"][layer_id]
    assert artifact["floors"][floor]["metric_navigation"] is False
    assert artifact["frames"][floor_data["frame_id"]]["metres_per_pixel"] == 0.05
    encoded = json.dumps(artifact)
    assert (
        "PRIVATE-PLAN-NOTES" not in encoded
        and "measured_by" not in encoded
        and "redactions" not in encoded
        and "synthetic-two-pages.pdf" not in encoded
    )
    asset_url = f"/api/v1/campuses/{bundle.campus.id}/releases/{release['id']}/floorplans/{layer_id}/{descriptor['checksum']}.png"
    image = client.get(asset_url)
    assert (
        image.status_code == 200
        and hashlib.sha256(image.content).hexdigest() == descriptor["checksum"]
    )
    assert "immutable" in image.headers["cache-control"]
    assert client.get(asset_url.replace(descriptor["checksum"], "0" * 64)).status_code == 404
    owner = sign_in(client, identity)
    cloned = make_draft(client, bundle, owner)
    copied = client.get(base(bundle, cloned) + "/floors").json()["floors"][0]
    assert (
        copied["id"] == floor
        and copied["layer_id"] == layer_id
        and copied["frame"]["calibration"]["reviewer"] == str(calibration_reviewer.id)
    )
    assert (
        client.put(
            path + "/floors/" + floor,
            json=floor_payload(bundle),
            headers=version(owner, current(client, path)),
        ).status_code
        == 409
    )
    reviewer_headers = sign_in(client, reviewer)
    rollback = client.post(
        f"/api/v1/admin/campuses/{bundle.campus.id}/rollback",
        json={
            "target_release_id": old_release,
            "expected_release_id": release["id"],
            "key": str(uuid4()),
            "reason": "Restore original outdoor release after isolated floorplan test.",
        },
        headers=reviewer_headers,
    )
    assert rollback.status_code == 200, rollback.text
    assert client.get(asset_url).content == image.content
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(
            text("UPDATE floorplan_layers SET png = :png WHERE dataset_revision_id = :rev"),
            {"png": b"corrupt", "rev": draft["id"]},
        )
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(
            text("UPDATE floorplan_jobs SET original = :raw WHERE id = :id"),
            {"raw": b"bad", "id": job.id},
        )


def test_replacement_deletion_dependency_confirmation_and_calibration_reset(
    client, db, bundle, identity, reviewer
):
    headers = sign_in(client, identity)
    draft, path, floor = create(client, bundle, headers)
    first = ready(client, db, path, headers, floor)
    r = apply(client, path, headers, first)
    assert r.status_code == 200
    original_layer = r.json()["layer_id"]
    assert (
        client.post(
            path + f"/floors/{floor}/calibration",
            json=measure(),
            headers=version(headers, current(client, path)),
        ).status_code
        == 200
    )
    second = ready(client, db, path, headers, floor, "synthetic-two-pages.pdf", 2)
    assert apply(client, path, headers, second).status_code == 409
    assert apply(client, path, headers, second, original_layer).status_code == 409
    frame = client.get(path + "/floors").json()["floors"][0]["frame_id"]
    node = Node(
        id=uuid4(),
        dataset_revision_id=UUID(draft["id"]),
        campus_id=bundle.campus.id,
        frame_id=UUID(frame),
        label="Future dependency fixture only",
        visibility="restricted",
        point=None,
        x_px=10,
        y_px=10,
    )
    db.add(node)
    db.flush()
    assert apply(client, path, headers, second, original_layer, True).status_code == 409
    db.delete(node)
    db.flush()
    assert apply(client, path, headers, second, original_layer, True).status_code == 200
    data = client.get(path + "/floors").json()["floors"][0]
    assert data["frame"]["calibration"] is None and data["frame"]["metres_per_pixel"] is None
    assert len(data["dependencies"]["layer_ids"]) == 2
    # Only the current selected derivative needs approval. Retained unapproved
    # originals/layers must neither block the release nor appear in its projection.
    review_headers = sign_in(client, reviewer)
    assert (
        client.post(
            path + f"/sources/{data['layer']['source_id']}/approve",
            headers=version(review_headers, current(client, path)),
        ).status_code
        == 200
    )
    headers = sign_in(client, identity)
    run = client.post(
        path + "/validations",
        json=expectations(bundle),
        headers=version(headers, current(client, path)),
    ).json()
    assert run["report"]["errors"] == 0, run
    from app.services.publication import public_projection, snapshot

    projection = public_projection(snapshot(db, db.get(Revision, UUID(draft["id"]))))
    assert list(projection["floorplans"]) == [data["layer"]["id"]]
    assert original_layer not in projection["floorplans"]
    assert (
        client.request(
            "DELETE",
            path + "/floors/" + floor,
            json={"remove_layer_ids": []},
            headers=version(headers, current(client, path)),
        ).status_code
        == 409
    )
    removed = client.request(
        "DELETE",
        path + "/floors/" + floor,
        json={"remove_layer_ids": data["dependencies"]["layer_ids"]},
        headers=version(headers, current(client, path)),
    )
    assert removed.status_code == 200, removed.text
    assert (
        client.get(path + "/floors").json()["floors"] == []
        and db.get(FloorplanJob, first.id).state == "applied"
    )


def test_stale_apply_retry_and_failed_write_preserve_every_record(
    client, db, bundle, identity, monkeypatch
):
    headers = sign_in(client, identity)
    draft, path, floor = create(client, bundle, headers)
    job = ready(client, db, path, headers, floor)
    start = current(client, path)
    audits = db.scalar(select(func.count()).select_from(AuditEvent))

    def fail(*args, **kwargs):
        raise DomainError("injected_failure", "Injected late audit failure.", 422)

    with monkeypatch.context() as patch:
        patch.setattr(service, "audit", fail)
        result = apply(client, path, headers, job)
        assert result.status_code == 422
    db.expire_all()
    assert current(client, path) == start and db.get(FloorplanJob, job.id).state == "ready"
    assert (
        db.scalar(select(func.count()).select_from(MapLayer)) == 0
        and db.scalar(select(func.count()).select_from(SourceAsset)) == 0
    )
    assert db.scalar(select(func.count()).select_from(AuditEvent)) == audits
    response = apply(client, path, headers, job)
    assert response.status_code == 200
    assert (
        client.post(
            path + f"/floorplan-jobs/{job.id}/apply",
            json={"replace_layer_id": None, "reset_calibration": False},
            headers=version(headers, start),
        ).status_code
        == 409
    )
    assert apply(client, path, headers, job).json()["retry"] is True
    assert apply(client, path, headers, job, None, True).status_code == 409
    counts = (current(client, path), db.scalar(select(func.count()).select_from(MapLayer)))
    assert counts == (start + 1, 1)
    bad = measure()
    bad["checks"][0]["distance_m"] = 40
    assert (
        client.post(
            path + f"/floors/{floor}/calibration",
            json=bad,
            headers=version(headers, current(client, path)),
        ).status_code
        == 422
    )
    assert current(client, path) == counts[0]


def test_uncalibrated_display_only_warning_and_restricted_derivative_exclusion(
    client, db, bundle, identity, reviewer
):
    owner = sign_in(client, identity)
    draft, path, floor = create(client, bundle, owner)
    job = ready(client, db, path, owner, floor)
    assert apply(client, path, owner, job).status_code == 200
    data = client.get(path + "/floors").json()["floors"][0]
    source = data["layer"]["source_id"]
    missing = client.post(
        path + "/validations",
        json=expectations(bundle),
        headers=version(owner, current(client, path)),
    ).json()
    assert missing["report"]["errors"] > 0
    reviewer_headers = sign_in(client, reviewer)
    assert (
        client.post(
            path + f"/sources/{source}/approve",
            headers=version(reviewer_headers, current(client, path)),
        ).status_code
        == 200
    )
    owner = sign_in(client, identity)
    run = client.post(
        path + "/validations",
        json=expectations(bundle),
        headers=version(owner, current(client, path)),
    ).json()
    assert run["report"]["errors"] == 0, run
    assert any(d["code"] == "uncalibrated_floor" for d in run["report"]["diagnostics"])
    from app.services.publication import public_projection, snapshot

    projection = public_projection(snapshot(db, db.get(Revision, UUID(draft["id"]))))
    assert projection["frames"][data["frame_id"]]["metres_per_pixel"] is None
    assert (
        client.put(
            path + "/floors/" + floor,
            json={**floor_payload(bundle), "visibility": "restricted"},
            headers=version(owner, current(client, path)),
        ).status_code
        == 200
    )
    projection = public_projection(snapshot(db, db.get(Revision, UUID(draft["id"]))))
    assert projection["floors"] == {} and projection["floorplans"] == {}


def test_source_quota_and_referenced_original_removal_are_explicit(
    client, db, bundle, identity, monkeypatch
):
    headers = sign_in(client, identity)
    draft, path, floor = create(client, bundle, headers)
    with monkeypatch.context() as patch:
        patch.setattr(service, "STORAGE_LIMIT", 1)
        assert upload(client, path, headers, options(floor)).status_code == 413
    job = ready(client, db, path, headers, floor)
    assert apply(client, path, headers, job).status_code == 200
    source = client.get(path + "/floors").json()["floors"][0]["layer"]["source_id"]
    assert (
        client.delete(
            path + f"/sources/{source}", headers=version(headers, current(client, path))
        ).status_code
        == 409
    )
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(text("DELETE FROM floorplan_jobs WHERE id = :id"), {"id": job.id})
