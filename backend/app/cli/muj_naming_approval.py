"""Explicit, separate-account E22 approval only; no publication capability."""

import json
from pathlib import Path
from uuid import UUID

from app.cli.indoor_demo import DemoError, persist
from app.cli.muj_naming_review import SUBMIT_PROOF, collect, require
from app.core.config import get_settings
from app.schemas.publication import DecisionInput
from app.services.muj_setup import CAMPUS_ID
from app.services.publication import checksum

# Mirrors publication.independent for read-only inspection. The normal decision
# API remains authoritative, including against races and future policy changes.
CONTRIBUTIONS = {
    "draft.create",
    "floor.create",
    "floor.update",
    "floor.delete",
    "floor.calibrate",
    "floorplan.upload",
    "floorplan.apply",
    "indoor.patch",
    "connections.patch",
    "import.apply",
    "source.register",
    "source.remove",
}


def reviewer(client, draft, submitter, creation_id):
    session = client.request("GET", "/api/v1/admin/session")
    actor = str(UUID(session["user_id"]))
    require(
        session["username"] == "muj-reviewer"
        and actor == str(UUID(client.session["user_id"]))
        and actor != submitter,
        "Use the existing muj-reviewer separate application account, never the submitter",
    )
    permissions = set().union(
        *(set(g["permissions"]) for g in session["grants"] if g["campus_id"] == str(CAMPUS_ID))
    )
    require(
        {"review_decide", "review_read", "audit_read"} <= permissions,
        "Reviewer lacks current campus-scoped review/audit permissions",
    )
    seen, revision_events = set(), []
    for offset in range(0, 10050, 50):
        page = client.request(
            "GET", f"/api/v1/admin/campuses/{CAMPUS_ID}/audit", query={"offset": offset}
        )
        require(isinstance(page, list) and len(page) <= 50, "Incomplete audit response")
        for event in page:
            require(event["id"] not in seen, "Audit pagination changed; retry read-only inspection")
            seen.add(event["id"])
            if event["revision_id"] == draft:
                revision_events.append(event)
                action = event["action"]
                require(
                    not (
                        event["actor_id"] == actor
                        and (action in CONTRIBUTIONS or action.startswith(("catalog.", "graph.")))
                    ),
                    "Reviewer contributed to this revision; normal contributor separation forbids approval",
                )
        if len(page) < 50:
            break
    else:
        require(
            False, "Complete contributor history unavailable within audit bound; inspect normal UI"
        )
    require(creation_id in seen, "Expected draft creation audit unavailable in complete history")
    return actor


