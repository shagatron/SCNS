"""Bounded staging and savepoint dry runs. Only apply writes to draft entities."""

import csv
import hashlib
import io
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from geoalchemy2 import Geography
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import cast, func, select, text
from sqlalchemy.exc import DBAPIError

from app.cli.dataset import geometry
from app.core.config import get_settings
from app.core.errors import DomainError
from app.models import Campus, Edge, Frame, Node, Revision
from app.models.admin import Department, DepartmentPlace
from app.models.imports import ImportBinding
from app.schemas.admin import CatalogWrite
from app.schemas.imports import (
    DepartmentPlaceFields,
    EdgeFields,
    FrameFields,
    ImportOptions,
    NodeFields,
)
from app.services.admin_auth import audit
from app.services.admin_catalog import (
    MODELS,
    claim_version,
    get_draft,
    record,
    referenced,
    write_record,
)

MODELS = {
    **MODELS,
    "frames": Frame,
    "nodes": Node,
    "edges": Edge,
    "department_places": DepartmentPlace,
}
ORDER = [
    "frames",
    "buildings",
    "places",
    "nodes",
    "edges",
    "departments",
    "department_places",
    "aliases",
    "anchors",
]
REFS = {
    "building_id": "buildings",
    "frame_id": "frames",
    "place_id": "places",
    "node_id": "nodes",
    "from_node_id": "nodes",
    "to_node_id": "nodes",
    "department_id": "departments",
    "physical_path_id": "physical_paths",
}
EXTERNAL = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
CATALOG = TypeAdapter(CatalogWrite)


def stable_id(campus_id, entity, external_id):
    return uuid5(NAMESPACE_URL, f"scns-import-v1:{campus_id}:{entity}:{external_id}")


def storage_dir():
    path = Path(get_settings().storage_root).resolve() / "private" / "imports"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def private_path(job):
    if not re.fullmatch(r"[0-9a-f]{32}\.upload", job.storage_key):
        raise ValueError("Invalid internal storage key")
    return storage_dir() / job.storage_key


def transition(job, state, actor=None):
    now = datetime.now(UTC)
    job.state = state
    job.updated_at = now
    job.history = [
        *job.history,
        {"state": state, "at": now.isoformat(), "actor_id": str(actor) if actor else None},
    ][-100:]


def log(db, job, action, actor, request_id, details=None):
    audit(
        db,
        f"import.{action}",
        request_id,
        actor_id=actor,
        campus_id=job.campus_id,
        revision_id=job.revision_id,
        resource_id=job.id,
        after={"checksum": job.checksum, "state": job.state, **(details or {})},
    )


def strict_json(value):
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError(f"Duplicate JSON field: {key[:64]}")
            result[key] = item
        return result

    return json.loads(
        value,
        object_pairs_hook=pairs,
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError("Non-finite JSON number")),
    )


