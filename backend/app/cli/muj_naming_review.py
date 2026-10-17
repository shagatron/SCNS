"""Exact-parent/full-diff E22 preparation and explicitly confirmed submission.

Read-only by default. No graph edits, approval or publication capability.
"""

import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from uuid import UUID

from app.cli import muj_publication as original
from app.cli.indoor_demo import DemoError, persist
from app.cli.muj_naming import published, supported_changes
from app.core.config import get_settings
from app.schemas.imports import ImportOptions
from app.services.catalog import normalize
from app.services.muj_setup import CAMPUS_ID, ROOT, prepared
from app.services.muj_update import comparable
from app.services.publication import TABLES, checksum, public_projection


def require(condition, message, details=None):
    if not condition:
        error = DemoError(message + " No dataset writes; preserve current draft/reasons.")
        error.evidence = details
        raise error


def select_run(packet, identity=None):
    if identity:
        run = next((r for r in packet["validations"] if r["id"] == str(identity)), None)
    else:
        run = next(
            (
                r
                for r in packet["validations"]
                if r["checksum"] == packet["checksum"]
                and r["edit_version"] == packet["edit_version"]
            ),
            None,
        )
    require(
        run is not None, "Selected current validation missing; run normal authoritative validation"
    )
    require(
        run["checksum"] == packet["checksum"]
        and (packet["status"] != "draft" or run["edit_version"] == packet["edit_version"]),
        "Selected validation is stale",
    )
    require(run["report"]["errors"] == 0, "Validation has blocking errors")
    findings = run["report"]["diagnostics"]
    require(
        all(
            d["severity"] == "warning"
            and checksum({k: v for k, v in d.items() if k != "id"})[:24] == d["id"]
            for d in findings
        ),
        "Unexpected/inconsistent diagnostic content or ID",
    )
    require(
        len(findings) == run["report"]["warnings"]
        and len({d["id"] for d in findings}) == len(findings),
        "Incomplete or duplicate diagnostic inventory",
    )
    return run


def reconstruct_parent(packet, release, artifact):
    require(
        packet["id"] == release["dataset_revision_id"] and packet["status"] == "frozen",
        "Expected frozen parent release revision",
    )
    result = {entity: {} for entity in TABLES}
    for item in packet["diff"]:
        require(
            item["entity"] in result and item["before"] is None and item["after"] is not None,
            "Parent diff is not a complete original-campus snapshot; separate assessment required",
        )
        require(item["id"] not in result[item["entity"]], "Duplicate parent diff record")
        result[item["entity"]][item["id"]] = item["after"]
    result["campus"] = artifact["campus"]
    require(
        checksum(result) == packet["checksum"] == release["checksum"],
        "Full reconstructed parent checksum does not match immutable release",
    )
    require(
        public_projection(result) == artifact,
        "Parent public projection differs from approved artifact",
    )
    return result


def verify_diff(parent, packet):
    expected = deepcopy(parent)
    allowed = supported_changes()
    require(
        len(allowed) == 2
        and {r["entity"] for r in allowed} == {"nodes", "places"}
        and all(
            r["marker"] == "E22"
            and r["external_id"] == "osm-node-11664524407"
            and r["proposed_name"] == "TMA Pai Auditorium entrance"
            for r in allowed
        ),
        "E22 allowlist differs",
    )
    changes = {(d["entity"], d["id"]): d for d in packet["diff"]}
    require(
        len(changes) == len(packet["diff"]) == 2
        and set(changes) == {(r["entity"], r["id"]) for r in allowed},
        "Full draft diff contains changes beyond the two E22 records",
        {
            "observed_diff": packet["diff"],
            "checksum": packet["checksum"],
            "expected_records": [{"entity": r["entity"], "id": r["id"]} for r in allowed],
        },
    )
    for row in allowed:
        entity, identity = row["entity"], row["id"]
        change = changes[entity, identity]
        before = parent[entity].get(identity)
        label = "name" if entity == "places" else "label"
        require(
            before is not None
            and change["before"] == before
            and before[label] == row["current_label"],
            "E22 before-image differs from the verified parent",
        )
        after = deepcopy(before)
        after[label] = row["proposed_name"]
        if entity == "places":
            after["search_text"] = normalize(
                " ".join([after["code"], after["name"], after["kind"], *after["aliases"]])
            )
        require(
            change["after"] == after,
            "E22 after-image includes an unexpected field or search-index change",
        )
        expected[entity][identity] = after
    require(
        checksum(expected) == packet["checksum"],
        "Full reconstructed draft checksum differs; preserve owner edits",
    )
    require(expected["sources"] == packet["sources"], "Source metadata/approvals changed")
    return expected


