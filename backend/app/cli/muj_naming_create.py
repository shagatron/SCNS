"""One E22 naming draft, resumed through durable intent and server idempotency.

No direct database access, publication or arbitrary naming capability.
"""

import json
from uuid import UUID, uuid5

from app.cli.indoor_demo import DemoError, persist
from app.cli.muj_naming import apply_reviewed, preflight, supported_changes
from app.core.portable import lock_file
from app.services.muj_setup import CAMPUS_ID

FORMAT = "scns-muj-e22-create-v1"


def creation_key(owner):
    # Deliberately independent of release/time/local file existence. Losing the
    # journal must not turn a retry by the same account into another draft.
    return "muj-e22-" + str(uuid5(CAMPUS_ID, FORMAT + ":" + str(UUID(owner))))


def read_state(path, owner):
    if not path.exists():
        return None
    try:
        state = json.loads(path.read_bytes())
        if (
            state["format"] != FORMAT
            or state["owner"] != owner
            or state["campus_id"] != str(CAMPUS_ID)
            or state["creation_key"] != creation_key(owner)
        ):
            raise ValueError
        UUID(state["release"]["id"])
        if state.get("draft"):
            UUID(state["draft"]["id"])
    except (KeyError, ValueError, TypeError):
        raise DemoError(
            "Saved E22 workflow differs or is invalid; preserve it. Use the original owner account; no new draft/key created."
        ) from None
    return state


def creation_evidence(client, state):
    # Bounded read. If the immutable audit has aged beyond this page, stop rather
    # than invent parentage. Admin Audit records can page to the original entry.
    events = client.request("GET", f"/api/v1/admin/campuses/{CAMPUS_ID}/audit")
    matches = [
        e
        for e in events
        if e["action"] == "draft.create"
        and e["actor_id"] == state["owner"]
        and e.get("after", {}).get("idempotency_key") == state["creation_key"]
    ]
    if len(matches) != 1:
        raise DemoError(
            "Creation audit not uniquely available in latest50 records. Draft UUID is retained; inspect Admin > Audit records (Next audit page) for the saved creation key/parent. Do not delete the journal or use a new key/account."
        )
    event = matches[0]
    if (
        event["revision_id"] != state["draft"]["id"]
        or event["campus_id"] != str(CAMPUS_ID)
        or event["after"]["parent_id"] != state["release"]["dataset_revision_id"]
    ):
        raise DemoError(
            "Created/recovered draft parent differs from the previewed public release. Draft retained; no rename. Inspect its creation audit; do not create a replacement automatically."
        )
    return event