def parse_content(raw, options, campus):
    """The same parser powers the worker and offline validation CLI."""
    text = raw.decode("utf-8-sig")
    if "\x00" in text:
        raise ValueError("Binary/NUL content is not a supported text dataset")
    if options.campus_code != campus.code or options.timezone != campus.timezone:
        raise ValueError("Campus code/timezone do not match the target campus")
    if options.format == "csv":
        csv.field_size_limit(get_settings().import_byte_limit)
        reader = csv.DictReader(io.StringIO(text, newline=""))
        if (
            not reader.fieldnames
            or len(reader.fieldnames) != len(set(reader.fieldnames))
            or len(reader.fieldnames) > 40
        ):
            raise ValueError("CSV needs unique headers (at most 40)")
        rows = []
        for number, row in enumerate(reader, 2):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"CSV row {number}: column count does not match headers")
            rows.append({"entity": options.entity, "_row": number, **row})
            if len(rows) > get_settings().import_row_limit:
                raise ValueError("Row limit exceeded; split the upload into related bundles")
    else:
        value = strict_json(text)
        if not isinstance(value, dict):
            raise ValueError("Expected a versioned JSON object or GeoJSON FeatureCollection")
        if options.format == "geojson":
            if value.get("type") != "FeatureCollection" or "crs" in value:
                raise ValueError("GeoJSON must be an RFC 7946 WGS84 FeatureCollection without crs")
            rows = []
            for number, feature in enumerate(value.get("features", []), 1):
                if (
                    not isinstance(feature, dict)
                    or feature.get("type") != "Feature"
                    or not isinstance(feature.get("properties"), dict)
                ):
                    raise ValueError(f"Feature {number}: expected Feature with properties")
                row = dict(feature["properties"])
                entity = row.get("entity", options.entity)
                field = {
                    "buildings": "footprint",
                    "places": "point",
                    "nodes": "point",
                    "edges": "geometry",
                }.get(entity)
                if not field:
                    raise ValueError(f"Feature {number}: entity does not accept outdoor geometry")
                row[field] = feature.get("geometry")
                rows.append({"entity": entity, "_row": number, **row})
        else:
            required = {
                "schema_version": "import-v1",
                "units": options.units,
                "campus_code": campus.code,
                "timezone": campus.timezone,
            }
            if any(value.get(key) != expected for key, expected in required.items()):
                raise ValueError("Bundle metadata must match import-v1, units, campus and timezone")
            if not isinstance(value.get("records"), list):
                raise ValueError("Bundle requires a records array")
            rows = [
                {"_row": n, **row}
                for n, row in enumerate(value["records"], 1)
                if isinstance(row, dict)
            ]
            if len(rows) != len(value["records"]):
                raise ValueError("Each record must be an object")
    if not 1 <= len(rows) <= get_settings().import_row_limit:
        raise ValueError("Upload is empty or exceeds the row limit")
    return rows


def snapshot(db, entity, row):
    if entity in {"buildings", "places", "departments", "aliases", "anchors"}:
        return record(db, entity, row).model_dump(mode="json")["item"]["data"]
    data = {
        column.name: getattr(row, column.name)
        for column in row.__table__.columns
        if column.name
        not in {
            "id",
            "campus_id",
            "dataset_revision_id",
            "point",
            "geometry",
            "x_px",
            "y_px",
            "width_px",
            "height_px",
            "metres_per_pixel",
            "calibration",
        }
    }
    for field in {"point", "geometry"}:
        if hasattr(row, field):
            data[field] = json.loads(db.scalar(select(func.ST_AsGeoJSON(getattr(row, field), 15))))
    return json.loads(json.dumps(data, default=str))


def resolve_id(db, revision, entity, value, targets):
    value = str(value)
    if (entity, value) in targets:
        return targets[entity, value]
    binding = db.scalar(
        select(ImportBinding).where(
            ImportBinding.dataset_revision_id == revision.id,
            ImportBinding.entity == entity,
            ImportBinding.external_id == value,
        )
    )
    if binding:
        return binding.record_id
    try:
        return UUID(value)
    except ValueError:
        if not EXTERNAL.fullmatch(value):
            raise ValueError("External references use 1–120 letters, digits, _, ., :, -") from None
        return stable_id(revision.campus_id, entity, value)


