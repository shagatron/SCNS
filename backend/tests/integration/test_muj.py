"""Pinned real OSM preparation through ordinary protected draft imports, no real release."""

import json
import secrets
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.cli.admin import bootstrap
from app.models import ActiveRelease, Campus, Edge, Revision
from app.models.admin import AuditEvent, RoleAssignment
from app.models.imports import ImportJob
from app.models.publication import SourceAsset
from app.services.imports import stable_id
from app.services.muj_setup import CAMPUS_ID, ROOT, prepared
from tests.integration.test_admin import sign_in, version
from tests.integration.test_imports import apply, preview, upload


@pytest.fixture
def identity(db, bundle, seeded):
    password = secrets.token_urlsafe(24)
    return bootstrap(db, "owner", "Test owner", password, bundle.campus.id), password


pytestmark = pytest.mark.integration


def provision(client, bundle, headers):
    response = client.post(f"/api/v1/admin/campuses/{bundle.campus.id}/muj-setup", headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_provision_authorization_csrf_idempotency_and_no_public_data(client, db, bundle, identity):
    url = f"/api/v1/admin/campuses/{bundle.campus.id}/muj-setup"
    assert client.post(url).status_code == 401
    headers = sign_in(client, identity)
    assert client.post(url, headers={"Origin": headers["Origin"]}).status_code == 403
    role = db.get(RoleAssignment, (identity[0].id, bundle.campus.id, "system_admin"))
    db.delete(role)
    db.add(RoleAssignment(user_id=identity[0].id, campus_id=bundle.campus.id, role="editor"))
    db.flush()
    assert client.post(url, headers=headers).status_code == 403
    db.add(RoleAssignment(user_id=identity[0].id, campus_id=bundle.campus.id, role="system_admin"))
    db.flush()
    before = list(db.scalars(select(ActiveRelease.release_id)))
    result = provision(client, bundle, headers)
    retry = provision(client, bundle, headers)
    assert retry["draft_id"] == result["draft_id"] and not retry["created"]
    campus = db.get(Campus, CAMPUS_ID)
    assert not campus.is_demo and campus.timezone == "Asia/Kolkata"
    assert (
        db.scalar(select(func.count()).select_from(Revision).where(Revision.campus_id == CAMPUS_ID))
        == 1
    )
    assert list(db.scalars(select(ActiveRelease.release_id))) == before
    assert all(c["id"] != str(CAMPUS_ID) for c in client.get("/api/v1/campuses").json())
    source = db.scalar(select(SourceAsset).where(SourceAsset.campus_id == CAMPUS_ID))
    assert source.approved_by is None and "OpenStreetMap" in source.attribution
    assert (
        db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "campus.muj_provision")
        )
        == 1
    )
    # Knowing a foreign source-campus UUID never provides provisioning access.
    assert (
        client.post(f"/api/v1/admin/campuses/{uuid4()}/muj-setup", headers=headers).status_code
        == 403
    )


def import_all(client, db, bundle, identity):
    headers = sign_in(client, identity)
    result = provision(client, bundle, headers)
    draft = {"id": result["draft_id"]}
    muj = SimpleNamespace(campus=SimpleNamespace(id=CAMPUS_ID, code="MUJ", timezone="Asia/Kolkata"))
    for path in sorted(ROOT.glob("batch-*.json")):
        response = upload(
            client,
            muj,
            draft,
            headers,
            raw=path.read_bytes(),
            key=path.stem + "-test",
            provenance="Pinned owner-supplied OSM preparation; no field survey",
            source_rights="OpenStreetMap ODbL",
        )
        job = preview(db, response)
        assert job.preview["counts"]["invalid"] == 0, [
            (r["external_id"], r["errors"]) for r in job.preview["rows"] if r["errors"]
        ][:10]
        assert job.preview["counts"]["conflict"] == 0
        apply(client, muj, draft, headers, job)
    return headers, result, muj, draft


