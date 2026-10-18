"""Real PostGIS staged import contract: security, atomicity and public isolation."""

import base64
import json
import secrets
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.cli.admin import bootstrap
from app.core.config import get_settings
from app.core.portable import is_private_file
from app.models import Edge, Place, Revision
from app.models.admin import AuditEvent, Department, RoleAssignment
from app.models.imports import ImportBinding, ImportJob
from app.services.imports import private_path, process_job
from tests.integration.test_admin import make_draft, sign_in, version
from tests.integration.test_api import body

pytestmark = pytest.mark.integration


@pytest.fixture
def identity(db, bundle, seeded, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    password = secrets.token_urlsafe(24)
    return bootstrap(db, "owner", "Test owner", password, bundle.campus.id), password


def options(bundle, **overrides):
    return {
        "format": "json",
        "campus_code": bundle.campus.code,
        "timezone": bundle.campus.timezone,
        "source_rights": "Synthetic testing only",
        "provenance": "Synthetic fixture; not surveyed",
        **overrides,
    }


def payload(bundle, records):
    return json.dumps(
        {
            "schema_version": "import-v1",
            "units": "WGS84_degrees_and_metres",
            "campus_code": bundle.campus.code,
            "timezone": bundle.campus.timezone,
            "records": records,
        }
    ).encode()


def paths(bundle, draft):
    campus = f"/api/v1/admin/campuses/{bundle.campus.id}"
    return campus + f"/drafts/{draft['id']}/imports", campus + "/imports"


def upload(client, bundle, draft, headers, records=None, raw=None, key=None, **overrides):
    opts = options(bundle, **overrides)
    return client.post(
        paths(bundle, draft)[0],
        params={"filename": "synthetic." + opts["format"]},
        content=raw if raw is not None else payload(bundle, records),
        headers={
            **headers,
            "Content-Type": "application/octet-stream",
            "Idempotency-Key": key or str(uuid4()),
            "X-Import-Options": base64.b64encode(json.dumps(opts).encode()).decode(),
        },
    )


def preview(db, response):
    assert response.status_code == 201, response.text
    job = db.get(ImportJob, UUID(response.json()["id"]))
    job.attempts += 1
    process_job(db, job)
    db.flush()
    return job


def department(external="dept-A", name="Imported department"):
    return {
        "entity": "departments",
        "external_id": external,
        "data": {"code": "IMP_A", "name": name},
    }


def apply(client, bundle, draft, headers, job):
    path = paths(bundle, draft)[1] + f"/{job.id}"
    valid = client.post(path + "/validate", headers=headers)
    assert valid.status_code == 200, valid.text
    response = client.post(path + "/apply", headers=version(headers, job.preview_version))
    assert response.status_code == 200, response.text
    return path


def test_bundle_preview_apply_audit_idempotency_and_public_isolation(client, db, bundle, identity):
    headers = sign_in(client, identity)
    draft = make_draft(client, bundle, headers)
    before_route = client.post("/api/v1/routes", json=body(bundle)).json()
    before_map = client.get(
        f"/api/v1/campuses/{bundle.campus.id}/map?bbox=-.001,-.001,.004,.004"
    ).json()
    records = [
        department(),
        {
            "entity": "places",
            "external_id": "private-new",
            "data": {
                "code": "IMP_P",
                "name": "Imported candidate",
                "kind": "help",
                "point": {"type": "Point", "coordinates": [0.001, 0.001]},
            },
        },
        {
            "entity": "department_places",
            "external_id": "link-A",
            "data": {"department_id": "dept-A", "place_id": "private-new"},
        },
    ]
    key = str(uuid4())
    response = upload(client, bundle, draft, headers, records, key=key)
    repeated = upload(client, bundle, draft, headers, records, key=key)
    assert response.json()["id"] == repeated.json()["id"]
    assert (
        upload(client, bundle, draft, headers, [department(name="Different")], key=key).status_code
        == 409
    )
    job = preview(db, response)
    assert job.state == "preview_ready" and job.preview["counts"]["add"] == 3
    assert (
        db.scalar(select(Department.id).where(Department.dataset_revision_id == draft["id"]))
        is None
    )
    assert private_path(job).is_file() and is_private_file(private_path(job))
    path = apply(client, bundle, draft, headers, job)
    assert client.post(path + "/apply", headers=version(headers, 1)).status_code == 200
    assert db.get(Revision, UUID(draft["id"])).edit_version == 2
    assert (
        db.scalar(
            select(func.count())
            .select_from(ImportBinding)
            .where(ImportBinding.dataset_revision_id == draft["id"])
        )
        == 3
    )
    assert (
        db.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "import.apply")
        )
        == 1
    )
    assert job.applier_id == identity[0].id
    after_route = client.post("/api/v1/routes", json=body(bundle)).json()
    for key in ("id", "generated_at", "departure_at", "valid_until", "restriction_window_end"):
        before_route.pop(key)
        after_route.pop(key)
    assert after_route == before_route
    assert (
        client.get(f"/api/v1/campuses/{bundle.campus.id}/map?bbox=-.001,-.001,.004,.004").json()
        == before_map
    )
    assert client.get(f"/api/v1/campuses/{bundle.campus.id}/search?q=Imported").json()["total"] == 0
    again = preview(db, upload(client, bundle, draft, headers, records))
    assert again.preview["counts"]["unchanged"] == 3
    apply(client, bundle, draft, headers, again)
    assert (
        db.scalar(
            select(func.count())
            .select_from(Department)
            .where(Department.dataset_revision_id == draft["id"])
        )
        == 1
    )