def normalize_rows(db, revision, rows, options):
    targets, seen, result = {}, set(), []
    for source in rows:
        item = {
            "row": source["_row"],
            "entity": source.get("entity", options.entity),
            "external_id": "",
            "action": "invalid",
            "errors": [],
            "warnings": [],
        }
        result.append(item)
        try:
            entity = item["entity"]
            if entity not in MODELS:
                raise ValueError(
                    "Unsupported entity; indoor floors/connectors are a later milestone"
                )
            source_data = source.get("data", source)
            if not isinstance(source_data, dict):
                raise ValueError("Record data must be an object")
            mapped = dict(source_data)
            for target, column in options.mapping.items():
                if column not in source_data:
                    raise ValueError(f"Mapped source column {column} is missing")
                mapped[target] = source_data[column]
                if column != target:
                    mapped.pop(column, None)
            external = mapped.get("external_id", source.get("external_id", ""))
            item["external_id"] = str(external)
            if not isinstance(external, str) or not EXTERNAL.fullmatch(external):
                raise ValueError("external_id is required: 1–120 letters, digits, _, ., :, -")
            if (entity, external) in seen:
                raise ValueError("Duplicate external_id in this batch")
            seen.add((entity, external))
            if mapped.get("campus_code", options.campus_code) != options.campus_code or mapped.get(
                "campus_id", str(revision.campus_id)
            ) != str(revision.campus_id):
                raise ValueError("Row belongs to another campus")
            binding = db.scalar(
                select(ImportBinding).where(
                    ImportBinding.dataset_revision_id == revision.id,
                    ImportBinding.entity == entity,
                    ImportBinding.external_id == external,
                )
            )
            adopted = source.get("existing_id") or mapped.get("existing_id")
            identity = (
                UUID(adopted)
                if adopted
                else (
                    binding.record_id
                    if binding
                    else stable_id(revision.campus_id, entity, external)
                )
            )
            if binding and binding.record_id != identity:
                raise ValueError("external_id is already bound to a different record")
            if adopted:
                referenced(db, MODELS[entity], revision.id, identity)
            if identity in [target for (kind, _), target in targets.items() if kind == entity]:
                raise ValueError("Multiple external IDs target the same record in this batch")
            targets[entity, external] = identity
            item["id"] = str(identity)
            item["data"] = {
                k: v
                for k, v in mapped.items()
                if k
                not in {
                    "entity",
                    "_row",
                    "external_id",
                    "existing_id",
                    "campus_code",
                    "campus_id",
                    "data",
                }
            }
        except (ValueError, TypeError, DomainError) as exc:
            item["errors"].append(exc.message if isinstance(exc, DomainError) else str(exc))
    for item in result:
        if item["errors"]:
            continue
        try:
            data = item["data"]
            for key, entity in REFS.items():
                if data.get(key) not in (None, ""):
                    data[key] = str(resolve_id(db, revision, entity, data[key], targets))
                elif key in data:
                    data[key] = None
            if "place_ids" in data:
                values = (
                    strict_json(data["place_ids"])
                    if isinstance(data["place_ids"], str)
                    else data["place_ids"]
                )
                data["place_ids"] = [
                    str(resolve_id(db, revision, "places", v, targets)) for v in values
                ]
            for field in ("point", "geometry", "footprint"):
                if field in data and isinstance(data[field], str):
                    data[field] = strict_json(data[field])
            for field in ("is_open",):
                if field in data and isinstance(data[field], str):
                    if data[field].lower() not in {"true", "false"}:
                        raise ValueError("is_open must be true or false")
                    data[field] = data[field].lower() == "true"
            if item["entity"] == "departments" and "place_ids" not in data:
                existing = db.get(Department, (revision.id, UUID(item["id"])))
                if existing:
                    data["place_ids"] = snapshot(db, "departments", existing)["place_ids"]
            if item["entity"] in {"frames", "nodes", "edges", "department_places"}:
                schema = {
                    "frames": FrameFields,
                    "nodes": NodeFields,
                    "edges": EdgeFields,
                    "department_places": DepartmentPlaceFields,
                }[item["entity"]]
                data = schema.model_validate(data).model_dump(mode="json")
            else:
                data = CATALOG.validate_python(
                    {"entity": item["entity"], "data": data}
                ).data.model_dump(mode="json")
            item["data"] = data
        except (ValueError, TypeError, ValidationError, DomainError) as exc:
            if isinstance(exc, ValidationError):
                item["errors"] = [
                    f"{'.'.join(map(str, e['loc']))}: {e['msg']}"
                    for e in exc.errors(include_input=False, include_url=False)
                ][:20]
            else:
                item["errors"].append(str(exc))
    return result