def test_real_batches_replay_connectivity_lengths_stale_write_and_public_isolation(
    client, db, bundle, identity, tmp_path, monkeypatch
):
    from app.core.config import get_settings

    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    headers, result, muj, draft = import_all(client, db, bundle, identity)
    revision = db.get(Revision, UUID(draft["id"]))
    count = db.scalar(
        select(func.count()).select_from(Edge).where(Edge.dataset_revision_id == revision.id)
    )
    assert count == json.loads((ROOT / "report.json").read_bytes())["included_counts"]["edges"]
    job = db.scalar(
        select(ImportJob).where(ImportJob.campus_id == CAMPUS_ID).order_by(ImportJob.created_at)
    )
    # Exact job replay doesn't increment version; new import key simulates interruption/retry.
    v = revision.edit_version
    repeated = client.post(
        f"/api/v1/admin/campuses/{CAMPUS_ID}/imports/{job.id}/apply", headers=version(headers, 1)
    )
    assert repeated.status_code == 200 and revision.edit_version == v
    path = ROOT / "batch-001.json"
    fresh = preview(
        db, upload(client, muj, draft, headers, raw=path.read_bytes(), key="new-replay-test")
    )
    assert fresh.preview["counts"]["unchanged"] == len(json.loads(path.read_bytes())["records"])
    base = f"/api/v1/admin/campuses/{CAMPUS_ID}/drafts/{revision.id}/graph"
    quality = client.get(base + "/validation").json()
    assert quality["errors"] == 0, quality
    start = stable_id(CAMPUS_ID, "places", "osm-node-10780185181")
    target = stable_id(CAMPUS_ID, "places", "osm-node-11573265515")
    route = client.get(base + "/route-test", params={"source": str(start), "target": str(target)})
    assert route.status_code == 200, route.text
    assert route.json()["distance_m"] > 0 and route.json()["edge_ids"]
    # A real concurrent edit invalidates the prepared preview (and its validation).
    revision.edit_version += 1
    db.flush()
    response = client.post(
        f"/api/v1/admin/campuses/{CAMPUS_ID}/imports/{fresh.id}/validate", headers=headers
    )
    assert response.status_code == 409
    assert (
        db.scalar(
            select(func.count()).select_from(Edge).where(Edge.dataset_revision_id == revision.id)
        )
        == count
    )
    assert client.get(f"/api/v1/campuses/{CAMPUS_ID}/release").status_code == 404
    print(
        "OSM software route",
        route.json()["distance_m"],
        "m",
        len(route.json()["edge_ids"]),
        "stored edges",
    )


def test_provision_transaction_rolls_back_and_pinned_files_are_valid(
    client, db, bundle, identity, monkeypatch
):
    import app.services.muj_setup as service

    manifest, config = prepared()
    assert (
        manifest["source_sha256"]
        == "d4b902b01fe944acb3161026679dabbab4898d6952bee22d7019f15fd15748de"
    )
    assert config["code"] == "MUJ"
    headers = sign_in(client, identity)

    def fail(*args, **kwargs):
        raise ValueError("Injected late source failure")

    monkeypatch.setattr(service, "add_source", fail)
    with pytest.raises(ValueError, match="Injected"):
        client.post(f"/api/v1/admin/campuses/{bundle.campus.id}/muj-setup", headers=headers)
    assert db.get(Campus, CAMPUS_ID) is None
    assert db.scalar(select(Revision.id).where(Revision.campus_id == CAMPUS_ID)) is None
    assert (
        db.scalar(select(RoleAssignment.user_id).where(RoleAssignment.campus_id == CAMPUS_ID))
        is None
    )


@pytest.mark.parametrize("role", ["editor", "reviewer_publisher", "operations"])
def test_only_existing_system_admin_can_create_a_campus(client, db, bundle, identity, role):
    headers = sign_in(client, identity)
    db.delete(db.get(RoleAssignment, (identity[0].id, bundle.campus.id, "system_admin")))
    db.add(RoleAssignment(user_id=identity[0].id, campus_id=bundle.campus.id, role=role))
    db.flush()
    response = client.post(f"/api/v1/admin/campuses/{bundle.campus.id}/muj-setup", headers=headers)
    assert response.status_code == 403
    assert db.get(Campus, CAMPUS_ID) is None


def test_changed_preparation_and_unrelated_admin_never_adopt_existing_muj(
    client, db, bundle, identity, monkeypatch
):
    import app.services.muj_setup as service
    from app.models.admin import User
    from app.services.admin_auth import HASHER

    headers = sign_in(client, identity)
    result = provision(client, bundle, headers)
    manifest, config = prepared()
    manifest["converter"] = "changed-preparation"
    monkeypatch.setattr(service, "prepared", lambda: (manifest, config))
    assert (
        client.post(
            f"/api/v1/admin/campuses/{bundle.campus.id}/muj-setup", headers=headers
        ).status_code
        == 409
    )
    monkeypatch.setattr(service, "prepared", prepared)
    password = secrets.token_urlsafe(24)
    outsider = User(
        username="another-admin",
        display_name="Isolated other administrator",
        password_hash=HASHER.hash(password),
    )
    db.add(outsider)
    db.flush()
    db.add(RoleAssignment(user_id=outsider.id, campus_id=bundle.campus.id, role="system_admin"))
    db.flush()
    h = sign_in(client, (outsider, password))
    assert (
        client.post(f"/api/v1/admin/campuses/{bundle.campus.id}/muj-setup", headers=h).status_code
        == 403
    )
    assert (
        str(db.scalar(select(Revision.id).where(Revision.campus_id == CAMPUS_ID)))
        == result["draft_id"]
    )
