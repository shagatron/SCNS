"""Prepare exact MUJ review evidence; explicit submit/independent approve, never publish.

All dataset access uses the existing local authenticated HTTP API. No database,
source approval, validation creation, graph writes or publication capability.
"""

import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from uuid import UUID

from app.cli.indoor_demo import Client, DemoError, persist, prompt_login
from app.core.config import get_settings
from app.schemas.imports import ImportOptions
from app.schemas.publication import DecisionInput, SubmitInput
from app.services.imports import stable_id
from app.services.muj_setup import CAMPUS_ID, ROOT, prepared
from app.services.muj_update import comparable, correction, graph_records

PAIRS = [
    ["2355ef5c-c611-567d-9e5e-9bb983986b00", "b7823a47-64ca-50e1-8d8e-159c48273de4"],
    ["bb717aa9-1b70-516a-b1e5-f6e4df4134a0", "fd76f58a-b463-5d95-93f6-f952c4f999a2"],
]
NOTES = (
    "Limited local OSM academic preview only; not official MUJ data or a field survey. "
    "Reviewed source-derived topology, provenance and individual warning reasons. "
    "Only mapped eligible journeys are supported; Library, academic-hostel crossing and "
    "verified step-free gaps remain unavailable. Near-duplicate source stubs remain ambiguous, "
    "not physically certified separate. No institutional or accessibility approval is implied."
)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def place(osm):
    return str(stable_id(CAMPUS_ID, "places", "osm-node-" + osm))


def pinned_graph():
    _, graph = graph_records(ROOT)
    patch, _ = correction()
    for change in patch["changes"]:
        if change["data"] is None:
            graph[change["entity"]].pop(change["id"])
        else:
            graph[change["entity"]][change["id"]] = change["data"]
    return graph


def topology(graph, profile):
    adjacency, reverse, weak = defaultdict(set), defaultdict(set), defaultdict(set)
    for e in graph["edges"].values():
        if (
            e["visibility"] != "public"
            or not e["is_open"]
            or (
                profile == "step_free"
                and (e["kind"] == "stairs" or e["accessibility_status"] != "verified_step_free")
            )
        ):
            continue
        a, b = e["from_node_id"], e["to_node_id"]
        adjacency[a].add(b)
        reverse[b].add(a)
        weak[a].add(b)
        weak[b].add(a)

    def reach(edges, starts):
        found, queue = set(starts), list(starts)
        while queue:
            for target in edges[queue.pop()]:
                if target not in found:
                    found.add(target)
                    queue.append(target)
        return found

    entrances = defaultdict(set)
    for _, a in sorted(graph["anchors"].items()):
        if (
            a["is_open"]
            and graph["nodes"][a["node_id"]]["visibility"] == "public"
            and (profile == "shortest" or a["accessibility_status"] == "verified_step_free")
        ):
            entrances[a["place_id"]].add(a["node_id"])
    reference = next(iter(entrances), None)
    forward = reach(adjacency, entrances[reference]) if reference else set()
    backward = reach(reverse, entrances[reference]) if reference else set()
    remaining = {i for i, n in graph["nodes"].items() if n["visibility"] == "public"}
    components = []
    while remaining:
        component = reach(weak, {min(remaining)})
        remaining -= component
        components.append(sorted(component))
    return {
        "reference_place": reference,
        "components": components,
        "places": {
            i: {
                "anchors": sorted(entrances[i]),
                "reachable_from_reference": bool(entrances[i] & forward),
                "can_return_to_reference": bool(entrances[i] & backward),
            }
            for i in graph["places"]
        },
    }


def near_pairs(graph, connections):
    records = []
    for pair in PAIRS:
        groups = [next((c for c in connections["components"] if n in c), []) for n in pair]
        anchors = [i for i, a in graph["anchors"].items() if any(a["node_id"] in c for c in groups)]
        records.append(
            {
                "nodes": pair,
                "records": {n: graph["nodes"].get(n) for n in pair},
                "incident_edges": {
                    i: e
                    for i, e in graph["edges"].items()
                    if any(n in (e["from_node_id"], e["to_node_id"]) for n in pair)
                },
                "components": groups,
                "component_anchors": anchors,
                "assessment": "Distinct source IDs on ways1247085147/1271670518. Both source ways carry building:levels=0;1;2;3 without explicit level/indoor tags. Proximity does not prove a join, duplicate feature or physical separation. No merge/graph change proposed. Each retained two-node component has one mapped entrance. No distinct-place journey joins these stubs to the tested routes; a GPS start on a stub could still approach its own entrance. Physical/floor relationship remains unresolved.",
                "manual_assessment_required": True,
            }
        )
    return records