def run(client, owner, folder, record_write):
    """One confirmation per mutating invocation; completed reruns are read-only."""
    changes = supported_changes()
    if (
        len(changes) != 2
        or {r["entity"] for r in changes} != {"nodes", "places"}
        or any(
            r.get("marker") != "E22"
            or r.get("external_id") != "osm-node-11664524407"
            or r["proposed_name"] != "TMA Pai Auditorium entrance"
            for r in changes
        )
    ):
        raise DemoError(
            "E22-only allowlist differs; no creation/application. Inspect the installed naming inventory."
        )
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = folder / "create-e22.json"
    with (folder / "create-e22.lock").open("a") as lock:
        try:
            lock_file(lock)
        except BlockingIOError:
            raise DemoError(
                "Another E22 workflow is running. Wait for it; do not create another draft."
            ) from None
        print(
            f"Durable E22 workflow: {path}. Keep this file and use the same owner account on retries."
        )
        state = read_state(path, owner)
        public = preflight(client)
        print(
            f"Published release {public['release']['id']}; artifact checksum {public['release']['artifact_checksum']}."
        )
        if public["blockers"]:
            raise DemoError("Published E22 preflight has blockers; no creation/application.")
        if state and state["release"] != public["release"]:
            raise DemoError(
                "Published release/restrictions differ from the saved intent. Preserve the existing draft/journal; inspect before resuming. No replacement draft created."
            )
        if not state:
            if not public["changes"]:
                print(
                    "Published E22 names already present; no draft created, applied0, remaining0."
                )
                return
            if len(public["changes"]) != 2:
                raise DemoError(
                    "Expected exactly the two E22 published naming changes. Preserve the partial/owner state and inspect; no draft created."
                )
            state = {
                "format": FORMAT,
                "owner": owner,
                "campus_id": str(CAMPUS_ID),
                "creation_key": creation_key(owner),
                "release": public["release"],
                "published_changes": public["changes"],
                "draft": None,
            }
        preview = preflight(client, state["draft"]["id"]) if state["draft"] else public
        if preview["blockers"] or preview["release"] != state["release"]:
            raise DemoError(
                "Draft/release evidence conflicts with saved intent; preserve owner edits, no application."
            )
        print("Exact E22-only preview (all unresolved identities, including E05, stay unchanged):")
        for change in preview["changes"]:
            print(
                f"{change['entity']}/{change['id']}: {change['before_label']} -> {change['after_label']}"
            )
        persist(folder / "create-e22-preview.json", preview)
        if state["draft"]:
            print(
                f"Retained draft {state['draft']['version']} UUID {state['draft']['id']}; edit version {preview['draft_version']}."
            )
        if state["draft"] and not preview["changes"]:
            creation_evidence(client, state)
            summarize(preview, state, 0)
            return
        if (
            input(
                "Type CREATE AND APPLY E22 to create/recover this single draft and apply only the shown names: "
            ).strip()
            != "CREATE AND APPLY E22"
        ):
            print("Stopped before creation/application. No dataset writes this run.")
            return
        fresh = preflight(client, state["draft"]["id"] if state["draft"] else None)
        if fresh != preview:
            raise DemoError(
                "Evidence/version changed during confirmation; preserve input and rerun. No new creation/application."
            )
        # Persist intent and key BEFORE any network write. No passwords/tokens.
        persist(path, state)
        if not state["draft"]:
            draft = client.request(
                "POST",
                f"/api/v1/admin/campuses/{CAMPUS_ID}/drafts",
                headers={"Idempotency-Key": state["creation_key"]},
            )
            state["draft"] = draft
            print(f"Created/recovered draft {draft['version']} UUID {draft['id']}.")
            # Failure here is recovered by the SAME server idempotency key,
            # even if the response or this local save was lost.
            persist(path, state)
        event = creation_evidence(client, state)
        state["creation_audit"] = event  # Actual immutable event, not replay request ID.
        persist(path, state)
        current = preflight(client, state["draft"]["id"])
        if current["release"] != state["release"] or current["blockers"]:
            raise DemoError(
                "Release/draft changed after creation; draft retained, no naming application."
            )
        # Creation does not grant permission to overwrite edits made in the new
        # draft before we first read it. The two approved old/new labels and
        # source coordinates/anchor bindings remain guarded by preflight/CAS.
        before = len(current["changes"])
        final = apply_reviewed(client, current, record_write)
        state["last_verification"] = {
            "draft_version": final["draft_version"],
            "remaining": final["changes"],
            "receipt_type": "state_verification",
        }
        persist(path, state)
        summarize(final, state, before)


def summarize(report, state, applied):
    print(
        f"Draft {state['draft']['version']} UUID {state['draft']['id']}; edit version {report['draft_version']}. Applied this run {applied}; remaining {len(report['changes'])}."
    )
    remaining = {c["id"] for c in report["changes"]}
    for change in supported_changes():
        status = "REMAINING" if change["id"] in remaining else "PRESENT (verified current state)"
        print(f"{status}: {change['entity']}/{change['id']} -> {change['proposed_name']}")
    print(
        "E05 and every other unresolved identity unchanged. Public release unchanged; no submission, approval or publication."
    )