def approve(
    client,
    draft,
    validation,
    submission_id,
    folder,
    expected_checksum,
    expected_version=None,
    confirm=None,
    notes_input=None,
):
    confirm, notes_input = confirm or input, notes_input or input
    draft, validation, submission_id = map(
        str, (UUID(str(draft)), UUID(str(validation)), UUID(str(submission_id)))
    )
    folder = Path(folder).resolve()
    saved_bytes = (folder / "report.json").read_bytes()
    saved = json.loads(saved_bytes)
    root = (
        Path(get_settings().storage_root)
        / "private/muj-naming-review"
        / draft
        / str(UUID(saved["prepared_by"]))
    ).resolve()
    require(
        folder.parent == root
        and folder.name == f"v{saved['version']}-{expected_checksum}-{validation}"
        and saved["scope_type"] == "e22-naming-clone"
        and saved["draft_id"] == draft
        and saved["campus_id"] == str(CAMPUS_ID)
        and saved["checksum"] == expected_checksum
        and saved["validation_id"] == validation
        and not saved["blockers"],
        "Select the exact unblocked E22 candidate bundle and expected evidence",
    )
    # This file alone supplies candidate reviewer reasons. Never read proposal.json
    # or fall back to the current submitter's acknowledgements.
    path = folder / "reviewer-proposal.json"
    selected_bytes = path.read_bytes()

    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate reviewer proposal JSON key")
            result[key] = value
        return result

    selected = json.loads(selected_bytes, object_pairs_hook=unique_keys)
    require(
        isinstance(selected, dict)
        and set(selected) == {"validation_id", "acknowledgements"}
        and selected["validation_id"] == validation
        and isinstance(selected["acknowledgements"], dict)
        and len(selected["acknowledgements"]) == 145
        and set(selected["acknowledgements"]) == set(saved["reviewer_proposed_reasons"])
        and all(
            isinstance(v, str) and 10 <= len(v.strip()) <= 2000
            for v in selected["acknowledgements"].values()
        ),
        "Review substantive reasons for exactly all145 current IDs; preserve candidate edits",
    )

    def checked():
        current = collect(client, UUID(draft), UUID(validation))
        require(
            not current["blockers"] and all(current[k] == saved[k] for k in SUBMIT_PROOF),
            "Parent/full diff/provenance/validation/findings changed since candidate preparation",
        )
        require(
            current["status"] == "review" and len(current["existing_submissions"]) == 1,
            "Expected one existing locked review submission; no new workflow",
        )
        sub = current["existing_submissions"][0]
        require(
            sub["id"] == submission_id
            and sub["checksum"] == expected_checksum
            and sub["validation_id"] == validation
            and sub["status"] in {"submitted", "approved"}
            and sub["edit_version"] == current["version"]
            and set(sub["acknowledgements"]) == set(selected["acknowledgements"]),
            "Exact submission/checksum/validation/version/warning coverage does not match",
        )
        actor = reviewer(client, draft, sub["submitter_id"], current["creation_audit"]["id"])
        require(
            saved["prepared_by"] in {actor, sub["submitter_id"]},
            "Candidate bundle belongs to neither this reviewer nor the actual submitter",
        )
        return current, sub, actor

    current, sub, actor = checked()
    journal = folder / "approval" / actor / submission_id
    intent_path = journal / "intent.json"
    binding = {
        "scope_type": "e22-naming-clone-approval",
        "draft_id": draft,
        "submission_id": submission_id,
        "actor_id": actor,
        "checksum": expected_checksum,
        "validation_id": validation,
    }
    intent = json.loads(intent_path.read_bytes()) if intent_path.exists() else None
    if intent:
        require(
            all(intent[k] == value for k, value in binding.items())
            and intent["payload"]["decision"] == "approve"
            and intent["payload"]["acknowledgements"] == selected["acknowledgements"]
            and intent["payload_checksum"] == checksum(intent["payload"]),
            "Approval intent/payload differs; preserve files and inspect server decision",
        )
        version, notes = intent["version"], intent["payload"]["notes"]
    else:
        require(
            sub["status"] == "submitted" and not sub["decisions"],
            "A decision already exists without this local intent; inspect normal review history, never replay",
        )
        version = current["version"]  # Fetch current version; never assume Windows still at4.
        notes = notes_input(
            "Enter your review decision notes (10–4000 characters; owner-operated separate-account review, no independent human/institutional claim): "
        )
    require(
        expected_version is None or expected_version == version,
        "Expected approval version differs from selected/recorded current version",
    )
    payload = DecisionInput.model_validate(
        {"decision": "approve", "notes": notes, "acknowledgements": selected["acknowledgements"]}
    ).model_dump(mode="json")
    require(10 <= len(notes.strip()) <= 4000, "Provide substantive explicit review decision notes")
    notes = payload["notes"]  # Display/reconcile the exact normal API-normalized notes.
    intent = {
        **binding,
        "version": version,
        "payload": payload,
        "payload_checksum": checksum(payload),
    }
    print(
        f"Owner-operated separate-account review: muj-reviewer ({actor}); no independent human/institutional approval claimed.\nSelected: {path}\nDraft {draft}; submission {submission_id}; selected version {version}, current version {current['version']}; checksum {expected_checksum}; validation {validation}."
    )
    print(
        f"Exact selected approval payload SHA256: {checksum(payload)}\n"
        + json.dumps(payload, indent=2, ensure_ascii=False)
    )

    def recover(state, submission):
        if submission["status"] != "approved":
            return False
        decisions = submission["decisions"]
        exact = [
            d
            for d in decisions
            if d["decision"] == "approve"
            and d["actor_id"] == actor
            and d["notes"] == notes
            and d["acknowledgements"] == payload["acknowledgements"]
        ]
        require(
            len(decisions) == len(exact) == 1 and state["version"] == version + 1,
            "Existing decision differs; no duplicate approval or invented evidence",
        )
        journal.mkdir(parents=True, exist_ok=True, mode=0o700)
        persist(
            journal / "receipt-recovery.json",
            {
                **binding,
                "state": "existing_approval_verified",
                "decision_id": exact[0]["id"],
                "version": state["version"],
                "payload_checksum": checksum(payload),
                "evidence_limit": "Exact real server decision verified read-only. No new approval audit; original request ID not reconstructed. Owner-operated separate-account review only.",
            },
        )
        print("Existing exact approval verified; no duplicate decision/write. No publication.")
        return True

    if recover(current, sub):
        return
    require(
        current["version"] == version and not sub["decisions"], "Review version/history changed"
    )
    if (
        confirm(
            "Inspect all145 reviewer reasons and decision notes. Type APPROVE E22 to approve this exact submitted draft only: "
        ).strip()
        != "APPROVE E22"
    ):
        print("Stopped; no approval write.")
        return
    require(
        path.read_bytes() == selected_bytes
        and (folder / "report.json").read_bytes() == saved_bytes,
        "Reviewer proposal/report changed during confirmation; edits preserved",
    )
    fresh, fresh_sub, _ = checked()
    if recover(fresh, fresh_sub):
        return
    require(
        fresh["version"] == version and fresh_sub == sub, "Submission changed during review; stop"
    )
    require(
        path.read_bytes() == selected_bytes
        and (folder / "report.json").read_bytes() == saved_bytes,
        "Reviewer proposal/report changed during final checks; edits preserved",
    )
    journal.mkdir(parents=True, exist_ok=True, mode=0o700)
    persist(intent_path, intent)
    try:
        response = client.request(
            "POST",
            f"/api/v1/admin/campuses/{CAMPUS_ID}/drafts/{draft}/submissions/{submission_id}/decision",
            payload,
            headers={"If-Match": f'"{version}"'},
        )
        persist(
            journal / "receipt.json",
            {
                **binding,
                "state": "action_response_received",
                "response": response,
                "request_id": client.last_request_id,
                "payload_checksum": checksum(payload),
            },
        )
    except (DemoError, OSError):
        raise DemoError(
            "Approval/receipt interrupted and may have committed. Preserve bundle and intent; rerun the identical approval command to inspect actual server state before any retry. No publication."
        ) from None
    print(
        f"Approved exact submission {submission_id} through normal API; current version {response['edit_version']}. Receipt: {journal}/receipt.json. No publication."
    )