def collect(client, draft, validation=None):
    base = f"/api/v1/admin/campuses/{CAMPUS_ID}/drafts/{draft}"
    packet = client.request("GET", base + "/review")
    if packet["status"] == "draft":
        graph = client.request("GET", base + "/graph")
    else:
        # Editable graph API intentionally rejects review/frozen revisions. For this
        # original new-campus draft, the authenticated review diff contains every row.
        graph = {
            "revision_version": packet["edit_version"],
            **{
                layer: {
                    d["id"]: d["after"]
                    for d in packet["diff"]
                    if d["entity"] == layer and d["after"] is not None
                }
                for layer in ("nodes", "edges", "anchors", "places", "frames")
            },
        }
        if any(set(graph[k]) != set(v) for k, v in pinned_graph().items()):
            raise DemoError(
                "Locked review diff is not a complete original MUJ dataset; cannot infer missing rows. Use normal review UI/separate assessment."
            )
    active = next(
        (s for s in packet["submissions"] if s["status"] in {"submitted", "approved", "published"}),
        None,
    )
    identity = str(validation) if validation else active["validation_id"] if active else None
    run = (
        next((r for r in packet["validations"] if r["id"] == identity), None)
        if identity
        else next(
            (
                r
                for r in packet["validations"]
                if r["edit_version"] == packet["edit_version"]
                and r["checksum"] == packet["checksum"]
            ),
            None,
        )
    )
    jobs = []
    if run:
        for item in run["report"]["imports"]:
            job = client.request(
                "GET", f"/api/v1/admin/campuses/{CAMPUS_ID}/imports/{UUID(item['id'])}"
            )
            # Bounded metadata only; omit row/history payloads.
            jobs.append(
                {
                    k: job[k]
                    for k in (
                        "id",
                        "campus_id",
                        "revision_id",
                        "filename",
                        "checksum",
                        "options",
                        "state",
                        "uploader_id",
                        "applier_id",
                    )
                }
            )
    latest = client.request("GET", base + "/review")
    if (latest["id"], latest["edit_version"], latest["checksum"], latest["status"]) != (
        str(draft),
        packet["edit_version"],
        packet["checksum"],
        packet["status"],
    ) or graph["revision_version"] != packet["edit_version"]:
        raise DemoError(
            "Draft changed during preflight; nothing submitted. Rerun against fresh evidence."
        )
    return packet, graph, run, jobs, active


