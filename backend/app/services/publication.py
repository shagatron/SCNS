"""Locked, exact-content review and atomic publication. No filesystem side effects."""

import hashlib
import json
import math
from datetime import date
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
from app.models.connections import (
    Connector,
    ConnectorPath,
    ConnectorStop,
    EntranceTransition,
    FloorRouting,
)
from app.models.floorplans import Floor, MapLayer
from app.models.imports import ImportBinding, ImportJob
from app.models.indoor import IndoorAccess, IndoorEdge, IndoorNode, Room
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
from app.services.admin_graph import validate_graph
from app.services.catalog import normalize
from app.services.imports import final_graph_guard, strict_json

VALIDATOR = "indoor-routing-v4"
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
    "floors": Floor,
    "floorplan_layers": MapLayer,
    "indoor_rooms": Room,
    "indoor_nodes": IndoorNode,
    "indoor_edges": IndoorEdge,
    "indoor_access": IndoorAccess,
    "floor_routing": FloorRouting,
    "connectors": Connector,
    "connector_stops": ConnectorStop,
    "connector_paths": ConnectorPath,
    "entrance_transitions": EntranceTransition,
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
                if col.name in {"dataset_revision_id", "campus_id", "original", "png"}:
                    continue
                value = getattr(row, col.name)
                if col.name in {"point", "footprint", "geometry"}:
                    value = (
                        json.loads(db.scalar(select(func.ST_AsGeoJSON(value, 15))))
                        if value is not None
                        else None
                    )
                elif isinstance(value, date):
                    value = value.isoformat()
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
        if s["approved_by"]
        and s["rights"] != "restricted"
        and s["derivative"] is not None
        and s["derivative"].get("type") == "FeatureCollection"
    }
    result["floors"] = {}
    result["floorplans"] = {}
    for identity, floor in full["floors"].items():
        if (
            floor["visibility"] != "public"
            or floor["building_id"] not in result["buildings"]
            or not floor["layer_id"]
        ):
            continue
        layer = full["floorplan_layers"].get(floor["layer_id"])
        source = full["sources"].get(layer["source_id"]) if layer else None
        if not source or not source["approved_by"] or source["rights"] == "restricted":
            continue
        frame = full["frames"].get(floor["frame_id"])
        if (
            not frame
            or frame["kind"] != "indoor"
            or layer["floor_id"] != identity
            or layer["frame_id"] != floor["frame_id"]
        ):
            continue
        value = frame["calibration"]
        result["floors"][identity] = {
            **fields(
                floor,
                (
                    "id",
                    "building_id",
                    "code",
                    "label",
                    "ordering",
                    "elevation_m",
                    "frame_id",
                    "layer_id",
                ),
            ),
            "navigation_mode": "display_only",
            "metric_navigation": False,
        }
        result["frames"][floor["frame_id"]] = {
            **fields(frame, ("id", "code", "kind", "width_px", "height_px", "metres_per_pixel")),
            "origin": "top_left",
            "axes": "x_right_y_down",
            "units": "pixels",
            "calibration_status": "calibrated"
            if value and value.get("reviewer")
            else "uncalibrated",
            "uncertainty_m": value["uncertainty_m"] if value and value.get("reviewer") else None,
        }
        result["floorplans"][layer["id"]] = {
            **fields(
                layer,
                (
                    "id",
                    "floor_id",
                    "frame_id",
                    "page",
                    "width_px",
                    "height_px",
                    "display_width_px",
                    "display_height_px",
                    "checksum",
                ),
            ),
            "title": source["title"],
            "attribution": source["attribution"],
            "media_type": "image/png",
        }
    result["indoor_rooms"] = {}
    result["indoor_nodes"] = {}
    result["indoor_edges"] = {}
    result["indoor_access"] = {}
    for entity, allowed_fields in {
        "indoor_rooms": ("id", "floor_id", "frame_id", "code", "x_px", "y_px"),
        "indoor_nodes": ("id", "floor_id", "frame_id", "kind", "label", "x_px", "y_px"),
        "indoor_edges": (
            "id",
            "floor_id",
            "frame_id",
            "physical_path_id",
            "from_node_id",
            "to_node_id",
            "kind",
            "polyline",
            "distance_m",
            "distance_status",
            "accessibility_status",
            "width_m",
            "slope_percent",
            "step_count",
            "surface",
            "is_open",
        ),
        "indoor_access": (
            "id",
            "floor_id",
            "frame_id",
            "room_id",
            "node_id",
            "role",
            "priority",
            "accessibility_status",
            "is_open",
        ),
    }.items():
        for identity, row in full.get(entity, {}).items():
            if row["visibility"] != "public" or row["floor_id"] not in result["floors"]:
                continue
            if entity == "indoor_rooms" and identity not in result["places"]:
                continue
            if entity == "indoor_edges" and any(
                row[k] not in result["indoor_nodes"] for k in ("from_node_id", "to_node_id")
            ):
                continue
            if entity == "indoor_access" and (
                row["room_id"] not in result["indoor_rooms"]
                or row["node_id"] not in result["indoor_nodes"]
            ):
                continue
            result[entity][identity] = fields(row, allowed_fields)
            if entity == "indoor_rooms":
                result["places"][identity].update(
                    code=row["code"],
                    floor_id=row["floor_id"],
                    frame_id=row["frame_id"],
                    navigation_mode="indoor_catalog_only",
                    routable=False,
                )
    from app.routing.projection import project_connections

    project_connections(result, full)
    for identity in list(result["places"]):
        if identity in full.get("indoor_rooms", {}) and identity not in result["indoor_rooms"]:
            del result["places"][identity]
    for identity in list(result["departments"]):
        result["departments"][identity]["place_ids"] = [
            p for p in result["departments"][identity]["place_ids"] if p in result["places"]
        ]
        if not result["departments"][identity]["place_ids"]:
            del result["departments"][identity]
    result["attributions"] = sorted(
        {
            s["attribution"]
            for s in full["sources"].values()
            if s["approved_by"]
            and s["rights"] != "restricted"
            and (
                (s["derivative"] or {}).get("kind") != "floorplan"
                or s["derivative"].get("layer_id") in result["floorplans"]
            )
        }
    )
    return result