def write_item(db, revision, item):
    entity, identity, data = item["entity"], UUID(item["id"]), item["data"]
    model = MODELS[entity]
    existing = db.get(model, (revision.id, identity))
    shape_field = {
        "places": "point",
        "buildings": "footprint",
        "nodes": "point",
        "edges": "geometry",
    }.get(entity)
    if shape_field:
        candidate = func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(data[shape_field])), 4326)
        if not db.scalar(
            select(func.ST_Covers(Campus.boundary, candidate)).where(
                Campus.id == revision.campus_id
            )
        ):
            raise ValueError(
                "Geometry falls outside the target campus boundary; correct coordinates or campus association."
            )
    if entity in {"buildings", "places", "departments", "aliases", "anchors"}:
        row, _, _ = write_record(
            db,
            revision,
            CATALOG.validate_python({"entity": entity, "data": data}),
            identity if existing else None,
            create_id=identity,
        )
    else:
        row = existing or model(
            id=identity, campus_id=revision.campus_id, dataset_revision_id=revision.id
        )
        values = dict(data)
        for key in REFS:
            if key in values:
                values[key] = UUID(values[key])
        if entity == "frames":
            if db.scalar(
                select(Frame.id)
                .where(
                    Frame.dataset_revision_id == revision.id,
                    Frame.code == values["code"],
                    Frame.id != identity,
                )
                .limit(1)
            ):
                raise ValueError(
                    "Duplicate coordinate-frame code; explicitly adopt the intended existing frame."
                )
        if entity == "nodes":
            frame = referenced(db, Frame, revision.id, values["frame_id"])
            if frame.kind != "outdoor":
                raise ValueError(
                    "Nodes require an outdoor WGS84 frame; indoor import is not enabled"
                )
            values["point"] = geometry(NodeFields.model_validate(data).point)
            values.update(x_px=None, y_px=None)
        elif entity == "edges":
            payload = EdgeFields.model_validate(data)
            source = referenced(db, Node, revision.id, payload.from_node_id)
            target = referenced(db, Node, revision.id, payload.to_node_id)
            frame = referenced(db, Frame, revision.id, payload.frame_id)
            if (
                source.id == target.id
                or not (source.frame_id == target.frame_id == frame.id)
                or frame.kind != "outdoor"
            ):
                raise ValueError("Edge endpoints must be distinct nodes in the same outdoor frame")
            points = payload.geometry.coordinates
            if tuple(points[0]) != tuple(
                snapshot(db, "nodes", source)["point"]["coordinates"]
            ) or tuple(points[-1]) != tuple(snapshot(db, "nodes", target)["point"]["coordinates"]):
                raise ValueError("Polyline must follow its directed node endpoints")
            if payload.visibility == "public" and (
                source.visibility != "public" or target.visibility != "public"
            ):
                raise ValueError("Public edge cannot expose restricted endpoints")
            if payload.kind == "stairs" and payload.accessibility_status == "verified_step_free":
                raise ValueError("Stairs cannot be step-free")
            if (
                payload.accessibility_status == "verified_step_free"
                and not payload.evidence.strip()
            ):
                raise ValueError("Step-free edge needs dated source/survey evidence")
            shape = geometry(payload.geometry)
            values["geometry"] = shape
            values["distance_m"] = func.ST_Length(cast(shape, Geography))
        elif entity == "department_places":
            referenced(db, Department, revision.id, values["department_id"])
            referenced(db, MODELS["places"], revision.id, values["place_id"])
        for key, value in values.items():
            setattr(row, key, value)
        db.add(row)
        db.flush()
    # Re-check the complete outdoor graph, including dependents of changed nodes.
    if entity in {"nodes", "frames"}:
        for edge in db.scalars(
            select(Edge).where(
                Edge.dataset_revision_id == revision.id,
                ((Edge.from_node_id == identity) | (Edge.to_node_id == identity))
                if entity == "nodes"
                else Edge.frame_id == identity,
            )
        ):
            source = referenced(db, Node, revision.id, edge.from_node_id)
            target = referenced(db, Node, revision.id, edge.to_node_id)
            if not (source.frame_id == target.frame_id == edge.frame_id):
                raise ValueError("Node/frame update would invalidate an existing edge")
            if edge.visibility == "public" and (
                source.visibility != "public" or target.visibility != "public"
            ):
                raise ValueError("Node update would expose a restricted endpoint")
    return row