def prepare(packet, graph, run, jobs, active, draft, assessments=None):
    assessments = assessments or {}
    blockers, reasons = [], {}
    baseline = pinned_graph()
    for entity, rows in baseline.items():
        if set(rows) != set(graph[entity]) or any(
            comparable(entity, graph[entity].get(i)) != row for i, row in rows.items()
        ):
            blockers.append(
                f"{entity} differ from the reviewed v2 correction pin. Preserve edits; separate assessment required."
            )
    connections = {p: topology(graph, p) for p in ("shortest", "step_free")}
    pairs = near_pairs(graph, connections["shortest"])
    if not run:
        blockers.append(
            "No selected current validation; run authoritative validation in the UI. No automatic validation/write."
        )
    elif (
        run["checksum"] != packet["checksum"]
        or (packet["status"] == "draft" and run["edit_version"] != packet["edit_version"])
        or (packet["status"] != "draft" and (not active or run["id"] != active["validation_id"]))
    ):
        blockers.append(
            "Selected validation is stale or not bound to the active submission; revalidate/review normally."
        )
    if run and run["report"]["errors"]:
        blockers.append(
            "Authoritative validation has blocking errors; no acknowledgement can resolve them."
        )
    sources = packet["sources"]
    manifest, _ = prepared()
    if len(sources) != 1 or any(
        s["rights"] != "authorized"
        or not s["approved_by"]
        or s["approved_by"] == s["uploader_id"]
        or manifest["source_sha256"] not in s["provenance"]
        or "OpenStreetMap" not in s["attribution"]
        or "ODbL" not in s["attribution"]
        or not s["derivative"]
        for s in sources.values()
    ):
        blockers.append(
            "Expected independently approved authorized OSM source/coverage derivative and visible attribution missing/changed; inspect rights before proceeding."
        )
    options = ImportOptions.model_validate_json((ROOT / "options.json").read_bytes()).model_dump(
        mode="json"
    )
    expected_jobs = {
        name: sha for name, sha in manifest["files"].items() if name.startswith("batch-")
    }
    if (
        len(jobs) != 3
        or {j["filename"] for j in jobs} != set(expected_jobs)
        or any(
            j["checksum"] != expected_jobs.get(j["filename"])
            or j["state"] != "committed"
            or j["campus_id"] != str(CAMPUS_ID)
            or j["revision_id"] != str(draft)
            or not j["applier_id"]
            or j["options"] != options
            for j in jobs
        )
    ):
        blockers.append(
            "Applied import metadata is not exactly the three pinned committed v1 batches/options; inspect provenance, do not reimport."
        )
    diagnostics = run["report"]["diagnostics"] if run else []
    if run:
        required = [("shortest", True), ("step_free", False)]
        if not all(
            any(
                e["source"] == place("10780185181")
                and e["target"] == place("11573265515")
                and e["profile"] == p
                and e["expected_found"] == found
                and e["passed"]
                and e.get("cost_mode") == "directions_only"
                and e.get("maximum_distance_m") is None
                for e in run["evidence"]
            )
            for p, found in required
        ):
            blockers.append(
                "Validation must include Hostel Entrance -> GHS Entrance: standard found, verified step-free absent, Directions only, no maximum bound."
            )
    unhandled = []
    for d in diagnostics:
        if d["severity"] != "warning":
            continue
        ids, code = d["ids"], d["code"]
        reason = None
        if (
            code.startswith("connectivity_")
            and code.removeprefix("connectivity_") in connections
            and len(ids) == 1
            and ids[0] in graph["places"]
        ):
            profile = code.removeprefix("connectivity_")
            item = connections[profile]["places"][ids[0]]
            reason = (
                f"Limited local OSM preview: {graph['places'][ids[0]]['name']} ({ids[0]}). "
                f"{profile} validator uses reference place {connections[profile]['reference_place']}; stored entrance/reachability evidence {json.dumps(item, sort_keys=True)}. "
                "This is source-graph coverage, not proof of physical isolation. No missing connection is invented; unsupported arrivals stay unavailable. "
                + (
                    "No verified step-free chain is asserted; OSM accessibility remains unverified."
                    if profile == "step_free"
                    else "A warning relative to that reference does not mean all other place pairs lack a route; only explicitly mapped eligible journeys are offered."
                )
            )
        elif code == "unmapped_entrance" and len(ids) == 1 and ids[0] in graph["places"]:
            reason = (
                f"{graph['places'][ids[0]]['name']} ({ids[0]}) remains a source catalog/display point without an open mapped entrance anchor. "
                "No door, floor, centroid or nearest-path join is inferred. Directions to this destination remain unavailable in this limited OSM preview; field/source entrance evidence is required for a later separately reviewed change."
            )
        elif code in {"components_shortest", "components_step_free"}:
            p = code.removeprefix("components_")
            reason = (
                f"Stored {p} graph has {len(connections[p]['components'])} weak components. Limited OSM preparation preserves explicit source-node topology, access/coverage and unresolved grade/floor gaps; it does not establish physical separation. "
                "No proximity merges or cross-campus/subway shortcut; unknown accessibility stays excluded from verified step-free routing. Only eligible mapped journeys supported; no full-campus connectivity promise."
            )
        elif (
            code == "unknown_accessibility"
            and ids
            and all(graph["edges"].get(i, {}).get("accessibility_status") == "unknown" for i in ids)
        ):
            reason = "OSM-derived accessibility is unverified. Unknown paths stay excluded from verified step-free routing; source wheelchair tags and estimated lengths are not a physical survey. No wheelchair/accessibility suitability claim; verified step-free journeys remain unavailable until separately evidenced and reviewed."
        elif code == "import_provenance" and len(ids) == 1:
            job = next((j for j in jobs if j["id"] == ids[0]), None)
            if job:
                reason = (
                    f"Applied import {job['filename']} / job {job['id']} / SHA256 {job['checksum']}. "
                    "Matches pinned owner-supplied OSM v1 batch and recorded create-only options/actor; original remains private. Source is ODbL, not institutional/field-survey evidence. Separately versioned v2 correction preserves original receipts. Retain OpenStreetMap attribution and applicable derivative-data licensing obligations."
                )
        elif code == "near_duplicate":
            pair = next((p for p in pairs if set(p["nodes"]) == set(ids)), None)
            manual = assessments.get(d["id"], {})
            if (
                pair
                and manual.get("accept_limited_osm_preview") is True
                and all(
                    isinstance(manual.get(k), str) and 20 <= len(manual[k].strip()) <= 800
                    for k in ("reason", "evidence_reviewed")
                )
            ):
                reason = (
                    manual["reason"].strip()
                    + " Evidence reviewed: "
                    + manual["evidence_reviewed"].strip()
                )
        if reason:
            reasons[d["id"]] = reason
        else:
            unhandled.append(d)
    if unhandled:
        blockers.append(
            "Some findings have no justified template. Inspect them separately; no blanket acknowledgement permitted."
        )
    return {
        "draft_id": str(draft),
        "campus_id": str(CAMPUS_ID),
        "version": packet["edit_version"],
        "checksum": packet["checksum"],
        "status": packet["status"],
        "validation_id": run["id"] if run else None,
        "validation": run,
        "sources": sources,
        "imports": jobs,
        "topology": connections,
        "near_duplicate_pairs": pairs,
        "warning_counts": dict(
            Counter(d["code"] for d in diagnostics if d["severity"] == "warning")
        ),
        "unjustified_findings": unhandled,
        "blockers": blockers,
        "proposed_reasons": reasons,
        "existing_submissions": packet["submissions"],
        "scope": NOTES,
        "graph_sha256": digest(graph),
    }