def review_sources(full):
    # Retained, unselected floorplan history stays private and cannot block or
    # authorize the selected display derivative. Outdoor source rules are unchanged.
    selected = {
        full["floorplan_layers"][floor["layer_id"]]["source_id"]
        for floor in full["floors"].values()
        if floor["layer_id"] in full["floorplan_layers"]
    }
    return {
        identity: source
        for identity, source in full["sources"].items()
        if (source["derivative"] or {}).get("kind") != "floorplan" or identity in selected
    }


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
        positions = (
            [coords]
            if kind == "Point"
            else coords
            if kind == "LineString"
            else [p for ring in coords for p in ring]
        )
        if any(len(p) != 2 or any(type(n) not in {int, float} for n in p) for p in positions):
            raise ValueError("Use numeric longitude/latitude pairs without booleans or altitude.")
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
    try:
        raw = (
            payload.original_text.encode("utf-8")
            if payload.original_text is not None
            else canonical(payload.original)
            if payload.original is not None
            else None
        )
        original = (
            strict_json(payload.original_text.removeprefix("\ufeff"))
            if payload.original_text is not None
            else payload.original
        )
        if original is not None and not isinstance(original, dict):
            raise ValueError("Original must be a JSON object")
    except (ValueError, UnicodeError, RecursionError):
        raise DomainError(
            "invalid_input",
            "Original must be valid UTF-8 JSON without duplicate keys/non-finite numbers; provide one original representation.",
        ) from None
    if raw and len(raw) > 5 * 1024 * 1024:
        raise DomainError("upload_too_large", "Original exceeds the private 5MiB limit.", 413)
    if payload.display_overlay and (raw is None or payload.rights == "restricted"):
        raise DomainError(
            "invalid_input",
            "A display derivative needs a permitted original; restricted originals never publish.",
        )
    try:
        derivative = sanitize_overlay(original) if payload.display_overlay else None
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
        original_filename=(payload.original_filename or "inline-source.json") if raw else None,
        media_type="application/geo+json"
        if payload.original_filename and payload.original_filename.lower().endswith(".geojson")
        else "application/json"
        if raw
        else None,
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
        or any(
            full["frames"].get(n["frame_id"], {}).get("kind") != "outdoor"
            for n in full["nodes"].values()
        )
    ):
        report(
            "validation_budget",
            "Reduce the dataset to complete diagnostics; only outdoor routing is supported; indoor graph nodes remain a later slice.",
        )
    try:
        final_graph_guard(db, revision)
    except (DomainError, ValueError) as exc:
        report("graph_integrity", exc.message if isinstance(exc, DomainError) else str(exc))
    for entity, model in MODELS.items():
        for row in db.scalars(select(model).where(model.dataset_revision_id == revision.id)):
            if entity == "places" and str(row.id) in full["indoor_rooms"]:
                continue
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
            " ".join(
                [
                    full["indoor_rooms"][identity]["code"]
                    if identity in full["indoor_rooms"]
                    else place["code"],
                    place["name"],
                    place["kind"],
                    *place["aliases"],
                ]
            )
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
    for identity, source in review_sources(full).items():
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
    from app.schemas.floorplans import CalibrationInput, FloorInput
    from app.services.floorplans import calibration as validate_calibration
    from app.services.indoor import validation as validate_indoor

    for floor_record in db.scalars(select(Floor).where(Floor.dataset_revision_id == revision.id)):
        if any(
            db.scalar(
                select(func.count())
                .select_from(m)
                .where(m.dataset_revision_id == revision.id, m.floor_id == floor_record.id)
            )
            for m in (Room, IndoorNode, IndoorEdge, IndoorAccess)
        ):
            indoor_quality = validate_indoor(db, revision, floor_record)
            findings.extend(indoor_quality["diagnostics"])
            if indoor_quality["truncated"]:
                report(
                    "indoor_budget",
                    "Reduce findings to complete indoor validation.",
                    "floors",
                    [str(floor_record.id)],
                )
    for identity, floor in full["floors"].items():
        try:
            FloorInput.model_validate(
                {
                    key: floor[key]
                    for key in (
                        "id",
                        "building_id",
                        "code",
                        "label",
                        "ordering",
                        "elevation_m",
                        "visibility",
                    )
                }
            )
        except ValueError:
            report("floor_fields", "Repair floor metadata.", "floors", [identity])
        layer = full["floorplan_layers"].get(floor["layer_id"]) if floor["layer_id"] else None
        frame = full["frames"].get(floor["frame_id"]) if floor["frame_id"] else None
        visible = (
            floor["visibility"] == "public"
            and floor["building_id"] in public_projection(full)["buildings"]
        )
        if (
            floor["visibility"] == "public"
            and full["buildings"].get(floor["building_id"], {}).get("visibility") != "public"
        ):
            report(
                "floor_visibility",
                "A public floor cannot expose a restricted building.",
                "floors",
                [identity],
            )
        if not layer:
            if visible:
                report(
                    "floor_plan_missing",
                    "Apply an approved plan or restrict this unfinished floor before publication.",
                    "floors",
                    [identity],
                )
            continue
        source = full["sources"].get(layer["source_id"])
        stored_layer = db.get(MapLayer, (revision.id, UUID(layer["id"])))
        if (
            not frame
            or frame["kind"] != "indoor"
            or layer["floor_id"] != identity
            or layer["frame_id"] != floor["frame_id"]
            or (frame["width_px"], frame["height_px"]) != (layer["width_px"], layer["height_px"])
            or hashlib.sha256(stored_layer.png).hexdigest() != layer["checksum"]
        ):
            report(
                "floor_plan_integrity",
                "Selected plan/frame/PNG checksum disagrees; reprocess and explicitly replace it.",
                "floors",
                [identity],
            )
            continue
        if not source or source["derivative"] != {
            key: value
            for key, value in {
                "kind": "floorplan",
                "layer_id": layer["id"],
                "checksum": layer["checksum"],
                "width_px": layer["width_px"],
                "height_px": layer["height_px"],
                "display_width_px": layer["display_width_px"],
                "display_height_px": layer["display_height_px"],
                "page": layer["page"],
            }.items()
        }:
            report(
                "floor_derivative",
                "Reprocess/approve the exact selected sanitized display derivative.",
                "floors",
                [identity],
            )
        if visible and (
            not source or source["rights"] == "restricted" or not source["approved_by"]
        ):
            report(
                "floor_asset_approval",
                "Public plans require permitted rights and independent sanitized derivative approval; restrict this floor otherwise.",
                "floors",
                [identity],
            )
        value = frame["calibration"]
        if value:
            try:
                checked = validate_calibration(
                    CalibrationInput.model_validate(
                        {
                            key: value[key]
                            for key in (
                                "method",
                                "primary",
                                "checks",
                                "measured_on",
                                "evidence",
                                "uncertainty_m",
                                "plan_quality",
                            )
                        }
                    ),
                    frame["width_px"],
                    frame["height_px"],
                    UUID(value["measured_by"]),
                    full["campus"]["is_demo"],
                    full["campus"]["timezone"],
                )
                if value.get("layer_checksum") != layer["checksum"] or not math.isclose(
                    checked["metres_per_pixel"], frame["metres_per_pixel"], rel_tol=1e-12
                ):
                    raise ValueError("Stale calibration")
            except (ValueError, KeyError, DomainError):
                report(
                    "floor_calibration",
                    "Repair/recalibrate inconsistent or stale measurement evidence.",
                    "floors",
                    [identity],
                )
            reviewer = db.get(User, UUID(value["reviewer"])) if value.get("reviewer") else None
            if visible and (
                not reviewer
                or not reviewer.active
                or str(reviewer.id) == value["measured_by"]
                or "source_approve" not in permissions(db, reviewer.id, revision.campus_id)
            ):
                report(
                    "calibration_review",
                    "Independent live calibration reviewer must approve these exact measurements.",
                    "floors",
                    [identity],
                )
        elif frame["metres_per_pixel"] is not None:
            report(
                "floor_calibration",
                "Metric scale has no measurements; clear/recalibrate it.",
                "floors",
                [identity],
            )
        elif visible:
            report(
                "uncalibrated_floor",
                "Plan is display-only: no indoor metric distance/ETA. Acknowledge and supply verified calibration before later metric routing.",
                "floors",
                [identity],
                "warning",
            )
        if visible and not full.get("floor_routing", {}).get(identity, {}).get("enabled"):
            report(
                "indoor_display_only",
                "Floor remains display-only until topology evidence and explicit routing capability are enabled and reviewed.",
                "floors",
                [identity],
                "warning",
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
    from app.services.connections import route_evidence_requirements
    from app.services.connections import validation as connection_validation

    connection_quality = connection_validation(db, revision)
    findings.extend(connection_quality["diagnostics"])
    if connection_quality["truncated"]:
        report(
            "connection_budget",
            "Connection diagnostics are incomplete; reduce unresolved findings.",
        )
    projected = public_projection(full)
    from app.core.config import get_settings
    from app.routing.mixed import compute

    evidence = []
    if not {"shortest", "step_free"}.issubset({r.profile for r in payload.routes}):
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
            try:
                computed = compute(
                    projected,
                    str(expected.source),
                    str(expected.target),
                    expected.profile,
                    expected.cost_mode,
                    get_settings().walking_speed_mps,
                )
                actual = {
                    "found": True,
                    "distance_m": computed["distance_m"],
                    "estimated_duration_s": computed["estimated_duration_s"],
                    "cost_units": computed["cost_units"],
                    "optimization_cost": computed["optimization_cost"],
                    "edge_ids": [s["edge_id"] for s in computed["segments"]],
                }
            except DomainError as exc:
                if exc.code not in {
                    "no_route",
                    "no_verified_step_free_route",
                    "location_not_routable",
                }:
                    raise
                actual = {"found": False, "distance_m": None, "edge_ids": [], "reason": exc.message}
            matched = actual["found"] == expected.expected_found and (
                expected.maximum_distance_m is None
                or (
                    actual["found"]
                    and actual["distance_m"] is not None
                    and actual["distance_m"] <= expected.maximum_distance_m
                )
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
    findings.extend(route_evidence_requirements(full, evidence))
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
            | AuditEvent.action.in_(
                [
                    "floor.create",
                    "floor.update",
                    "floor.delete",
                    "floor.calibrate",
                    "floorplan.upload",
                    "floorplan.apply",
                    "indoor.patch",
                    "connections.patch",
                ]
            )
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
    for source in review_sources(full).values():
        if source["approved_by"]:
            source_reviewer = db.get(User, UUID(source["approved_by"]))
            if (
                not source_reviewer
                or not source_reviewer.active
                or "source_approve" not in permissions(db, source_reviewer.id, revision.campus_id)
            ):
                raise DomainError(
                    "approval_revoked",
                    "A source reviewer is no longer authorized; obtain a fresh source review and validation.",
                    409,
                )
    for floor in full["floors"].values():
        if floor["visibility"] != "public" or not floor["frame_id"]:
            continue
        calibration = full["frames"][floor["frame_id"]]["calibration"]
        if calibration and calibration.get("reviewer"):
            calibration_reviewer = db.get(
                User, UUID(calibration["reviewer"]), populate_existing=True
            )
            if (
                not calibration_reviewer
                or not calibration_reviewer.active
                or "source_approve"
                not in permissions(db, calibration_reviewer.id, revision.campus_id)
            ):
                raise DomainError(
                    "approval_revoked",
                    "A calibration reviewer is no longer authorized; return to draft for fresh calibration review/validation.",
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
    from app.services.qr import reconcile

    reconcile(db, release, artifact, actor, request_id)
    from app.services.closures import reconcile as reconcile_closures

    overlay_version = reconcile_closures(db, release, artifact, actor, request_id)
    submission.status = "published"
    result = {
        "release_id": str(release.id),
        "closure_overlay_version": overlay_version,
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
        or target.publication_order >= current.publication_order
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
    from app.services.mixed_routes import release_projection
    from app.services.qr import reconcile

    reconcile(db, target, release_projection(db, target), actor, request_id)
    from app.services.closures import reconcile as reconcile_closures

    overlay_version = reconcile_closures(
        db, target, release_projection(db, target), actor, request_id
    )
    active.release_id = target.id
    result = {
        "release_id": str(target.id),
        "previous_release_id": str(current.id),
        "closure_overlay_version": overlay_version,
    }
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
        after={**result, "reason": payload.reason, "closure_overlay_version": overlay_version},
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