def final_graph_guard(db, revision):
    for model, limit in (
        (Node, get_settings().graph_node_limit),
        (Edge, get_settings().graph_edge_limit),
    ):
        if (
            db.scalar(
                select(func.count())
                .select_from(model)
                .where(model.dataset_revision_id == revision.id)
            )
            > limit
        ):
            raise ValueError("Draft exceeds configured graph limits; split/reduce the dataset.")
    invalid = db.scalar(
        text("""
        SELECT EXISTS (
          SELECT 1 FROM navigation_edges e
          JOIN navigation_nodes s ON s.dataset_revision_id=e.dataset_revision_id AND s.id=e.from_node_id
          JOIN navigation_nodes t ON t.dataset_revision_id=e.dataset_revision_id AND t.id=e.to_node_id
          WHERE e.dataset_revision_id=:revision AND (
            s.frame_id<>e.frame_id OR t.frame_id<>e.frame_id OR
            NOT ST_Equals(ST_StartPoint(e.geometry),s.point) OR
            NOT ST_Equals(ST_EndPoint(e.geometry),t.point) OR
            (e.visibility='public' AND (s.visibility<>'public' OR t.visibility<>'public')))
        ) OR EXISTS (
          SELECT 1 FROM place_anchors a
          JOIN places p ON p.dataset_revision_id=a.dataset_revision_id AND p.id=a.place_id
          JOIN navigation_nodes n ON n.dataset_revision_id=a.dataset_revision_id AND n.id=a.node_id
          WHERE a.dataset_revision_id=:revision AND p.visibility='public' AND n.visibility<>'public'
        )
    """),
        {"revision": revision.id},
    )
    if invalid:
        raise ValueError(
            "Batch would invalidate existing graph endpoints, frames or public anchor visibility. Include all dependent geometry changes in the same bundle."
        )


def stage(db, job):
    revision = get_draft(db, job.campus_id, job.revision_id)
    # Shared lock gives a coherent preview version and blocks all ordinary CAS edits.
    db.execute(select(Revision.id).where(Revision.id == revision.id).with_for_update(read=True))
    db.refresh(revision)
    options = ImportOptions.model_validate(job.options)
    path = private_path(job)
    raw = path.read_bytes()
    if (
        len(raw) > get_settings().import_byte_limit
        or hashlib.sha256(raw).hexdigest() != job.checksum
    ):
        raise ValueError("Private upload size/checksum verification failed")
    rows = normalize_rows(
        db, revision, parse_content(raw, options, db.get(Campus, job.campus_id)), options
    )
    started = time.monotonic()
    with db.begin_nested() as simulation:
        for item in sorted(
            rows, key=lambda x: ORDER.index(x["entity"]) if x["entity"] in ORDER else 99
        ):
            if time.monotonic() - started > get_settings().import_parse_seconds:
                raise ValueError("Validation time limit exceeded; split this batch")
            if item["errors"]:
                continue
            existing = db.get(MODELS[item["entity"]], (revision.id, UUID(item["id"])))
            item["before"] = snapshot(db, item["entity"], existing) if existing else None
            try:
                with db.begin_nested():
                    row = write_item(db, revision, item)
                    item["after"] = snapshot(db, item["entity"], row)
                    item["action"] = (
                        "unchanged"
                        if item["before"] == item["after"]
                        else ("update" if existing else "add")
                    )
                    if existing and item["action"] == "update" and options.policy == "create_only":
                        raise ValueError(
                            "Existing content differs: choose explicit upsert policy to update"
                        )
                    if item["entity"] in {"nodes", "edges", "anchors"}:
                        item["warnings"].append(
                            "Draft candidate only; geometry/accessibility needs field verification before any future publication."
                        )
            except (ValueError, DomainError, DBAPIError) as exc:
                if isinstance(exc, DBAPIError) and getattr(exc.orig, "sqlstate", None) not in {
                    "23503",
                    "23505",
                    "23514",
                    "P0001",
                }:
                    raise
                item["action"] = (
                    "conflict" if isinstance(exc, DBAPIError) or existing else "invalid"
                )
                item["errors"].append(
                    "Duplicate code/link or invalid database geometry/reference constraint. Use existing_id only to explicitly adopt the intended draft record."
                    if isinstance(exc, DBAPIError)
                    else (exc.message if isinstance(exc, DomainError) else str(exc))
                )
        try:
            final_graph_guard(db, revision)
        except ValueError as exc:
            for item in rows:
                if item["entity"] in {"nodes", "edges", "frames", "anchors"} and not item["errors"]:
                    item["errors"].append(str(exc))
                    item["action"] = "invalid"
        simulation.rollback()
    job.preview_version = revision.edit_version
    job.preview = {
        "counts": {
            key: sum(i["action"] == key for i in rows)
            for key in ("add", "update", "unchanged", "conflict", "invalid")
        },
        "rows": rows,
    }
    transition(job, "preview_ready")
    job.failure = None
    log(
        db,
        job,
        "preview",
        job.uploader_id,
        "import-worker",
        {"counts": job.preview["counts"], "version": job.preview_version},
    )