def report_markdown(report, payload):
    lines = [
        "# MUJ local OSM publication preflight",
        f"Draft {report['draft_id']} | version {report['version']} | {report['status']}",
        f"Checksum {report['checksum']} | validation {report['validation_id']}",
        report["scope"],
        "This report is not approval. Source review is not institutional endorsement. No dataset write occurs during preflight.",
        "## Blockers",
        *[f"- {b}" for b in report["blockers"]],
        "## Warning counts",
        json.dumps(report["warning_counts"], indent=2),
        "## Source approval and exact import provenance",
        "```json",
        json.dumps({"sources": report["sources"], "imports": report["imports"]}, indent=2),
        "```",
        "## Near-duplicate source/topology evidence",
        "```json",
        json.dumps(report["near_duplicate_pairs"], indent=2),
        "```",
        "## Exact proposed payload (inspect every ID and reason; edit proposal.json to preserve your own wording)",
        "```json",
        json.dumps(payload, indent=2),
        "```",
        "## Findings not automatically justified",
        "```json",
        json.dumps(report["unjustified_findings"], indent=2),
        "```",
        "## Existing server-entered reasons (never overwritten)",
        "```json",
        json.dumps(report["existing_submissions"], indent=2),
        "```",
    ]
    return "\n\n".join(lines) + "\n"