def verify_parent_baseline(parent, packet, run, jobs):
    for entity, rows in original.pinned_graph().items():
        require(
            set(rows) == set(parent[entity])
            and all(comparable(entity, parent[entity][i]) == value for i, value in rows.items()),
            f"Parent {entity} differs from original reviewed v2 pin",
        )
    manifest, _ = prepared()
    sources = parent["sources"]
    require(
        sources == packet["sources"]
        and len(sources) == 1
        and all(
            s["rights"] == "authorized"
            and s["approved_by"]
            and s["approved_by"] != s["uploader_id"]
            and manifest["source_sha256"] in s["provenance"]
            and "OpenStreetMap" in s["attribution"]
            and "ODbL" in s["attribution"]
            and s["derivative"]
            for s in sources.values()
        ),
        "Parent authorized source, approval or attribution differs",
    )
    options = ImportOptions.model_validate_json((ROOT / "options.json").read_bytes()).model_dump(
        mode="json"
    )
    files = {n: h for n, h in manifest["files"].items() if n.startswith("batch-")}
    require(
        len(jobs) == 3
        and {j["filename"] for j in jobs} == set(files)
        and all(
            j["campus_id"] == str(CAMPUS_ID)
            and j["revision_id"] == packet["id"]
            and j["state"] == "committed"
            and j["checksum"] == files.get(j["filename"])
            and j["options"] == options
            and j["applier_id"]
            for j in jobs
        ),
        "Parent import receipts do not match exact pinned batches/options/actors",
    )
    require(
        {d["ids"][0] for d in run["report"]["diagnostics"] if d["code"] == "import_provenance"}
        == {j["id"] for j in jobs},
        "Parent import warnings/receipts differ",
    )


def compare_findings(previous, current, acknowledgements):
    old = {d["id"]: d for d in previous}
    expected = {}
    removed = []
    transitions = []
    e22 = next(r for r in supported_changes() if r["entity"] == "places")
    for identity, diagnostic in old.items():
        if diagnostic["code"] == "import_provenance":
            removed.append(diagnostic)
            continue
        updated = deepcopy(diagnostic)
        renamed = diagnostic["code"] in {
            "connectivity_shortest",
            "connectivity_step_free",
        } and diagnostic["ids"] == [e22["id"]]
        if renamed:
            require(
                e22["current_label"] in diagnostic["message"], "E22 parent finding wording differs"
            )
            updated["message"] = updated["message"].replace(
                e22["current_label"], e22["proposed_name"]
            )
            updated["id"] = checksum({k: v for k, v in updated.items() if k != "id"})[:24]
        require(updated["id"] not in expected, "Ambiguous counterpart mapping")
        expected[updated["id"]] = updated
        transitions.append(
            {
                "old_id": identity,
                "current_id": updated["id"],
                "code": diagnostic["code"],
                "changed_label": renamed,
            }
        )
    actual = {d["id"]: d for d in current}
    require(
        len(actual) == len(current) and actual == expected,
        "Unexpected current finding additions/removals/content; no blanket reason carry-forward",
        {
            "added_ids": sorted(set(actual) - set(expected)),
            "missing_ids": sorted(set(expected) - set(actual)),
            "differences": [
                {"id": i, "expected": expected.get(i), "actual": actual.get(i)}
                for i in sorted(set(expected) | set(actual))
                if expected.get(i) != actual.get(i)
            ],
        },
    )
    require(
        len(previous) == 148
        and len(removed) == 3
        and len(current) == 145
        and sum(t["changed_label"] for t in transitions) == 2,
        "Unexpected naming-clone warning delta",
    )
    reasons = {}
    unjustified = []
    for transition in transitions:
        reason = acknowledgements.get(transition["old_id"])
        if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 2000:
            unjustified.append(transition)
            continue
        if transition["changed_label"]:
            reason = reason.replace(e22["current_label"], e22["proposed_name"])
            suffix = " Naming-only E22 update: TMA Pai Auditorium entrance; same stable place, topology and unverified accessibility. No main-entrance or institutional/field approval claim."
            if suffix.strip() not in reason:
                reason += suffix
        if len(reason) > 2000:
            unjustified.append(transition)
        else:
            reasons[transition["current_id"]] = reason
    return transitions, removed, reasons, unjustified