def test_conflicts_adoption_explicit_upsert_and_stale_preview(client, db, bundle, identity):
    headers = sign_in(client, identity)
    draft = make_draft(client, bundle, headers)
    place = next(p for p in bundle.places if p.code == "LIB")
    record = {
        "entity": "places",
        "external_id": "official-library",
        "data": {
            "code": place.code,
            "name": "Candidate name",
            "kind": place.kind,
            "description": place.description,
            "point": place.point.model_dump(mode="json"),
            "building_id": str(place.building_id),
        },
    }
    duplicate = preview(db, upload(client, bundle, draft, headers, [record]))
    assert duplicate.preview["counts"]["conflict"] == 1
    record["existing_id"] = str(place.id)
    conflict = preview(db, upload(client, bundle, draft, headers, [record]))
    assert conflict.preview["counts"]["conflict"] == 1
    job = preview(db, upload(client, bundle, draft, headers, [record], policy="upsert"))
    assert job.preview["counts"]["update"] == 1
    path = paths(bundle, draft)[1] + f"/{job.id}"
    assert client.post(path + "/validate", headers=headers).status_code == 200
    other = preview(db, upload(client, bundle, draft, headers, [department()]))
    apply(client, bundle, draft, headers, other)
    assert client.post(path + "/apply", headers=version(headers, 1)).status_code == 409
    assert db.get(Place, (UUID(draft["id"]), place.id)).name == place.name
    assert client.post(path + "/refresh", headers=headers).status_code == 200
    process_job(db, job)
    apply(client, bundle, draft, headers, job)
    assert db.get(Place, (UUID(draft["id"]), place.id)).name == "Candidate name"


@pytest.mark.parametrize(
    "role,read,write",
    [
        ("editor", 200, 201),
        ("reviewer_publisher", 200, 403),
        ("operations", 403, 403),
        ("system_admin", 200, 201),
    ],
)
def test_permissions_csrf_and_campus_isolation(client, db, bundle, identity, role, read, write):
    headers = sign_in(client, identity)
    draft = make_draft(client, bundle, headers)
    job = preview(db, upload(client, bundle, draft, headers, [department()]))
    assignment = db.get(RoleAssignment, (identity[0].id, bundle.campus.id, "system_admin"))
    db.delete(assignment)
    db.add(RoleAssignment(user_id=identity[0].id, campus_id=bundle.campus.id, role=role))
    db.flush()
    path = paths(bundle, draft)[1]
    assert client.get(path).status_code == read
    assert upload(client, bundle, draft, headers, [department("other")]).status_code == write
    assert upload(client, bundle, draft, {}, [department()]).status_code == 403
    foreign = str(uuid4())
    assert client.get(path.replace(str(bundle.campus.id), foreign)).status_code == 403
    assert (
        client.get(
            path.replace(str(bundle.campus.id), foreign) + f"/{job.id}/errors.csv"
        ).status_code
        == 403
    )
    assert (
        client.post(
            path.replace(str(bundle.campus.id), foreign) + f"/{job.id}/apply", headers=headers
        ).status_code
        == 403
    )
    assert client.get(path + f"/{uuid4()}").status_code == (404 if read == 200 else 403)