def preflight(client, draft, validation=None):
    user = str(UUID(client.session["user_id"]))
    packet, graph, run, jobs, active = collect(client, draft, validation)
    report = prepare(packet, graph, run, jobs, active, draft)
    report["prepared_by"] = user
    report["submission_id"] = active["id"] if active else None
    mode = "submit" if packet["status"] == "draft" else "approve"
    report["action"] = mode
    folder = (
        Path(get_settings().storage_root)
        / "private/muj-publication"
        / str(draft)
        / user
        / (
            f"v{report['version']}-{report['checksum'][:12]}-{report['validation_id'] or 'no-validation'}"
        )
    )
    for directory in (
        folder.parents[3],
        folder.parents[2],
        folder.parents[1],
        folder.parent,
        folder,
    ):
        # Restrict only this helper's tree; do not change existing upload storage permissions.
        if directory.name == "private":
            continue
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
    manual_path = folder / "manual-findings.json"
    if not manual_path.exists():
        persist(
            manual_path,
            {
                d["id"]: {
                    "accept_limited_osm_preview": False,
                    "reason": "",
                    "evidence_reviewed": "",
                }
                for d in report["unjustified_findings"]
                if d["code"] == "near_duplicate"
            },
        )
    manual_path.chmod(0o600)
    assessments = json.loads(manual_path.read_text())
    if assessments:
        report = prepare(packet, graph, run, jobs, active, draft, assessments)
        report.update(prepared_by=user, submission_id=active["id"] if active else None, action=mode)
    report["manual_assessments"] = assessments
    proposed = {"acknowledgements": report["proposed_reasons"]}
    proposed.update(
        {"validation_id": report["validation_id"]}
        if mode == "submit"
        else {"decision": "approve", "notes": NOTES}
    )
    # Preserve owner/reviewer edits to the private proposal, including stale IDs for inspection.
    proposal = folder / "proposal.json"
    if proposal.exists():
        proposed = json.loads(proposal.read_text())
        for identity, reason in report["proposed_reasons"].items():
            proposed.setdefault("acknowledgements", {}).setdefault(identity, reason)
        persist(proposal, proposed)
    else:
        persist(proposal, proposed)
    try:
        model = SubmitInput if mode == "submit" else DecisionInput
        checked = model.model_validate(proposed).model_dump(mode="json")
        if set(checked["acknowledgements"]) != set(report["proposed_reasons"]) or any(
            not 10 <= len(v.strip()) <= 2000 for v in checked["acknowledgements"].values()
        ):
            raise ValueError
        if mode == "submit" and checked["validation_id"] != report["validation_id"]:
            raise ValueError
    except (ValueError, TypeError):
        report["blockers"].append(
            "Existing proposal has stale/invalid fields or reasons; retained untouched. Reconcile the private proposal and rerun preflight."
        )
    persist(folder / "report.json", report)
    persist(
        folder.parents[1] / "latest.json",
        {
            "bundle": str(folder),
            "prepared_by": user,
            "action": mode,
            "version": report["version"],
            "checksum": report["checksum"],
            "validation_id": report["validation_id"],
        },
    )
    text = report_markdown(report, proposed)
    temp = folder / "report.md.tmp"
    temp.write_text(text, encoding="utf-8")
    temp.chmod(0o600)
    temp.replace(folder / "report.md")
    print(f"Read-only preflight: {len(report['blockers'])} blockers; {report['warning_counts']}")
    print(
        f"Current draft version {report['version']}; checksum {report['checksum']}; validation {report['validation_id']}"
    )
    print(
        f"Inspect full report and exact proposed payload BEFORE any action: {folder}/report.md and {proposal}"
    )
    print(
        "No graph/source/validation/acknowledgement/submission/approval/publication writes. Existing submitted reasons retained in report. Browser-unsaved textarea reasons are not on the server; copy them privately into proposal.json before proceeding."
    )
    return folder, report