def collect(client, draft, validation=None):
    release, artifact = published(client)
    base = f"/api/v1/admin/campuses/{CAMPUS_ID}/drafts"
    packet = client.request("GET", f"{base}/{draft}/review")
    require(
        packet["id"] == str(draft) and packet["status"] in {"draft", "review"},
        "Expected existing naming draft/review revision",
    )
    creation = []
    for offset in range(0, 10001, 50):
        page = client.request(
            "GET", f"/api/v1/admin/campuses/{CAMPUS_ID}/audit", query={"offset": offset}
        )
        creation.extend(
            e for e in page if e["action"] == "draft.create" and e["revision_id"] == str(draft)
        )
        if creation or len(page) < 50:
            break
    require(
        len(creation) == 1 and creation[0]["after"]["parent_id"] == release["dataset_revision_id"],
        "Draft parent not uniquely verified against current published release within the bounded10050-entry audit search; inspect Audit records / Next audit page",
    )
    parent_packet = client.request("GET", f"{base}/{release['dataset_revision_id']}/review")
    parent = reconstruct_parent(parent_packet, release, artifact)
    current = verify_diff(parent, packet)
    submissions = [
        s
        for s in parent_packet["submissions"]
        if s["status"] == "published" and s["checksum"] == release["checksum"]
    ]
    require(len(submissions) == 1, "Published parent submission/history not unique")
    submission = submissions[0]
    parent_run = select_run(parent_packet, submission["validation_id"])
    _, _, _, jobs, _ = original.collect(client, UUID(parent_packet["id"]), parent_run["id"])
    verify_parent_baseline(parent, parent_packet, parent_run, jobs)
    run = select_run(packet, validation)
    require(
        run["validator"] == parent_run["validator"],
        "Validator changed; separate evidence assessment required",
    )
    require(
        run["report"]["imports"] == [] and run["report"]["sources"] == current["sources"],
        "Clone import/source validation evidence differs",
    )

    def route_evidence(rows):
        return sorted(
            ({k: v for k, v in row.items() if k != "reason"} for row in rows), key=checksum
        )

    require(
        route_evidence(run["evidence"]) == route_evidence(parent_run["evidence"]),
        "Current route acceptance evidence differs from reviewed parent; inspect before retaining reasons",
        {
            "parent_validation_id": parent_run["id"],
            "previous_evidence": parent_run["evidence"],
            "current_validation_id": run["id"],
            "current_evidence": run["evidence"],
            "current_version": packet["edit_version"],
            "current_checksum": packet["checksum"],
        },
    )
    expected_counts = {
        "connectivity_shortest": 52,
        "connectivity_step_free": 55,
        "unmapped_entrance": 33,
        "near_duplicate": 2,
        "components_shortest": 1,
        "components_step_free": 1,
        "unknown_accessibility": 1,
    }
    require(
        dict(Counter(d["code"] for d in run["report"]["diagnostics"])) == expected_counts
        and dict(Counter(d["code"] for d in parent_run["report"]["diagnostics"]))
        == {**expected_counts, "import_provenance": 3},
        "Unexpected warning categories/counts; separate assessment required",
    )
    transitions, removed, reasons, unjustified = compare_findings(
        parent_run["report"]["diagnostics"],
        run["report"]["diagnostics"],
        submission["acknowledgements"],
    )
    decisions = [d for d in submission["decisions"] if d["decision"] == "approve"]
    require(
        len(decisions) == 1 and decisions[0]["actor_id"] != submission["submitter_id"],
        "Expected distinct approving application account history",
    )
    _, _, reviewer_reasons, reviewer_unjustified = compare_findings(
        parent_run["report"]["diagnostics"],
        run["report"]["diagnostics"],
        decisions[0]["acknowledgements"],
    )
    latest = client.request("GET", f"{base}/{draft}/review")
    parent_latest = client.request("GET", f"{base}/{parent_packet['id']}/review")
    active_latest, _ = published(client)
    require(
        (
            latest["edit_version"],
            latest["checksum"],
            latest["status"],
            latest["validations"],
            latest["submissions"],
        )
        == (
            packet["edit_version"],
            packet["checksum"],
            packet["status"],
            packet["validations"],
            packet["submissions"],
        )
        and parent_latest == parent_packet
        and active_latest == release,
        "Draft, validation, parent history or public release changed during preflight",
    )
    return {
        "scope_type": "e22-naming-clone",
        "action": "read_only",
        "draft_id": str(draft),
        "campus_id": str(CAMPUS_ID),
        "version": packet["edit_version"],
        "status": packet["status"],
        "checksum": packet["checksum"],
        "validation_id": run["id"],
        "parent_release": release,
        "creation_audit": creation[0],
        "parent_submission_id": submission["id"],
        "previous_validation": parent_run,
        "previous_submission": submission,
        "near_duplicate_pairs": original.near_pairs(
            current, original.topology(current, "shortest")
        ),
        "full_diff": packet["diff"],
        "validation": run,
        "sources": current["sources"],
        "original_imports": jobs,
        "warning_counts": dict(Counter(d["code"] for d in run["report"]["diagnostics"])),
        "counterparts": transitions,
        "removed_import_findings": removed,
        "proposed_reasons": reasons,
        "reviewer_proposed_reasons": reviewer_reasons,
        "unjustified_findings": unjustified + reviewer_unjustified,
        "existing_submissions": packet["submissions"],
        "blockers": ["Some prior reasons missing/invalid; individual reassessment required"]
        if unjustified or reviewer_unjustified
        else [],
        "qualification": "Candidate reasons only. All145current findings require current review, including the two ambiguous near-duplicate pairs. Separate owner-operated accounts are not independent human/institutional review. No new source, field/accessibility or main-entrance approval. No dataset writes.",
    }