def test_csv_mapping_invalid_rows_safe_report_and_mapping_reprocess(client, db, bundle, identity):
    headers = sign_in(client, identity)
    draft = make_draft(client, bundle, headers)
    raw = b"key,dept_code,title\na,CSV_A,CSV department\nb,CSV_A,Duplicate code\n"
    job = preview(
        db,
        upload(
            client,
            bundle,
            draft,
            headers,
            raw=raw,
            format="csv",
            entity="departments",
            mapping={"external_id": "key", "code": "dept_code", "name": "title"},
        ),
    )
    assert job.preview["counts"]["add"] == 1 and job.preview["counts"]["conflict"] == 1
    path = paths(bundle, draft)[1] + f"/{job.id}"
    assert client.post(path + "/validate", headers=headers).status_code == 422
    report = client.get(path + "/errors.csv")
    assert (
        "Duplicate code/link" in report.text
        and "attachment" in report.headers["content-disposition"]
    )
    assert (
        db.scalar(select(Department.id).where(Department.dataset_revision_id == draft["id"]))
        is None
    )
    changed = {
        **job.options,
        "mapping": {"external_id": "missing", "code": "dept_code", "name": "title"},
    }
    assert client.put(path + "/mapping", json=changed, headers=headers).status_code == 200
    process_job(db, job)
    assert all("missing" in i["errors"][0] for i in job.preview["rows"])


def test_geojson_and_related_outdoor_graph_full_polyline(client, db, bundle, identity):
    headers = sign_in(client, identity)
    draft = make_draft(client, bundle, headers)
    raw = json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "external_id": "geo-p",
                        "code": "GEO_P",
                        "name": "GeoJSON candidate",
                        "kind": "help",
                    },
                    "geometry": {"type": "Point", "coordinates": [0.001, 0.001]},
                }
            ],
        }
    ).encode()
    geo = preview(db, upload(client, bundle, draft, headers, raw=raw, format="geojson"))
    apply(client, bundle, draft, headers, geo)
    records = [
        {"entity": "frames", "external_id": "out", "data": {"code": "IMPORT_WGS84"}},
        {
            "entity": "nodes",
            "external_id": "n1",
            "data": {
                "frame_id": "out",
                "label": "Synthetic 1",
                "point": {"type": "Point", "coordinates": [0, 0]},
            },
        },
        {
            "entity": "nodes",
            "external_id": "n2",
            "data": {
                "frame_id": "out",
                "label": "Synthetic 2",
                "point": {"type": "Point", "coordinates": [0.001, 0]},
            },
        },
        {
            "entity": "edges",
            "external_id": "e1",
            "data": {
                "frame_id": "out",
                "from_node_id": "n1",
                "to_node_id": "n2",
                "physical_path_id": "path-1",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[0, 0], [0.0005, 0.001], [0.001, 0]],
                },
                "evidence": "Synthetic geometry; not field verified",
            },
        },
    ]
    job = preview(db, upload(client, bundle, draft, headers, records[::-1]))
    assert job.preview["counts"]["add"] == 4, job.preview
    apply(client, bundle, draft, headers, job)
    edge = db.get(
        Edge,
        (
            UUID(draft["id"]),
            UUID(next(i["id"] for i in job.preview["rows"] if i["entity"] == "edges")),
        ),
    )
    assert edge.distance_m > 200 and edge.distance_status == "estimated"
    same = preview(db, upload(client, bundle, draft, headers, records))
    assert same.preview["counts"]["unchanged"] == 4


