"""Read-only MUJ published naming preflight; optional explicit source-supported draft rename.

No guessed names, draft creation, graph repair, source approval or publication.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

from app.cli.indoor_demo import Client, DemoError, persist, prompt_login
from app.core.config import get_settings
from app.schemas.admin import PlaceFields
from app.schemas.graph import GraphNodeFields
from app.services.muj_naming import INVENTORY
from app.services.muj_setup import CAMPUS_ID

MODELS = {"places": PlaceFields, "nodes": GraphNodeFields}
LABELS = {"places": "name", "nodes": "label"}


def supported_changes():
    inventory = json.loads(INVENTORY.read_bytes())
    return [
        r
        for r in inventory["records"]
        if r["entity"] in MODELS and r["proposed_name"] and r["current_label"] != r["proposed_name"]
    ]


def published(client):
    path = f"/api/v1/campuses/{CAMPUS_ID}/release"
    release = client.request("GET", path)
    checksum = release.get("artifact_checksum")
    try:
        identity = str(UUID(release["id"]))
        valid = len(bytes.fromhex(checksum)) == 32
    except (KeyError, ValueError, TypeError):
        valid = False
    if not valid or release.get("campus_id") != str(CAMPUS_ID):
        raise DemoError("A checksummed published MUJ artifact is required; no writes.")
    artifact_path = f"/api/v1/campuses/{CAMPUS_ID}/artifacts/{identity}/{checksum}.json"
    if release.get("artifact_url") != artifact_path:
        raise DemoError("Unexpected artifact URL; no writes.")
    raw = client.request("GET", artifact_path, binary=True)
    if hashlib.sha256(raw).hexdigest() != checksum:
        raise DemoError("Public artifact checksum mismatch; no writes.")
    data = json.loads(raw)
    if data.get("campus", {}).get("id") != str(CAMPUS_ID) or data.get("audience") != "public":
        raise DemoError("Unexpected public artifact identity; no writes.")
    if client.request("GET", path) != release:
        raise DemoError("Published release/restrictions changed during preflight; rerun read-only.")
    return release, data


def writable(entity, row):
    model = MODELS[entity]
    return model.model_validate({k: row[k] for k in model.model_fields if k in row}).model_dump(
        mode="json"
    )


def preflight(client, draft=None):
    release, data = published(client)
    graph = None
    if draft:
        graph = client.request("GET", f"/api/v1/admin/campuses/{CAMPUS_ID}/drafts/{draft}/graph")
    inventory = json.loads(INVENTORY.read_bytes())
    report = {
        "format": "scns-muj-naming-preflight-v1",
        "campus_id": str(CAMPUS_ID),
        "release": release,
        "source_sha256": inventory["source_sha256"],
        "draft_id": str(draft) if draft else None,
        "draft_version": graph["revision_version"] if graph else None,
        "inventory": [],
        "changes": [],
        "blockers": [],
        "qualification": "Source-only names; no field/main/accessibility/institutional approval. No publication. Unresolved identities require owner identification.",
    }
    for r in inventory["records"]:
        row = data.get(r["entity"], {}).get(r["id"])
        key = LABELS.get(r["entity"], "name")
        report["inventory"].append(
            {
                "entity": r["entity"],
                "id": r["id"],
                "marker": r["marker"],
                "pinned_label": r["current_label"],
                "published_label": row.get(key) if row else None,
                "present_in_release": row is not None,
                "proposed_name": r["proposed_name"],
                "reason": r["reason"],
                "confidence": r["confidence"],
            }
        )
    for r in supported_changes():
        entity, identity, label = r["entity"], r["id"], LABELS[r["entity"]]
        baseline = data.get(entity, {}).get(identity)
        current = graph.get(entity, {}).get(identity) if graph else baseline
        if not baseline or not current:
            report["blockers"].append(
                f"Missing published/draft {entity}/{identity}; no guessed reconstruction."
            )
            continue
        # Identity is proven by the exact source member, never a nearby footprint.
        if baseline["point"] != r["point"] or current["point"] != r["point"]:
            report["blockers"].append(f"Moved source member {identity}; preserve and reassess.")
        for row in (baseline, current):
            if row[label] not in {r["current_label"], r["proposed_name"]}:
                report["blockers"].append(
                    f"Owner label differs at {identity}; preserve it and stop."
                )
        for field in ("building_id", "kind") if entity == "places" else ("frame_id",):
            if current[field] != baseline[field]:
                report["blockers"].append(
                    f"Draft association/frame changed at {identity}; reassess."
                )
        if current[label] != r["proposed_name"]:
            before = writable(entity, current) if graph else None
            after = {**before, label: r["proposed_name"]} if before else None
            report["changes"].append(
                {
                    "entity": entity,
                    "id": identity,
                    "marker": r["marker"],
                    "before_label": current[label],
                    "after_label": r["proposed_name"],
                    "before": before,
                    "after": after,
                    "source_reason": r["reason"],
                }
            )
    if graph:
        # Bind the exact place to its actual entrance node, preserving all anchors.
        place = next(r["id"] for r in supported_changes() if r["entity"] == "places")
        node = next(r["id"] for r in supported_changes() if r["entity"] == "nodes")
        for rows in (data, graph):
            if not any(
                a["place_id"] == place and a["node_id"] == node for a in rows["anchors"].values()
            ):
                report["blockers"].append(
                    "Source entrance anchor changed/missing; no automatic repair."
                )
    return report


def apply_reviewed(client, preview, record_write):
    if not preview["draft_id"] or preview["blockers"]:
        raise DemoError("An explicitly selected editable draft and unblocked preview are required.")
    fresh = preflight(client, preview["draft_id"])
    if fresh != preview:
        raise DemoError(
            "Evidence/version changed after preview; preserve work and rerun read-only."
        )
    expected = preview["draft_version"]
    base = f"/api/v1/admin/campuses/{CAMPUS_ID}/drafts/{preview['draft_id']}"
    for change in preview["changes"]:
        # Full fresh version and fields before each normal transaction, including
        # between catalog and graph calls. A partial success is safely resumable.
        state = preflight(client, preview["draft_id"])
        if (
            state["blockers"]
            or state["release"] != preview["release"]
            or state["draft_version"] != expected
        ):
            raise DemoError(
                "Concurrent draft/release change; stopped, preserving any completed names."
            )
        if change not in state["changes"]:
            raise DemoError("Affected input changed; stopped without overwriting owner work.")
        headers = {"If-Match": f'"{expected}"'}
        if change["entity"] == "places":
            result = client.request(
                "PUT",
                base + f"/catalog/places/{change['id']}",
                {"entity": "places", "data": change["after"]},
                headers=headers,
            )
        else:
            result = client.request(
                "POST",
                base + "/graph",
                {"changes": [{"entity": "nodes", "id": change["id"], "data": change["after"]}]},
                headers=headers,
            )
        expected = result["revision_version"]
        record_write(
            {
                "receipt_type": "application",
                "change": change,
                "revision_version": expected,
                "audit_request_id": client.last_request_id,
            }
        )
    final = preflight(client, preview["draft_id"])
    if (
        final["changes"]
        or final["blockers"]
        or final["draft_version"] != expected
        or final["release"] != preview["release"]
    ):
        raise DemoError("Final state changed; rerun read-only. No automatic publication.")
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--draft",
        type=UUID,
        help="Explicit existing editable naming draft; otherwise published read-only",
    )
    parser.add_argument(
        "--apply-source-name",
        action="store_true",
        help="Only the source-supported E22 auditorium name; requires preview and explicit APPLY NAMES",
    )
    args = parser.parse_args()
    if args.apply_source_name and not args.draft:
        parser.error("--apply-source-name requires --draft; no draft is created automatically")
    client = Client(origin=os.environ.get("PUBLIC_APP_URL", "http://localhost:5173"))
    attempted = False
    try:
        prompt_login(client, "MUJ editor/owner")
        user = str(UUID(client.session["user_id"]))  # Real SessionOut shape.
        preview = preflight(client, args.draft)
        folder = Path(get_settings().storage_root) / "private/muj-naming" / user
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        report = folder / f"preflight-{uuid4()}.json"
        persist(report, preview)
        print(
            f"Read-only preflight: release {preview['release']['id']}, checksum {preview['release']['artifact_checksum']}; draft version {preview['draft_version']}. Report: {report}"
        )
        for c in preview["changes"]:
            print(
                f"{c['marker']} {c['entity']}/{c['id']}: {c['before_label']} -> {c['after_label']}"
            )
        print(
            f"{len(preview['blockers'])} blockers. Unresolved identities remain unchanged; review the numbered atlas."
        )
        if preview["blockers"]:
            raise DemoError("Naming preflight blocked; inspect report. No dataset writes.")
        if not args.apply_source_name:
            return
        if not preview["changes"]:
            print(
                "Names already present: verified current state only; zero dataset writes/audits this run."
            )
            return
        if (
            input(
                "Inspect the exact private report. Type APPLY NAMES to rename only E22 in this draft: "
            ).strip()
            != "APPLY NAMES"
        ):
            print("Stopped at preview; no dataset writes.")
            return
        attempted = True

        def receipt(item):
            persist(
                folder / f"receipt-{uuid4()}.json",
                {
                    **item,
                    "requested_by": user,
                    "draft_id": str(args.draft),
                    "release_id": preview["release"]["id"],
                },
            )

        apply_reviewed(client, preview, receipt)
        print(
            "Source-supported names saved in draft only. Review/validation/publication remain explicit and separate."
        )
    except (DemoError, ValueError, KeyError, OSError, TypeError):
        if attempted:
            print(
                "A name transaction may have succeeded. Preserve the draft; rerun WITHOUT --apply-source-name to verify partial/current state. Exact already-present names are no-ops; no original audit evidence is invented."
            )
        raise SystemExit(
            "Naming helper stopped safely; inspect the private report/API status. No credentials printed, no bypass or publication."
        ) from None
    finally:
        client.logout()


if __name__ == "__main__":
    main()