def preflight(client, draft, validation=None):
    user = str(UUID(client.session["user_id"]))
    root = Path(get_settings().storage_root) / "private/muj-naming-review" / str(draft) / user
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        report = collect(client, draft, validation)
    except DemoError as error:
        persist(
            root / "blocked.json",
            {
                "draft_id": str(draft),
                "blockers": [str(error)],
                "details": getattr(error, "evidence", None),
                "scope_type": "e22-naming-clone",
                "action": "read_only",
            },
        )
        raise DemoError(f"{error} Inspect {root}/blocked.json.") from None
    folder = root / f"v{report['version']}-{report['checksum']}-{report['validation_id']}"
    folder.mkdir(exist_ok=True, mode=0o700)
    effective = {}
    for filename, reasons in [
        ("proposal.json", report["proposed_reasons"]),
        ("reviewer-proposal.json", report["reviewer_proposed_reasons"]),
    ]:
        path = folder / filename
        proposed = {"validation_id": report["validation_id"], "acknowledgements": reasons}
        current_submissions = [
            s
            for s in report["existing_submissions"]
            if s["checksum"] == report["checksum"]
            and s["validation_id"] == report["validation_id"]
            and s["status"] in {"submitted", "approved"}
        ]
        if current_submissions and not path.exists():
            existing = current_submissions[0]["acknowledgements"]
            if filename == "reviewer-proposal.json":
                decisions = [
                    d for d in current_submissions[0]["decisions"] if d["decision"] == "approve"
                ]
                existing = decisions[-1]["acknowledgements"] if decisions else reasons
            proposed["acknowledgements"] = deepcopy(existing)
        if path.exists():
            proposed = json.loads(path.read_text())
            for identity, reason in reasons.items():
                proposed.setdefault("acknowledgements", {}).setdefault(identity, reason)
        if (
            proposed.get("validation_id") != report["validation_id"]
            or set(proposed["acknowledgements"]) != set(reasons)
            or any(
                not isinstance(v, str) or not 10 <= len(v.strip()) <= 2000
                for v in proposed["acknowledgements"].values()
            )
        ):
            report["blockers"].append(
                f"{filename} has stale/invalid owner edits; retained for reconciliation"
            )
        persist(path, proposed)
        effective[filename] = proposed
    report["effective_proposals"] = effective
    report["prepared_by"] = user
    persist(folder / "report.json", report)
    persist(
        root / "latest.json",
        {
            "bundle": str(folder),
            "version": report["version"],
            "checksum": report["checksum"],
            "validation_id": report["validation_id"],
        },
    )
    text = (
        "# E22 naming clone review preflight\n\n"
        + report["qualification"]
        + "\n\n```json\n"
        + json.dumps(report, indent=2, ensure_ascii=False)
        + "\n```\n"
    )
    path = folder / "report.md"
    path.write_text(text, encoding="utf-8")
    path.chmod(0o600)
    print(
        f"Read-only E22 review: draft {draft}, current version {report['version']}, checksum {report['checksum']}, validation {report['validation_id']}; {len(report['blockers'])} blockers."
    )
    print(
        f"145counterparts:143unchanged +2E22label/ID updates;3original import warnings absent in clone (original receipts/bindings verified, no new imports). Inspect {folder}/report.md and proposal.json before any normal UI action."
    )
    return folder, report