@pytest.mark.parametrize(
    "change", ["duplicate", "mixed_campus", "unknown_node", "bad_geometry", "bad_frame"]
)
def test_row_errors_leave_no_partial_graph(client, db, bundle, identity, change):
    headers = sign_in(client, identity)
    draft = make_draft(client, bundle, headers)
    rows = [department()]
    if change == "duplicate":
        rows += [department()]
    elif change == "mixed_campus":
        rows[0]["data"]["campus_code"] = "FOREIGN"
    elif change == "bad_geometry":
        rows += [
            {
                "entity": "places",
                "external_id": "bad",
                "data": {
                    "code": "BAD",
                    "name": "Bad",
                    "kind": "help",
                    "point": {"type": "Point", "coordinates": [900, 0]},
                },
            }
        ]
    else:
        rows += (
            [
                {
                    "entity": "anchors",
                    "external_id": "bad",
                    "data": {"place_id": str(bundle.places[0].id), "node_id": str(uuid4())},
                }
            ]
            if change == "unknown_node"
            else [
                {
                    "entity": "nodes",
                    "external_id": "bad",
                    "data": {
                        "frame_id": str(uuid4()),
                        "label": "Bad",
                        "point": {"type": "Point", "coordinates": [0, 0]},
                    },
                }
            ]
        )
    job = preview(db, upload(client, bundle, draft, headers, rows))
    path = paths(bundle, draft)[1] + f"/{job.id}"
    assert job.preview["counts"]["invalid"] >= 1
    assert client.post(path + "/validate", headers=headers).status_code == 422
    assert client.post(path + "/apply", headers=version(headers, 1)).status_code == 409
    assert (
        db.scalar(select(Department.id).where(Department.dataset_revision_id == draft["id"]))
        is None
    )
    assert db.get(Revision, UUID(draft["id"])).edit_version == 1


def test_size_format_private_access_cancel_and_bounded_retry(
    client, db, bundle, identity, monkeypatch
):
    headers = sign_in(client, identity)
    draft = make_draft(client, bundle, headers)
    monkeypatch.setenv("IMPORT_BYTE_LIMIT", "1024")
    get_settings.cache_clear()
    assert upload(client, bundle, draft, headers, raw=b"x" * 1025).status_code == 413
    assert upload(client, bundle, draft, headers, raw=b"{broken").status_code == 422
    job = preview(db, upload(client, bundle, draft, headers, raw=b"{}"))
    assert job.state == "failed"
    path = paths(bundle, draft)[1] + f"/{job.id}"
    for _ in range(2):
        assert client.post(path + "/retry", headers=headers).status_code == 200
        job.attempts += 1
        process_job(db, job)
    assert client.post(path + "/retry", headers=headers).status_code == 409
    assert client.post(path + "/cancel", headers=headers).status_code == 200
    assert client.post(path + "/apply", headers=headers).status_code == 409
    assert client.get("/storage/private/imports/" + job.storage_key).status_code == 404
    assert client.get(
        "/api/v1/admin/campuses/" + str(bundle.campus.id) + "/imports/" + str(job.id) + "/source"
    ).status_code in (404, 405)


def test_apply_failure_rolls_back_entities_version_bindings_and_audit(
    client, db, bundle, identity, monkeypatch
):
    from app.services import imports

    headers = sign_in(client, identity)
    draft = make_draft(client, bundle, headers)
    rows = [
        department(),
        {
            "entity": "departments",
            "external_id": "dept-B",
            "data": {"code": "IMP_B", "name": "Second"},
        },
    ]
    job = preview(db, upload(client, bundle, draft, headers, rows))
    path = paths(bundle, draft)[1] + f"/{job.id}"
    assert client.post(path + "/validate", headers=headers).status_code == 200
    original = imports.write_item

    def fail_second(db, revision, item):
        if item["external_id"] == "dept-B":
            from app.core.errors import DomainError

            raise DomainError("import_validation_failed", "Injected second-row failure", 409)
        return original(db, revision, item)

    monkeypatch.setattr(imports, "write_item", fail_second)
    assert client.post(path + "/apply", headers=version(headers, 1)).status_code == 409
    assert (
        db.scalar(select(Department.id).where(Department.dataset_revision_id == draft["id"]))
        is None
    )
    assert (
        db.scalar(select(ImportBinding.id).where(ImportBinding.dataset_revision_id == draft["id"]))
        is None
    )
    assert db.scalar(select(Revision.edit_version).where(Revision.id == draft["id"])) == 1
    db.expire_all()
    assert (
        db.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "import.record")
        )
        == 0
    )
    assert job.state == "validated"


