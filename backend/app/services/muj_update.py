"""Pure pinned v1 -> v2 graph patch planning. All writes use the normal graph API."""

import hashlib
import json
from pathlib import Path

from app.cli.indoor_demo import DemoError
from app.schemas.admin import AnchorFields
from app.schemas.graph import GraphNodeFields, GraphPatch
from app.schemas.imports import EdgeFields
from app.services.imports import stable_id
from app.services.muj_setup import CAMPUS_ID, ROOT, prepared
from app.services.osm_conversion import VERSION, VERSION2, encode

ROOT2 = ROOT.parent / "muj-v2"
FIELDS = {"nodes": GraphNodeFields, "edges": EdgeFields, "anchors": AnchorFields}
REFS = {
    "frame_id": "frames",
    "from_node_id": "nodes",
    "to_node_id": "nodes",
    "physical_path_id": "physical_paths",
    "place_id": "places",
    "node_id": "nodes",
}
MARKER = f"MUJ source-segment correction {VERSION2}"


def graph_records(root):
    manifest, _ = prepared(root)
    result = {entity: {} for entity in FIELDS}
    for filename in sorted(manifest["files"]):
        if not filename.startswith("batch-"):
            continue
        for row in json.loads((root / filename).read_bytes())["records"]:
            entity = row["entity"]
            if entity not in FIELDS:
                continue
            data = {
                k: str(stable_id(CAMPUS_ID, REFS[k], v)) if k in REFS else v
                for k, v in row["data"].items()
            }
            result[entity][str(stable_id(CAMPUS_ID, entity, row["external_id"]))] = (
                FIELDS[entity].model_validate(data).model_dump(mode="json")
            )
    return manifest, result


def correction():
    before_manifest, before = graph_records(ROOT)
    after_manifest, after = graph_records(ROOT2)
    if (
        before_manifest["converter"] != VERSION
        or after_manifest["converter"] != VERSION2
        or before_manifest["source_sha256"] != after_manifest["source_sha256"]
    ):
        raise DemoError("Unexpected correction source/version; nothing applied.")
    fingerprint = hashlib.sha256(encode(after_manifest)).hexdigest()
    changes = []
    for entity in FIELDS:
        for identity in sorted(set(before[entity]) | set(after[entity])):
            old, new = before[entity].get(identity), after[entity].get(identity)
            if old == new:
                continue
            if new:
                new = dict(new)
                evidence = "accessibility_evidence" if entity == "anchors" else "evidence"
                new[evidence] += (
                    f"\n{MARKER}; manifest SHA256 {fingerprint}; source-derived, not field verified."
                )
            changes.append({"entity": entity, "id": identity, "data": new})
    patch = GraphPatch.model_validate({"changes": changes}).model_dump(mode="json")
    return {
        "format": "scns-muj-graph-correction-v2",
        "campus_id": str(CAMPUS_ID),
        "source_sha256": before_manifest["source_sha256"],
        "from_manifest_sha256": hashlib.sha256(encode(before_manifest)).hexdigest(),
        "to_manifest_sha256": fingerprint,
        **patch,
    }, before


def comparable(entity, row):
    if row is None:
        return None
    # Reject unexpected coordinate/attribute changes, but ignore server-computed distance.
    return (
        FIELDS[entity]
        .model_validate({k: row[k] for k in FIELDS[entity].model_fields if k in row})
        .model_dump(mode="json")
    )


def plan(current, draft_id):
    patch, baseline = correction()
    changes = patch["changes"]
    complete = all(
        comparable(c["entity"], current[c["entity"]].get(c["id"])) == c["data"] for c in changes
    )
    # Every existing endpoint used by a new path must retain its pinned position/attributes.
    touched_nodes = {
        c["data"][field]
        for c in changes
        if c["entity"] == "edges" and c["data"]
        for field in ("from_node_id", "to_node_id")
    }
    for identity in touched_nodes:
        if (
            identity in baseline["nodes"]
            and comparable("nodes", current["nodes"].get(identity)) != baseline["nodes"][identity]
        ):
            raise DemoError(
                f"Owner edit or unexpected referenced node {identity}; preserve and reconcile manually. Nothing applied."
            )
    for c in changes:
        if not complete and comparable(c["entity"], current[c["entity"]].get(c["id"])) != baseline[
            c["entity"]
        ].get(c["id"]):
            raise DemoError(
                f"Owner edit, collision or partial/manual correction at {c['entity']}/{c['id']}; nothing applied."
            )
    added_anchors = [c["data"] for c in changes if c["entity"] == "anchors" and c["data"]]
    if any(a["place_id"] not in current["places"] for a in added_anchors):
        raise DemoError("Required existing catalog destination is missing; nothing applied.")
    return {
        **patch,
        "draft_id": str(draft_id),
        "revision_version": current["revision_version"],
        "state": "already_applied" if complete else "preview",
        "counts": {
            "add": sum(
                c["data"] is not None and c["id"] not in baseline[c["entity"]] for c in changes
            ),
            "update": sum(
                c["data"] is not None and c["id"] in baseline[c["entity"]] for c in changes
            ),
            "delete": sum(c["data"] is None for c in changes),
        },
        "qualification": "Draft only. No access, source approval, accessibility verification or publication inferred.",
    }


def apply_reviewed(client, preview):
    if str(preview["campus_id"]) != str(CAMPUS_ID):
        raise DemoError("Foreign campus correction refused.")
    path = f"/api/v1/admin/campuses/{CAMPUS_ID}/drafts/{preview['draft_id']}/graph"
    current = client.request("GET", path)
    fresh = plan(current, preview["draft_id"])
    if fresh["state"] == "already_applied":
        return fresh  # Ambiguous post/receipt loss or exact retry; no version/audit write.
    if fresh != preview:
        raise DemoError(
            "Draft/version or preparation changed since preview. Generate and review a new preview; do not overwrite."
        )
    client.request(
        "POST",
        path,
        {"changes": preview["changes"]},
        headers={"If-Match": f'"{preview["revision_version"]}"'},
    )
    return {
        **preview,
        "state": "applied",
        "audit_request_id": getattr(client, "last_request_id", None),
    }