# Immutable proof fields must still match the inspected bundle, not merely two names.
SUBMIT_PROOF = (
    "scope_type",
    "campus_id",
    "draft_id",
    "checksum",
    "validation_id",
    "parent_release",
    "creation_audit",
    "parent_submission_id",
    "previous_validation",
    "previous_submission",
    "near_duplicate_pairs",
    "full_diff",
    "validation",
    "sources",
    "original_imports",
    "warning_counts",
    "counterparts",
    "removed_import_findings",
    "proposed_reasons",
    "reviewer_proposed_reasons",
    "unjustified_findings",
)


def submit(client, draft, validation, folder, expected_version, expected_checksum, confirm=None):
    """Submit the existing reviewed owner payload, never regenerate or approve it."""
    from app.schemas.publication import SubmitInput

    confirm = confirm or input
    user = str(UUID(client.session["user_id"]))  # SessionOut is top-level, never ['user']['id'].
    draft, validation = str(UUID(str(draft))), str(UUID(str(validation)))
    root = (
        Path(get_settings().storage_root) / "private/muj-naming-review" / draft / user
    ).resolve()
    folder = Path(folder).resolve()
    require(folder.parent == root, "Select this authenticated owner's exact naming-clone bundle")
    saved_bytes = (folder / "report.json").read_bytes()
    saved = json.loads(saved_bytes)
    require(
        saved["scope_type"] == "e22-naming-clone"
        and saved["prepared_by"] == user
        and saved["draft_id"] == draft
        and saved["campus_id"] == str(CAMPUS_ID)
        and saved["version"] == expected_version
        and saved["checksum"] == expected_checksum
        and saved["validation_id"] == validation
        and folder.name == f"v{expected_version}-{expected_checksum}-{validation}",
        "Command, owner, bundle and expected draft evidence must match exactly",
    )
    require(
        not saved["blockers"], "Saved preflight has blockers; reconcile without discarding reasons"
    )
    path = folder / "proposal.json"
    payload_bytes = path.read_bytes()

    # Reject ambiguous duplicate JSON keys instead of silently picking a reason.
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate proposal JSON key")
            result[key] = value
        return result

    selected = json.loads(payload_bytes, object_pairs_hook=unique_keys)
    require(
        isinstance(selected, dict)
        and set(selected) == {"validation_id", "acknowledgements"}
        and isinstance(selected["acknowledgements"], dict)
        and selected["validation_id"] == validation,
        "Select the exact current validation and warning-reason payload",
    )
    payload = SubmitInput.model_validate(selected).model_dump(mode="json")
    require(
        len(payload["acknowledgements"]) == 145
        and set(payload["acknowledgements"]) == set(saved["proposed_reasons"])
        and all(
            isinstance(v, str) and 10 <= len(v.strip()) <= 2000
            for v in payload["acknowledgements"].values()
        ),
        "Provide substantive reasons for exactly all 145 current warning IDs; preserve edited text",
    )
    intent = {
        "scope_type": "e22-naming-clone",
        "draft_id": draft,
        "actor_id": user,
        "version": expected_version,
        "checksum": expected_checksum,
        "validation_id": validation,
        "payload_checksum": checksum(payload),
    }
    intent_path = folder / "intent-submit.json"
    if intent_path.exists():
        require(
            json.loads(intent_path.read_bytes()) == intent,
            "Submission intent differs; preserve bundle and inspect server history before reconciliation",
        )

    def checked():
        current = collect(client, UUID(draft), UUID(validation))
        require(
            not current["blockers"] and all(current[k] == saved[k] for k in SUBMIT_PROOF),
            "Parent, full diff, source/provenance, validation or findings changed since reviewed preflight",
        )
        return current

    def recover(current):
        submissions = current["existing_submissions"]
        if not submissions:
            return False
        exact = [
            s
            for s in submissions
            if s["status"] in {"submitted", "approved"}
            and s["submitter_id"] == user
            and s["validation_id"] == validation
            and s["checksum"] == expected_checksum
            and s["edit_version"] == expected_version + 1
            and s["acknowledgements"] == payload["acknowledgements"]
        ]
        require(
            len(exact) == 1 and len(submissions) == 1,
            "Existing submission differs or history is ambiguous; no duplicate submission",
        )
        persist(
            folder / "receipt-submit-recovery.json",
            {
                "state": "existing_submission_verified",
                "submission_id": exact[0]["id"],
                "status": exact[0]["status"],
                "verified_by": user,
                "version": current["version"],
                "checksum": expected_checksum,
                "payload_checksum": checksum(payload),
                "evidence_limit": "Exact server submission verified read-only. No new workflow write; original request ID not reconstructed.",
            },
        )
        print(
            f"Existing exact submission {exact[0]['id']} verified; no duplicate write. No approval/publication."
        )
        return True

    current = checked()
    if recover(current):
        return
    require(
        current["version"] == expected_version and current["status"] == "draft",
        "Draft version/status changed; stop and preserve reasons",
    )
    print(
        f"Selected bundle: {folder}\nDraft: {draft}; version: {expected_version}; checksum: {expected_checksum}"
    )
    print(
        f"Exact selected payload SHA256: {checksum(payload)}; 145 individual reasons:\n"
        + json.dumps(payload, indent=2, ensure_ascii=False)
    )
    if (
        confirm(
            "Review every selected reason. Type SUBMIT E22 to lock and submit this exact draft (no approval/publication): "
        ).strip()
        != "SUBMIT E22"
    ):
        print("Stopped; no workflow write.")
        return
    require(
        path.read_bytes() == payload_bytes and (folder / "report.json").read_bytes() == saved_bytes,
        "Payload/report changed during confirmation; input preserved, review again",
    )
    fresh = checked()  # Full safeguards again after the human review interval.
    if recover(fresh):
        return
    require(
        fresh["version"] == expected_version and fresh["status"] == "draft",
        "Draft changed during confirmation; no submission",
    )
    persist(intent_path, intent)  # Durable intent before the only workflow POST.
    try:
        response = client.request(
            "POST",
            f"/api/v1/admin/campuses/{CAMPUS_ID}/drafts/{draft}/submissions",
            payload,
            headers={"If-Match": f'"{expected_version}"'},
        )
        persist(
            folder / "receipt-submit.json",
            {
                "state": "action_response_received",
                "response": response,
                "actor_id": user,
                "request_id": client.last_request_id,
                "payload_checksum": checksum(payload),
            },
        )
    except (DemoError, OSError):
        raise DemoError(
            "Submission/receipt interrupted and may have committed. Preserve this exact bundle and rerun the SAME command: full checks and exact server reconciliation precede any retry. Do not create another draft or invent audit evidence."
        ) from None
    print(
        f"Submitted {response['id']} through normal API; draft locked for review. No approval/publication. Receipt: {folder}/receipt-submit.json"
    )
