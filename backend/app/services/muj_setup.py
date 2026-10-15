"""Bounded additive provisioning of the pinned MUJ preparation, never publication."""

import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func, select, text

from app.cli.dataset import geometry
from app.core.errors import DomainError
from app.models import Campus, Revision
from app.models.admin import AuditEvent, RoleAssignment
from app.schemas.api import Point, Polygon
from app.schemas.publication import SourceInput
from app.services.admin_auth import audit
from app.services.admin_catalog import create_draft
from app.services.osm_conversion import ATTRIBUTION, VERSION
from app.services.publication import add_source

ROOT = Path(__file__).resolve().parents[3] / "data/muj"
CAMPUS_ID = uuid5(NAMESPACE_URL, "scns-campus:MUJ:osm-preparation-v1")


def prepared(root=ROOT):
    manifest = json.loads((root / "manifest.json").read_bytes())
    for name, checksum in manifest["files"].items():
        if (
            Path(name).name != name
            or hashlib.sha256((root / name).read_bytes()).hexdigest() != checksum
        ):
            raise ValueError(
                "Pinned MUJ preparation checksum mismatch; regenerate and review the complete preparation"
            )
    return manifest, json.loads((root / "campus.json").read_bytes())


def provision(db, actor, request_id):
    """Caller must authorize system administration before entry, under normal CSRF/session."""
    manifest, config = prepared()
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('scns-provision-MUJ-v1'))"))
    campus = db.scalar(select(Campus).where((Campus.code == "MUJ") | (Campus.id == CAMPUS_ID)))
    prior = db.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "campus.muj_provision", AuditEvent.campus_id == CAMPUS_ID
        )
    )
    if campus:
        if (
            campus.id != CAMPUS_ID
            or not prior
            or prior.after.get("source_sha256") != manifest["source_sha256"]
        ):
            raise DomainError(
                "conflict",
                "MUJ already exists with different provenance; nothing overwritten. Resolve with the campus owner.",
                409,
            )
        if not db.get(RoleAssignment, (actor.id, CAMPUS_ID, "system_admin")):
            raise DomainError(
                "access_denied",
                "This preparation is already owned. Ask its system administrator for a normal MUJ campus grant.",
                403,
            )
        revision = db.get(Revision, prior.revision_id)
        if not revision or revision.status != "draft":
            raise DomainError(
                "conflict",
                "The prepared MUJ draft is no longer editable. Do not rerun over reviewed or released data.",
                409,
            )
        return {
            "campus_id": str(CAMPUS_ID),
            "draft_id": str(revision.id),
            "edit_version": revision.edit_version,
            "source_sha256": manifest["source_sha256"],
            "created": False,
        }
    boundary = geometry(Polygon.model_validate(config["boundary"]))
    if not db.scalar(select(func.ST_IsValid(boundary))):
        raise DomainError("invalid_input", "Prepared campus extent is invalid.")
    campus = Campus(
        id=CAMPUS_ID,
        code="MUJ",
        name=config["name"],
        timezone=config["timezone"],
        is_demo=False,
        center=geometry(Point.model_validate(config["center"])),
        boundary=boundary,
    )
    db.add(campus)
    db.flush()
    db.add(RoleAssignment(user_id=actor.id, campus_id=CAMPUS_ID, role="system_admin"))
    db.flush()
    draft = create_draft(db, CAMPUS_ID, actor.id, request_id, key=VERSION)
    revision = db.get(Revision, draft.id)
    add_source(
        db,
        revision,
        SourceInput(
            title="MUJ OpenStreetMap export — unverified preparation",
            rights="authorized",
            provenance=f"Owner-supplied OpenStreetMap XML SHA256 {manifest['source_sha256']}; {VERSION}. ODbL licensed source, not official MUJ data/field survey. Exact academic and hostel polygons; enclosing display extent includes an unclaimed gap. Indoor and grade-separated routing quarantined. Source rights/public audience still require independent review.",
            attribution=ATTRIBUTION,
            original=json.loads((ROOT / "coverage.geojson").read_bytes()),
            original_filename="muj-osm-coverage.geojson",
            display_overlay=True,
        ),
        actor,
        request_id,
    )
    audit(
        db,
        "campus.muj_provision",
        request_id,
        actor_id=actor.id,
        campus_id=CAMPUS_ID,
        revision_id=revision.id,
        resource_id=CAMPUS_ID,
        after={
            "source_sha256": manifest["source_sha256"],
            "converter": VERSION,
            "timezone": config["timezone"],
            "is_demo": False,
            "extent_policy": "display hull; exact coverage retained as unapproved source",
            "owner_role": "system_admin",
        },
    )
    return {
        "campus_id": str(CAMPUS_ID),
        "draft_id": str(revision.id),
        "edit_version": revision.edit_version,
        "source_sha256": manifest["source_sha256"],
        "created": True,
    }
