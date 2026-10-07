"""Locked, exact-content review and atomic publication. No filesystem side effects."""

import hashlib
import json
from uuid import UUID, uuid4

from geoalchemy2 import Geography
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import cast, func, select, text

from app.core.errors import DomainError
from app.models import (
    ActiveRelease,
    Anchor,
    Building,
    Campus,
    Edge,
    Frame,
    Node,
    Place,
    Release,
    Revision,
)
from app.models.admin import AuditEvent, Department, DepartmentPlace, PlaceAlias, User
from app.models.imports import ImportBinding, ImportJob
from app.models.publication import (
    ReleaseAction,
    ReleaseArtifact,
    ReviewDecision,
    ReviewSubmission,
    SourceAsset,
    ValidationRun,
)
from app.schemas.admin import CatalogWrite
from app.schemas.api import Point, Polygon
from app.schemas.dataset import validate_positions
from app.services.admin_auth import audit, permissions
from app.services.admin_catalog import MODELS, record
from app.services.admin_graph import route_test, validate_graph
from app.services.catalog import normalize
from app.services.imports import final_graph_guard

VALIDATOR = "outdoor-publication-v1"
TABLES = {
    "frames": Frame,
    "buildings": Building,
    "places": Place,
    "nodes": Node,
    "edges": Edge,
    "anchors": Anchor,
    "departments": Department,
    "department_places": DepartmentPlace,
    "aliases": PlaceAlias,
    "bindings": ImportBinding,
    "sources": SourceAsset,
}


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def checksum(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def locked_revision(db, campus_id, revision_id, header=None, *, read=False):
    revision = db.scalar(
        select(Revision)
        .where(Revision.id == revision_id, Revision.campus_id == campus_id)
        .with_for_update(read=read)
        .execution_options(populate_existing=True)
    )
    if revision is None:
        raise DomainError("location_not_found", "Revision not found in this campus.", 404)
    if header is not None:
        if header != f'"{revision.edit_version}"':
            raise DomainError(
                "conflict",
                "The revision changed. Refresh and retain/reconcile your input before retrying.",
                409,
            )
    elif not read:
        raise DomainError(
            "precondition_required", "Send the current revision version in If-Match.", 428
        )
    return revision


def snapshot(db, revision):
    """Full reviewed dataset, excluding storage bytes and volatile review bookkeeping."""
    result = {}
    for name, model in TABLES.items():
        rows = db.scalars(
            select(model)
            .where(model.dataset_revision_id == revision.id)
            .order_by(model.id)
            .limit(15001)
        ).all()
        if len(rows) > 15000:
            raise DomainError(
                "dataset_limit",
                "Publication supports at most 15,000 records per entity layer.",
                422,
            )
        values = {}
        for row in rows:
            item = {}
            for col in model.__table__.columns:
                if col.name in {"dataset_revision_id", "campus_id", "original"}:
                    continue
                value = getattr(row, col.name)
                if col.name in {"point", "footprint", "geometry"}:
                    value = (
                        json.loads(db.scalar(select(func.ST_AsGeoJSON(value, 15))))
                        if value is not None
                        else None
                    )
                elif isinstance(value, UUID):
                    value = str(value)
                item[col.name] = value
            values[str(row.id)] = item
        result[name] = values
    campus = db.get(Campus, revision.campus_id)
    result["campus"] = dict(
        id=str(campus.id),
        code=campus.code,
        name=campus.name,
        timezone=campus.timezone,
        is_demo=campus.is_demo,
        center=json.loads(db.scalar(select(func.ST_AsGeoJSON(campus.center, 15)))),
        boundary=json.loads(db.scalar(select(func.ST_AsGeoJSON(campus.boundary, 15)))),
    )
    return result


def public_projection(full):
    """One approved projection shared by artifacts and server query eligibility."""

    def fields(row, allowed):
        return {key: row[key] for key in allowed}

    allowed = {
        "buildings": ("id", "code", "name", "footprint"),
        "places": ("id", "code", "name", "kind", "description", "building_id", "point", "aliases"),
        "nodes": ("id", "frame_id", "label", "point"),
        "edges": (
            "id",
            "physical_path_id",
            "from_node_id",
            "to_node_id",
            "frame_id",
            "kind",
            "geometry",
            "distance_m",
            "distance_status",
            "accessibility_status",
            "is_open",
            "width_m",
            "slope_percent",
            "step_count",
            "surface",
        ),
        "anchors": ("id", "place_id", "node_id", "accessibility_status", "is_open"),
    }
    result = {"schema_version": 1, "audience": "public", "campus": full["campus"]}
    for layer in ("buildings", "places", "nodes", "edges", "anchors"):
        eligible = {}
        for identity, row in full[layer].items():
            if layer != "anchors" and row["visibility"] != "public":
                continue
            if (
                layer == "places"
                and row["building_id"]
                and row["building_id"] not in result["buildings"]
            ):
                continue
            if layer == "edges" and (
                row["from_node_id"] not in result["nodes"]
                or row["to_node_id"] not in result["nodes"]
            ):
                continue
            if layer == "anchors" and (
                row["place_id"] not in result["places"] or row["node_id"] not in result["nodes"]
            ):
                continue
            eligible[identity] = fields(row, allowed[layer])
        result[layer] = eligible
    used_frames = {n["frame_id"] for n in result["nodes"].values()}
    result["frames"] = {
        i: fields(f, ("id", "code", "kind")) for i, f in full["frames"].items() if i in used_frames
    }
    result["departments"] = {}
    for identity, department in full["departments"].items():
        links = sorted(
            {
                link["place_id"]
                for link in full["department_places"].values()
                if link["department_id"] == identity and link["place_id"] in result["places"]
            }
        )
        if links:
            result["departments"][identity] = {
                **fields(department, ("id", "code", "name", "description")),
                "place_ids": links,
            }
    result["assets"] = {
        i: {
            "id": i,
            "title": s["title"],
            "attribution": s["attribution"],
            "checksum": checksum(s["derivative"]),
            "geojson": s["derivative"],
        }
        for i, s in full["sources"].items()
        if s["approved_by"] and s["rights"] != "restricted" and s["derivative"] is not None
    }
    result["attributions"] = sorted(
        {
            s["attribution"]
            for s in full["sources"].values()
            if s["approved_by"] and s["rights"] != "restricted"
        }
    )
    return result


def sanitize_overlay(original):
    """Only bounded WGS84 vectors and plain reviewed labels, never arbitrary properties."""
    if original.get("type") != "FeatureCollection" or set(original) - {"type", "features"}:
        raise ValueError("Use a WGS84 FeatureCollection without custom CRS/foreign members.")
    features = original.get("features")
    if not isinstance(features, list) or not 1 <= len(features) <= 500:
        raise ValueError("Overlay must have 1–500 features.")
    clean = []
    for feature in features:
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise ValueError("Invalid feature.")
        geo = feature.get("geometry", {})
        kind, coords = geo.get("type"), geo.get("coordinates")
        if kind == "Point":
            Point.model_validate(geo)
            validate_positions([coords])
        elif kind == "LineString":
            if not isinstance(coords, list) or not 2 <= len(coords) <= 500:
                raise ValueError("Line needs 2–500 coordinates.")
            validate_positions(coords)
        elif kind == "Polygon":
            Polygon.model_validate(geo)
            if not isinstance(coords, list) or not 1 <= len(coords) <= 10:
                raise ValueError("Polygon needs 1–10 rings.")
            for ring in coords:
                if not 4 <= len(ring) <= 500 or ring[0] != ring[-1]:
                    raise ValueError("Polygon rings must close with 4–500 coordinates.")
                validate_positions(ring)
        else:
            raise ValueError(
                "Only outdoor Point/LineString/Polygon derivatives are supported; floorplans belong to M3."
            )
        props = feature.get("properties") or {}
        if props.get("public") is not True:
            continue
        label = props.get("label", "")
        if not isinstance(label, str) or len(label) > 160:
            raise ValueError("Label must be plain text up to 160 characters.")
        clean.append(
            {
                "type": "Feature",
                "geometry": {"type": kind, "coordinates": coords},
                "properties": {"label": label},
            }
        )
    if not clean:
        raise ValueError("Explicitly mark approved public features with properties.public=true.")
    return {"type": "FeatureCollection", "features": clean}


def add_source(db, revision, payload, actor, request_id):
    if revision.status != "draft":
        raise DomainError(
            "conflict", "Return the submission to draft before changing sources.", 409
        )
    campus = db.get(Campus, revision.campus_id)
    if payload.rights == "synthetic" and not campus.is_demo:
        raise DomainError(
            "invalid_input", "Synthetic rights are only allowed for a clearly labelled demo campus."
        )
    raw = canonical(payload.original) if payload.original is not None else None
    if raw and len(raw) > 5 * 1024 * 1024:
        raise DomainError("upload_too_large", "Original exceeds the private 5MiB limit.", 413)
    if payload.display_overlay and (raw is None or payload.rights == "restricted"):
        raise DomainError(
            "invalid_input",
            "A display derivative needs a permitted original; restricted originals never publish.",
        )
    try:
        derivative = sanitize_overlay(payload.original) if payload.display_overlay else None
    except (ValueError, TypeError, AttributeError, ValidationError):
        raise DomainError(
            "invalid_input",
            "Use a bounded WGS84 GeoJSON FeatureCollection with Point, LineString or Polygon geometry and plain labels.",
        ) from None
    if derivative:
        for feature in derivative["features"]:
            geo = json.dumps(feature["geometry"])
            if not db.scalar(
                select(func.ST_IsValid(func.ST_SetSRID(func.ST_GeomFromGeoJSON(geo), 4326)))
            ) or not db.scalar(
                select(
                    func.ST_Covers(
                        campus.boundary, func.ST_SetSRID(func.ST_GeomFromGeoJSON(geo), 4326)
                    )
                )
            ):
                raise DomainError(
                    "invalid_input",
                    "Overlay geometry must be valid and inside this campus boundary.",
                )
    row = SourceAsset(
        id=uuid4(),
        campus_id=revision.campus_id,
        dataset_revision_id=revision.id,
        title=payload.title,
        rights=payload.rights,
        provenance=payload.provenance,
        attribution=payload.attribution,
        uploader_id=actor.id,
        original=raw,
        original_checksum=hashlib.sha256(raw).hexdigest() if raw else None,
        derivative=derivative,
    )
    used = db.scalar(
        select(func.coalesce(func.sum(func.octet_length(SourceAsset.original)), 0)).where(
            SourceAsset.campus_id == revision.campus_id
        )
    )
    if used + len(raw or b"") > 100 * 1024 * 1024:
        raise DomainError(
            "storage_limit",
            "Campus source quota is 100MiB; remove unused draft originals before retrying.",
            413,
        )
    db.add(row)
    revision.edit_version += 1
    revision.checksum = None
    db.flush()
    audit(
        db,
        "source.register",
        request_id,
        actor_id=actor.id,
        campus_id=revision.campus_id,
        revision_id=revision.id,
        resource_id=row.id,
        after={
            "title": row.title,
            "original_checksum": row.original_checksum,
            "rights": row.rights,
        },
    )
    return {"id": str(row.id), "edit_version": revision.edit_version}


def validate(db, revision, payload, actor, request_id):
    if revision.status != "draft":
        raise DomainError("conflict", "Validation requires an editable draft.", 409)
    full = snapshot(db, revision)
    quality = validate_graph(db, revision)
    findings = quality["diagnostics"]

    def report(code, message, entity="revision", ids=None, severity="error"):
        findings.append(
            dict(code=code, message=message, entity=entity, ids=ids or [], severity=severity)
        )

    if (
        quality["truncated"]
        or any(
            sum(f["code"] == code for f in findings) >= 100
            for code in ("near_duplicate", "unmapped_intersection")
        )
        or any(f["kind"] != "outdoor" for f in full["frames"].values())
    ):
        report(
            "validation_budget",
            "Reduce the dataset to complete diagnostics; only outdoor publication is supported in 2C.",
        )
    try:
        final_graph_guard(db, revision)
    except (DomainError, ValueError) as exc:
        report("graph_integrity", exc.message if isinstance(exc, DomainError) else str(exc))
    for entity, model in MODELS.items():
        for row in db.scalars(select(model).where(model.dataset_revision_id == revision.id)):
            try:
                TypeAdapter(CatalogWrite).validate_python(record(db, entity, row).item)
            except (ValueError, ValidationError):
                report(
                    "catalog_fields",
                    "Repair invalid catalog fields before submission.",
                    entity,
                    [str(row.id)],
                )
    for identity, place in full["places"].items():
        if (
            place["visibility"] == "public"
            and place["building_id"]
            and full["buildings"].get(place["building_id"], {}).get("visibility") != "public"
        ):
            report(
                "restricted_building",
                "Detach this public place from its restricted building.",
                "places",
                [identity],
            )
        if place["visibility"] == "public" and not any(
            a["place_id"] == identity and a["is_open"] for a in full["anchors"].values()
        ):
            report(
                "unmapped_entrance",
                "Routing unavailable: no open entrance. Acknowledge this explicitly disclosed coverage gap.",
                "places",
                [identity],
                "warning",
            )
        aliases = sorted(a["value"] for a in full["aliases"].values() if a["place_id"] == identity)
        expected_search = normalize(
            " ".join([place["code"], place["name"], place["kind"], *place["aliases"]])
        )
        if set(place["aliases"]) != set(aliases) or place["search_text"] != expected_search:
            report(
                "alias_projection",
                "Repair the canonical alias/search projection.",
                "places",
                [identity],
            )
    for model, col, entity in [
        (Building, Building.footprint, "buildings"),
        (Place, Place.point, "places"),
        (Node, Node.point, "nodes"),
    ]:
        for identity in db.scalars(
            select(model.id).where(
                model.dataset_revision_id == revision.id,
                ~func.ST_Covers(db.get(Campus, revision.campus_id).boundary, col),
            )
        ):
            report(
                "outside_boundary",
                "Move this geometry inside the approved campus boundary.",
                entity,
                [str(identity)],
            )
    for identity in db.scalars(
        select(Edge.id).where(
            Edge.dataset_revision_id == revision.id,
            func.abs(func.ST_Length(cast(Edge.geometry, Geography)) - Edge.distance_m) > 0.01,
        )
    ):
        report(
            "invalid_distance", "Recalculate full stored polyline length.", "edges", [str(identity)]
        )
    permitted_sources = [
        s for s in full["sources"].values() if s["rights"] != "restricted" and s["approved_by"]
    ]
    if not permitted_sources:
        report(
            "source_approval",
            "Register permitted rights/provenance and obtain independent source approval.",
            "sources",
        )
    for identity, source in full["sources"].items():
        if source["approved_by"]:
            approver = db.get(User, UUID(source["approved_by"]))
            if (
                not approver
                or not approver.active
                or "source_approve" not in permissions(db, approver.id, revision.campus_id)
            ):
                report(
                    "source_reviewer_revoked",
                    "Source approval reviewer is inactive or no longer authorized; replace/review the source again.",
                    "sources",
                    [identity],
                )
        if source["derivative"] and not source["approved_by"]:
            report(
                "asset_approval",
                "Review the exact sanitized derivative and approve it, or remove it from this draft.",
                "sources",
                [identity],
            )
    for job in db.scalars(
        select(ImportJob)
        .where(ImportJob.revision_id == revision.id, ImportJob.state == "committed")
        .order_by(ImportJob.id)
    ):
        report(
            "import_provenance",
            f"Review applied import {job.filename}: rights/provenance are shown in the review packet; original stays private.",
            "imports",
            [str(job.id)],
            "warning",
        )
    unknown = [
        i
        for i, e in full["edges"].items()
        if e["visibility"] == "public" and e["accessibility_status"] == "unknown"
    ]
    if unknown:
        report(
            "unknown_accessibility",
            "Unknown accessibility remains excluded from verified step-free routing. Do not infer suitability.",
            "edges",
            unknown,
            "warning",
        )
    evidence = []
    if {r.profile for r in payload.routes} != {"shortest", "step_free"}:
        report(
            "route_profiles",
            "Expected-route evidence must cover both standard and step-free profiles.",
            "routes",
        )
    for expected in payload.routes:
        item = expected.model_dump(mode="json")
        try:
            if expected.source == expected.target or any(
                full["places"].get(str(i), {}).get("visibility") != "public"
                for i in (expected.source, expected.target)
            ):
                raise ValueError("Use two distinct public places.")
            actual = route_test(db, revision, expected.source, expected.target, expected.profile)
            matched = actual["found"] == expected.expected_found and (
                expected.maximum_distance_m is None
                or (actual["found"] and actual["distance_m"] <= expected.maximum_distance_m)
            )
            item.update(actual=actual, passed=matched)
            if not matched:
                report(
                    "route_expectation",
                    "Computed route differs from the expected result. Correct the graph or explicitly revise the expectation/reason.",
                    "routes",
                    [str(expected.source), str(expected.target)],
                )
        except (DomainError, ValueError) as exc:
            item.update(
                passed=False, error=exc.message if isinstance(exc, DomainError) else str(exc)
            )
            report(
                "route_reference",
                "Route evidence requires distinct existing public places.",
                "routes",
            )
        evidence.append(item)
    for finding in findings:
        finding["id"] = checksum(finding)[:24]
    report_value = dict(
        errors=sum(f["severity"] == "error" for f in findings),
        warnings=sum(f["severity"] == "warning" for f in findings),
        diagnostics=findings,
        sources=full["sources"],
        imports=[
            {"id": str(j.id), "checksum": j.checksum, "filename": j.filename, "options": j.options}
            for j in db.scalars(
                select(ImportJob)
                .where(ImportJob.revision_id == revision.id, ImportJob.state == "committed")
                .order_by(ImportJob.id)
            )
        ],
    )
    run = ValidationRun(
        campus_id=revision.campus_id,
        revision_id=revision.id,
        edit_version=revision.edit_version,
        checksum=checksum(full),
        validator=VALIDATOR,
        actor_id=actor.id,
        report=report_value,
        evidence=evidence,
    )
    db.add(run)
    db.flush()
    audit(
        db,
        "revision.validate",
        request_id,
        actor_id=actor.id,
        campus_id=revision.campus_id,
        revision_id=revision.id,
        resource_id=run.id,
        after={
            "checksum": run.checksum,
            "errors": report_value["errors"],
            "warnings": report_value["warnings"],
        },
    )
    return run


def acknowledgements(run, values):
    warning_ids = {f["id"] for f in run.report["diagnostics"] if f["severity"] == "warning"}
    if set(values) != warning_ids or any(not 10 <= len(v.strip()) <= 2000 for v in values.values()):
        raise DomainError(
            "warning_acknowledgement",
            "Provide an explicit reason (10–2000 characters) for every current warning and no stale warning IDs.",
            422,
        )


def submit(db, revision, payload, actor, request_id):
    run = db.get(ValidationRun, payload.validation_id)
    if (
        revision.status != "draft"
        or not run
        or run.revision_id != revision.id
        or run.campus_id != revision.campus_id
        or run.edit_version != revision.edit_version
        or run.checksum != checksum(snapshot(db, revision))
        or run.validator != VALIDATOR
    ):
        raise DomainError(
            "conflict",
            "Validation is stale or belongs to another revision. Run validation again.",
            409,
        )
    if run.report["errors"]:
        raise DomainError(
            "validation_failed",
            "Resolve all blocking errors and rerun validation before submission.",
            422,
        )
    acknowledgements(run, payload.acknowledgements)
    revision.status = "review"
    revision.checksum = run.checksum
    revision.edit_version += 1
    submission = ReviewSubmission(
        campus_id=revision.campus_id,
        revision_id=revision.id,
        validation_id=run.id,
        submitter_id=actor.id,
        edit_version=revision.edit_version,
        checksum=run.checksum,
        status="submitted",
        acknowledgements=payload.acknowledgements,
    )
    db.add(submission)
    db.flush()
    audit(
        db,
        "review.submit",
        request_id,
        actor_id=actor.id,
        campus_id=revision.campus_id,
        revision_id=revision.id,
        resource_id=submission.id,
        after={"checksum": run.checksum, "version": revision.edit_version},
    )
    return submission


def independent(db, submission, actor):
    contributor = db.scalar(
        select(AuditEvent.id)
        .where(
            AuditEvent.revision_id == submission.revision_id,
            AuditEvent.actor_id == actor.id,
            (AuditEvent.action == "draft.create")
            | AuditEvent.action.like("catalog.%")
            | AuditEvent.action.like("graph.%")
            | (AuditEvent.action == "import.apply")
            | (AuditEvent.action == "source.register")
            | (AuditEvent.action == "source.remove"),
        )
        .limit(1)
    )
    if actor.id == submission.submitter_id or contributor:
        raise DomainError(
            "separation_of_duties",
            "A contributor/submitter cannot approve or publish this revision. Use an independent campus reviewer, including for system administrators.",
            403,
        )


def decision(db, revision, submission, payload, actor, request_id):
    if (
        revision.status != "review"
        or submission.status not in {"submitted", "approved"}
        or submission.edit_version != revision.edit_version
        or submission.checksum != checksum(snapshot(db, revision))
    ):
        raise DomainError(
            "conflict", "Review content/state changed; reload the review packet.", 409
        )
    run = db.get(ValidationRun, submission.validation_id)
    if payload.decision == "approve":
        independent(db, submission, actor)
        if submission.status != "submitted":
            raise DomainError("conflict", "This submission already has a decision.", 409)
        acknowledgements(run, payload.acknowledgements)
        submission.status = "approved"
    else:
        submission.status = "rejected" if payload.decision == "reject" else "withdrawn"
        revision.status = "draft"
        revision.checksum = None
    revision.edit_version += 1
    submission.edit_version = revision.edit_version
    entry = ReviewDecision(
        submission_id=submission.id,
        actor_id=actor.id,
        decision=payload.decision,
        notes=payload.notes,
        acknowledgements=payload.acknowledgements,
    )
    db.add(entry)
    audit(
        db,
        "review." + payload.decision,
        request_id,
        actor_id=actor.id,
        campus_id=revision.campus_id,
        revision_id=revision.id,
        resource_id=submission.id,
        after={
            "checksum": submission.checksum,
            "status": submission.status,
            "notes": payload.notes,
        },
    )
    db.flush()
    return submission


def generate_artifact(full):
    # Kept as a pure boundary so generation/storage failures can be injected and rolled back.
    artifact = public_projection(full)
    canonical(artifact)
    return artifact


def action_retry(db, campus_id, actor, payload):
    prior = db.scalar(
        select(ReleaseAction).where(
            ReleaseAction.campus_id == campus_id,
            ReleaseAction.actor_id == actor.id,
            ReleaseAction.key == payload.key,
        )
    )
    fingerprint = checksum(payload.model_dump(mode="json"))
    if prior:
        if prior.fingerprint != fingerprint:
            raise DomainError("conflict", "Idempotency key was used with a different request.", 409)
        return prior.result
    return None


def campus_lock(db, campus_id):
    # Same lock as draft creation/demo seeding, then revision row lock: one lock order.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": str(campus_id)})


def active_pointer(db, campus_id, expected):
    active = db.scalar(
        select(ActiveRelease)
        .where(ActiveRelease.campus_id == campus_id, ActiveRelease.audience == "public")
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (active.release_id if active else None) != expected:
        raise DomainError(
            "conflict",
            "The active release changed. Compare the latest release before publishing or rolling back.",
            409,
        )
    return active


def publish(db, revision, submission, payload, actor, request_id):
    independent(db, submission, actor)
    if (
        revision.status != "review"
        or submission.status != "approved"
        or submission.edit_version != revision.edit_version
    ):
        raise DomainError(
            "conflict", "Publication requires the exact approved review version.", 409
        )
    full = snapshot(db, revision)
    if checksum(full) != submission.checksum or revision.checksum != submission.checksum:
        raise DomainError(
            "conflict", "Approved content changed. Return to draft and revalidate.", 409
        )
    active = active_pointer(db, revision.campus_id, payload.expected_release_id)
    approving = db.scalar(
        select(ReviewDecision).where(
            ReviewDecision.submission_id == submission.id, ReviewDecision.decision == "approve"
        )
    )
    reviewer = db.get(User, approving.actor_id) if approving else None
    if (
        not reviewer
        or not reviewer.active
        or "review_decide" not in permissions(db, reviewer.id, revision.campus_id)
    ):
        raise DomainError(
            "approval_revoked",
            "Approval reviewer is no longer authorized; return to draft and obtain fresh independent approval.",
            409,
        )
    artifact = generate_artifact(full)
    revision.status = "frozen"
    revision.edit_version += 1
    db.flush()
    release = Release(
        id=uuid4(),
        campus_id=revision.campus_id,
        dataset_revision_id=revision.id,
        checksum=revision.checksum,
    )
    db.add(release)
    db.flush()
    db.add(
        ReleaseArtifact(
            release_id=release.id,
            campus_id=revision.campus_id,
            checksum=checksum(artifact),
            content=artifact,
            publisher_id=actor.id,
            submission_id=submission.id,
        )
    )
    if active:
        active.release_id = release.id
    else:
        db.add(
            ActiveRelease(campus_id=revision.campus_id, audience="public", release_id=release.id)
        )
    submission.status = "published"
    result = {
        "release_id": str(release.id),
        "artifact_checksum": checksum(artifact),
        "edit_version": revision.edit_version,
        "revision_id": str(revision.id),
    }
    db.add(
        ReleaseAction(
            campus_id=revision.campus_id,
            actor_id=actor.id,
            key=payload.key,
            fingerprint=checksum(payload.model_dump(mode="json")),
            result=result,
        )
    )
    audit(
        db,
        "release.publish",
        request_id,
        actor_id=actor.id,
        campus_id=revision.campus_id,
        revision_id=revision.id,
        resource_id=release.id,
        before={
            "release_id": str(payload.expected_release_id) if payload.expected_release_id else None
        },
        after={
            **result,
            "submission_id": str(submission.id),
            "content_checksum": revision.checksum,
        },
    )
    db.flush()
    return result


def rollback(db, campus_id, payload, actor, request_id):
    active = active_pointer(db, campus_id, payload.expected_release_id)
    target = db.scalar(
        select(Release).where(
            Release.id == payload.target_release_id, Release.campus_id == campus_id
        )
    )
    current = db.get(Release, active.release_id) if active else None
    if (
        not target
        or not current
        or target.id == current.id
        or db.get(Revision, target.dataset_revision_id).version
        >= db.get(Revision, current.dataset_revision_id).version
        or db.get(Revision, target.dataset_revision_id).status != "frozen"
    ):
        raise DomainError(
            "invalid_input", "Choose an earlier immutable release in this campus history."
        )
    artifact = db.get(ReleaseArtifact, target.id)
    if target.checksum != db.get(Revision, target.dataset_revision_id).checksum or (
        artifact is None and not db.get(Campus, campus_id).is_demo
    ):
        raise DomainError(
            "release_integrity",
            "Target needs an approved artifact or a trusted synthetic legacy release.",
            422,
        )
    if artifact and artifact.checksum != checksum(artifact.content):
        raise DomainError(
            "release_integrity",
            "Target artifact failed integrity verification; the active release was retained.",
            422,
        )
    active.release_id = target.id
    result = {"release_id": str(target.id), "previous_release_id": str(current.id)}
    db.add(
        ReleaseAction(
            campus_id=campus_id,
            actor_id=actor.id,
            key=payload.key,
            fingerprint=checksum(payload.model_dump(mode="json")),
            result=result,
        )
    )
    audit(
        db,
        "release.rollback",
        request_id,
        actor_id=actor.id,
        campus_id=campus_id,
        revision_id=target.dataset_revision_id,
        resource_id=target.id,
        before={"release_id": str(current.id)},
        after={**result, "reason": payload.reason, "closure_overlay_version": 0},
    )
    db.flush()
    return result


def packet(db, revision):
    runs = db.scalars(
        select(ValidationRun)
        .where(ValidationRun.revision_id == revision.id)
        .order_by(ValidationRun.created_at.desc(), ValidationRun.id)
        .limit(30)
    ).all()
    submissions = db.scalars(
        select(ReviewSubmission)
        .where(ReviewSubmission.revision_id == revision.id)
        .order_by(ReviewSubmission.edit_version.desc())
        .limit(30)
    ).all()
    full = snapshot(db, revision)
    parent = db.get(Revision, revision.parent_id) if revision.parent_id else None
    old = snapshot(db, parent) if parent else {}
    diff = []
    for entity in TABLES:
        for identity in sorted(set(full[entity]) | set(old.get(entity, {}))):
            before, after = old.get(entity, {}).get(identity), full[entity].get(identity)
            if before != after:
                diff.append(dict(entity=entity, id=identity, before=before, after=after))

    def output(obj, exclude=()):
        return {
            c.name: str(getattr(obj, c.name))
            if isinstance(getattr(obj, c.name), UUID)
            else getattr(obj, c.name)
            for c in obj.__table__.columns
            if c.name not in exclude
        }

    return {
        "id": str(revision.id),
        "status": revision.status,
        "edit_version": revision.edit_version,
        "checksum": checksum(full),
        "sources": full["sources"],
        "places": [
            {"id": i, "name": p["name"]}
            for i, p in full["places"].items()
            if p["visibility"] == "public"
        ],
        "validations": [output(r) for r in runs],
        "submissions": [
            {
                **output(s),
                "decisions": [
                    output(d)
                    for d in db.scalars(
                        select(ReviewDecision)
                        .where(ReviewDecision.submission_id == s.id)
                        .order_by(ReviewDecision.created_at)
                    )
                ],
            }
            for s in submissions
        ],
        "diff": diff,
        "public_counts": {
            k: len(v)
            for k, v in public_projection(full).items()
            if isinstance(v, dict) and k != "campus"
        },
        "limits": "15,000 records/layer; 30 validation/submission history entries; complete diff retained.",
    }