def process_job(db, job):
    try:
        with db.begin_nested():
            stage(db, job)
    except (
        ValueError,
        TypeError,
        KeyError,
        OSError,
        UnicodeError,
        csv.Error,
        RecursionError,
        DomainError,
    ) as exc:
        transition(job, "failed")
        job.failure = (exc.message if isinstance(exc, DomainError) else str(exc))[:2000]
        log(db, job, "failed", job.uploader_id, "import-worker", {"message": job.failure})


def apply_job(db, job, actor, request_id, header):
    if job.state == "committed":
        return  # Replayed apply is a read of the already-committed job, never another write.
    if job.state != "validated" or not job.preview:
        raise DomainError(
            "import_validation_failed", "Validate a clean preview before applying.", 409
        )
    revision = get_draft(db, job.campus_id, job.revision_id)
    if header != f'"{job.preview_version}"':
        raise DomainError("conflict", "Apply must use the exact preview version in If-Match.", 409)
    claim_version(db, revision, header)
    for item in sorted(job.preview["rows"], key=lambda x: ORDER.index(x["entity"])):
        if item["errors"]:
            raise DomainError("import_validation_failed", "Batch contains invalid rows.", 409)
        if item["action"] != "unchanged":
            write_item(db, revision, item)
        binding = db.scalar(
            select(ImportBinding).where(
                ImportBinding.dataset_revision_id == revision.id,
                ImportBinding.entity == item["entity"],
                ImportBinding.external_id == item["external_id"],
            )
        )
        if not binding:
            db.add(
                ImportBinding(
                    id=uuid4(),
                    campus_id=job.campus_id,
                    dataset_revision_id=revision.id,
                    entity=item["entity"],
                    external_id=item["external_id"],
                    record_id=UUID(item["id"]),
                )
            )
        audit(
            db,
            "import.record",
            request_id,
            actor_id=actor,
            campus_id=job.campus_id,
            revision_id=revision.id,
            resource_id=UUID(item["id"]),
            before=item.get("before"),
            after={
                "job_id": str(job.id),
                "entity": item["entity"],
                "external_id": item["external_id"],
                "action": item["action"],
                "data": item.get("after"),
            },
        )
    db.flush()
    try:
        final_graph_guard(db, revision)
    except ValueError as exc:
        raise DomainError("import_validation_failed", str(exc), 409) from None
    transition(job, "committed", actor)
    job.applier_id = actor
    log(
        db,
        job,
        "apply",
        actor,
        request_id,
        {
            "uploader_id": str(job.uploader_id),
            "counts": job.preview["counts"],
            "version": revision.edit_version,
        },
    )


def safe_csv_cell(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else value


def error_csv(job):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["row", "entity", "external_id", "action", "errors", "warnings"])
    for item in (job.preview or {}).get("rows", []):
        writer.writerow(
            [safe_csv_cell(item.get(key, "")) for key in ("row", "entity", "external_id", "action")]
            + [safe_csv_cell("; ".join(item.get(key, []))) for key in ("errors", "warnings")]
        )
    if job.failure:
        writer.writerow(["", "", "", "failed", safe_csv_cell(job.failure), ""])
    return output.getvalue()