def test_all_executable_bundle_templates_and_unchanged_reimport(client, db, bundle, identity):
    from pathlib import Path

    headers = sign_in(client, identity)
    draft = make_draft(client, bundle, headers)
    root = Path(__file__).resolve().parents[3] / "data/templates/import-v1"
    job = preview(
        db, upload(client, bundle, draft, headers, raw=(root / "catalog-bundle.json").read_bytes())
    )
    assert job.preview["counts"]["add"] == 10, job.preview
    apply(client, bundle, draft, headers, job)
    again = preview(
        db, upload(client, bundle, draft, headers, raw=(root / "catalog-bundle.json").read_bytes())
    )
    assert again.preview["counts"]["unchanged"] == 10, again.preview
    base = f"/api/v1/admin/campuses/{bundle.campus.id}"
    for name in ("places.csv", "catalog-bundle.json", "places.geojson"):
        response = client.get(base + "/import-templates/" + name)
        assert response.status_code == 200 and response.content == (root / name).read_bytes()
    assert client.get(base + "/import-templates/secret.env").status_code == 404


def test_node_change_cannot_invalidate_existing_edges_or_public_anchors(
    client, db, bundle, identity
):
    headers = sign_in(client, identity)
    draft = make_draft(client, bundle, headers)
    node = bundle.nodes[0]
    row = {
        "entity": "nodes",
        "external_id": "adopt-node",
        "existing_id": str(node.id),
        "data": {
            "frame_id": str(node.frame_id),
            "label": node.label,
            "visibility": node.visibility,
            "point": {"type": "Point", "coordinates": [0.001, 0.001]},
        },
    }
    job = preview(db, upload(client, bundle, draft, headers, [row], policy="upsert"))
    assert job.preview["counts"]["invalid"] == 1
    assert any(
        "invalidate existing graph" in message for message in job.preview["rows"][0]["errors"]
    )
    assert (
        client.post(paths(bundle, draft)[1] + f"/{job.id}/validate", headers=headers).status_code
        == 422
    )


def test_geojson_crs_boundary_row_limit_metadata_and_storage_quota(
    client, db, bundle, identity, monkeypatch
):
    headers = sign_in(client, identity)
    draft = make_draft(client, bundle, headers)
    wrong_crs = preview(
        db,
        upload(
            client,
            bundle,
            draft,
            headers,
            raw=b'{"type":"FeatureCollection","crs":{},"features":[]}',
            format="geojson",
        ),
    )
    assert wrong_crs.state == "failed" and "WGS84" in wrong_crs.failure
    row = {
        "entity": "places",
        "external_id": "foreign-geometry",
        "data": {
            "code": "OUT",
            "name": "Wrong campus",
            "kind": "help",
            "point": {"type": "Point", "coordinates": [10, 10]},
        },
    }
    job = preview(db, upload(client, bundle, draft, headers, [row]))
    assert "outside the target campus" in job.preview["rows"][0]["errors"][0]
    assert (
        upload(client, bundle, draft, headers, [department()], campus_code="FOREIGN").status_code
        == 422
    )
    assert (
        upload(client, bundle, draft, headers, [department()], source_rights="   ").status_code
        == 422
    )
    monkeypatch.setenv("IMPORT_ROW_LIMIT", "1")
    get_settings.cache_clear()
    oversized = preview(db, upload(client, bundle, draft, headers, [department(), department("b")]))
    assert oversized.state == "failed" and "row limit" in oversized.failure
    monkeypatch.setenv("IMPORT_STORAGE_LIMIT", "1024")
    get_settings.cache_clear()
    assert (
        upload(
            client, bundle, draft, headers, raw=payload(bundle, [department()]) + b" " * 1024
        ).status_code
        == 413
    )


def test_checksum_verification_and_private_failure_redaction(client, db, bundle, identity):
    headers = sign_in(client, identity)
    draft = make_draft(client, bundle, headers)
    response = upload(client, bundle, draft, headers, [department()])
    job = db.get(ImportJob, UUID(response.json()["id"]))
    private_path(job).write_bytes(b"{}")
    process_job(db, job)
    assert job.state == "failed" and "checksum" in job.failure
    private_path(job).unlink()
    process_job(db, job)
    assert job.state == "failed" and "unreadable" in job.failure
    assert job.storage_key not in job.failure and str(private_path(job)) not in job.failure