def perform(client, folder, action, confirm=None):
    confirm = confirm or input
    root = (Path(get_settings().storage_root) / "private/muj-publication").resolve()
    folder = folder.resolve()
    if root not in folder.parents:
        raise DemoError("Use the exact private preflight bundle printed by this helper.")
    saved = json.loads((folder / "report.json").read_text())
    if saved.get("scope_type") == "e22-naming-clone":
        raise DemoError(
            "Original pinned action path refuses naming-clone bundles; use --naming-clone --action submit for explicit owner submission. Approval stays in the normal UI."
        )
    payload = json.loads((folder / "proposal.json").read_text())
    if saved["prepared_by"] != str(UUID(client.session["user_id"])) or saved["action"] != action:
        raise DemoError(
            "Use your own fresh preflight for this action; independent review is separate."
        )
    draft = UUID(saved["draft_id"])
    if saved["campus_id"] != str(CAMPUS_ID):
        raise DemoError("Foreign campus bundle refused.")
    model = SubmitInput if action == "submit" else DecisionInput
    payload = model.model_validate(payload).model_dump(mode="json")
    if action == "approve" and payload["decision"] != "approve":
        raise DemoError(
            "Only explicit independent approval is supported; reject/withdraw through the UI."
        )
    if action == "submit" and payload["validation_id"] != saved["validation_id"]:
        raise DemoError("Proposal validation changed; create a fresh preflight.")
    packet, graph, run, jobs, active = collect(client, draft, saved["validation_id"])
    # Reconcile a previously committed exact action before checking the old version.
    # Evidence comes from the actual server packet, never an invented request/audit ID.
    recovered = None
    if (
        active
        and packet["checksum"] == saved["checksum"]
        and active["validation_id"] == saved["validation_id"]
    ):
        if (
            action == "submit"
            and active["submitter_id"] == saved["prepared_by"]
            and active["acknowledgements"] == payload["acknowledgements"]
        ):
            recovered = {"submission_id": active["id"], "status": active["status"]}
        if (
            action == "approve"
            and active["id"] == saved["submission_id"]
            and active["status"] in {"approved", "published"}
        ):
            decision = next(
                (
                    d
                    for d in active["decisions"]
                    if d["decision"] == "approve"
                    and d["actor_id"] == saved["prepared_by"]
                    and d["notes"] == payload["notes"]
                    and d["acknowledgements"] == payload["acknowledgements"]
                ),
                None,
            )
            if decision:
                recovered = {"submission_id": active["id"], "status": active["status"]}
    if recovered:
        persist(
            folder / f"receipt-{action}.json",
            {
                "state": "existing_action_verified",
                **recovered,
                "verified_by": saved["prepared_by"],
                "version": packet["edit_version"],
                "checksum": packet["checksum"],
                "evidence_limit": "Observed existing exact server submission/decision. Original request ID not recovered; no new workflow write.",
            },
        )
        print(
            "Existing exact action verified from server packet; no duplicate write. Original request audit ID not reconstructed."
        )
        return
    assessments = json.loads((folder / "manual-findings.json").read_text())
    current = prepare(packet, graph, run, jobs, active, draft, assessments)
    if (
        current["blockers"]
        or saved["blockers"]
        or assessments != saved.get("manual_assessments", {})
    ):
        raise DemoError("Preflight has blockers. Inspect report; do not override safeguards.")
    if any(
        current[k] != saved[k]
        for k in (
            "version",
            "checksum",
            "status",
            "validation_id",
            "imports",
            "sources",
            "validation",
        )
    ) or (action == "approve" and (not active or active["id"] != saved["submission_id"])):
        raise DemoError(
            "Draft, evidence or provenance changed since preflight. No write; generate/review a new bundle. Existing reasons preserved."
        )
    expected_ids = set(current["proposed_reasons"])
    if set(payload["acknowledgements"]) != expected_ids or any(
        not 10 <= len(v.strip()) <= 2000 for v in payload["acknowledgements"].values()
    ):
        raise DemoError(
            "Provide substantive reasons for exactly the current warning IDs; preserve and reconcile stale/missing reasons."
        )
    if action == "submit" and payload["validation_id"] != saved["validation_id"]:
        raise DemoError("Proposal validation changed; create a fresh preflight.")
    print(report_markdown(current, payload))
    token = "SUBMIT" if action == "submit" else "APPROVE"
    if (
        confirm(
            f"Inspect report/each reason. Type {token} to {'lock and submit' if action == 'submit' else 'independently approve'} this exact version; anything else stops: "
        ).strip()
        != token
    ):
        print("Stopped; no workflow write.")
        return
    # A human may spend minutes reading; re-read after confirmation, before If-Match write.
    fresh = client.request("GET", f"/api/v1/admin/campuses/{CAMPUS_ID}/drafts/{draft}/review")
    if (fresh["edit_version"], fresh["checksum"], fresh["status"]) != (
        saved["version"],
        saved["checksum"],
        saved["status"],
    ):
        raise DemoError("Draft changed while reviewing; no write. Prepare fresh evidence.")
    base = f"/api/v1/admin/campuses/{CAMPUS_ID}/drafts/{draft}"
    path = base + (
        "/submissions" if action == "submit" else f"/submissions/{saved['submission_id']}/decision"
    )
    try:
        response = client.request(
            "POST", path, payload, headers={"If-Match": f'"{saved["version"]}"'}
        )
        persist(
            folder / f"receipt-{action}.json",
            {
                "state": "action_response_received",
                "response": response,
                "actor_id": saved["prepared_by"],
                "request_id": client.last_request_id,
            },
        )
    except (DemoError, OSError):
        raise DemoError(
            "Action/receipt interrupted and may have committed. Preserve the bundle; rerun the SAME action/bundle to verify server state before any retry. Never publish automatically."
        ) from None
    print(
        "Workflow action saved using normal permissions/CSRF/CAS/audits. No graph edit or publication. Final publication remains explicit in Review and releases."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", type=UUID, required=True)
    parser.add_argument("--validation", type=UUID)
    parser.add_argument("--action", choices=["preflight", "submit", "approve"], default="preflight")
    parser.add_argument("--bundle", type=Path)
    parser.add_argument(
        "--naming-clone",
        action="store_true",
        help="E22 clone full-parent/diff preflight (default), or explicitly confirmed submit",
    )
    parser.add_argument("--expected-version", type=int)
    parser.add_argument("--expected-checksum")
    args = parser.parse_args()
    if args.naming_clone and (
        args.action == "approve" or (args.action == "preflight" and args.bundle)
    ):
        parser.error("Naming-clone supports default preflight or explicit submit only; no approval")
    if (
        args.naming_clone
        and args.action == "submit"
        and (
            args.validation is None
            or args.expected_version is None
            or args.expected_version < 1
            or args.expected_checksum is None
            or len(args.expected_checksum) != 64
            or any(c not in "0123456789abcdef" for c in args.expected_checksum)
        )
    ):
        parser.error(
            "Clone submit requires --validation, --expected-version and full --expected-checksum"
        )
    if (args.expected_version is not None or args.expected_checksum is not None) and not (
        args.naming_clone and args.action == "submit"
    ):
        parser.error("Expected-version/checksum flags are only for explicit naming-clone submit")
    if args.action != "preflight" and not args.bundle:
        parser.error("Explicit action requires the previously inspected --bundle path")
    client = Client(origin=os.environ.get("PUBLIC_APP_URL", "http://localhost:5173"))
    try:
        prompt_login(
            client,
            "MUJ owner/editor or reviewer application account"
            if args.naming_clone
            else "MUJ owner/editor or independent reviewer (as appropriate for this action)",
        )
        UUID(client.session["user_id"])
        if args.naming_clone:
            from app.cli.muj_naming_review import preflight as naming_preflight
            from app.cli.muj_naming_review import submit as naming_submit

            if args.action == "preflight":
                naming_preflight(client, args.draft, args.validation)
            else:
                naming_submit(
                    client,
                    args.draft,
                    args.validation,
                    args.bundle,
                    args.expected_version,
                    args.expected_checksum,
                )
        elif args.action == "preflight":
            preflight(client, args.draft, args.validation)
        else:
            # Bind the command's campus/draft to the saved bundle, never silently select another.
            saved = json.loads((args.bundle / "report.json").read_text())
            if saved["draft_id"] != str(args.draft):
                raise DemoError("Command draft differs from bundle; no workflow write.")
            perform(client, args.bundle, args.action)
    except (DemoError, OSError, ValueError, KeyError, TypeError, AttributeError):
        import sys

        error = sys.exception()
        raise SystemExit(
            str(error)
            if isinstance(error, DemoError)
            else "Invalid/unavailable preflight, session, payload or storage. Preserve files and inspect; no bypass attempted."
        ) from None
    finally:
        client.logout()


if __name__ == "__main__":
    main()
