"""Preview and explicitly apply the versioned MUJ correction through authenticated graph services."""

import argparse
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from app.cli.indoor_demo import Client, DemoError, persist, prompt_login
from app.core.config import get_settings
from app.services.muj_setup import CAMPUS_ID
from app.services.muj_update import apply_reviewed, plan


def save_receipt(folder, result, requester):
    applied = result["state"] == "applied"
    if applied:
        path = folder / f"receipt-{uuid4()}.json"
        identity = {"requested_by": requester}
    else:
        # Recovery proves current state, not who/when originally applied it. Never reuse
        # the graph GET request ID as evidence of the original graph POST.
        path = folder / (
            f"verification-v{result['revision_version']}-{result['to_manifest_sha256'][:12]}.json"
        )
        identity = {"verified_by": requester}
    document = {
        **result,
        **identity,
        "receipt_type": "application" if applied else "state_verification",
        "recorded_at": datetime.now(UTC).isoformat(),
        "graph_writes_this_run": int(applied),
    }
    if not applied:
        document.pop("audit_request_id", None)
        document["evidence_limit"] = (
            "Verified exact correction records, deletions, dependencies and manifest against "
            "the authenticated saved graph at revision_version. Counts describe the existing "
            "correction, not new writes. Original application actor/request audit not recovered."
        )
    try:
        persist(path, document)
    except OSError:
        raise DemoError(
            ("Graph application succeeded, but" if applied else "Existing correction verified, but")
            + " receipt saving failed. Preserve the draft; use --recover-receipt after fixing private storage."
        ) from None
    print(
        f"Receipt: {path}"
        if applied
        else f"Verified already_applied at draft version {result['revision_version']}; "
        f"no graph writes. Verification receipt: {path}. Original application audit not recovered."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", type=UUID, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument(
        "--recover-receipt",
        action="store_true",
        help="Verify the existing correction and save a verification receipt; never apply graph changes",
    )
    args = parser.parse_args()
    client = Client(origin=os.environ.get("PUBLIC_APP_URL", "http://localhost:5173"))
    application_attempted = False
    try:
        prompt_login(client, "MUJ editor/owner")
        # Validate the real SessionOut identity before any possible graph transaction.
        try:
            requester = str(UUID(client.session["user_id"]))
        except (KeyError, TypeError, ValueError, AttributeError):
            raise DemoError(
                "Unexpected authenticated session identity; no graph write attempted."
            ) from None
        preview = plan(
            client.request("GET", f"/api/v1/admin/campuses/{CAMPUS_ID}/drafts/{args.draft}/graph"),
            args.draft,
        )
        folder = Path(get_settings().storage_root) / "private/muj-updates" / str(args.draft)
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = (
            folder
            / f"preview-v{preview['revision_version']}-{preview['to_manifest_sha256'][:12]}.json"
        )
        persist(path, preview)
        print(
            f"Correction {preview['state']}: {preview['counts']}; original v1 receipts retained. Preview: {path}"
        )
        print(
            "Read-only verification; counts describe the existing correction, not new writes."
            if args.recover_receipt or preview["state"] == "already_applied"
            else "Review all proposed geometry, additions and explicit edge removals before applying. No publication or approval occurs."
        )
        if args.recover_receipt and preview["state"] != "already_applied":
            raise DemoError(
                "Correction is not already applied. Recovery refused; no graph write attempted. "
                "Preserve existing work and inspect the preview."
            )
        if args.plan_only:
            return
        if preview["state"] == "already_applied":
            save_receipt(folder, preview, requester)
            return
        if (
            input(
                "Type APPLY to save this exact reviewed correction in one draft transaction (anything else stops): "
            ).strip()
            != "APPLY"
        ):
            print("Stopped after preview. Nothing applied; rerun safely.")
            return
        application_attempted = True
        receipt = apply_reviewed(client, preview)
        save_receipt(folder, receipt, requester)
        print(
            f"Correction {receipt['state']}. Normal server validation/CAS/audits enforced; MUJ remains unpublished."
        )
    except (DemoError, ValueError, OSError) as error:
        if application_attempted:
            # A failed response/local save does not imply a rolled-back graph transaction.
            print(
                "Application may have committed; do not repeat APPLY. Verify/recover read-only with: "
                f"python -m app.cli.muj_update --draft {args.draft} --recover-receipt"
            )
        # DemoError is sanitized; avoid arbitrary validation bodies/values/credentials.
        raise SystemExit(
            str(error)
            if isinstance(error, DemoError)
            else "Correction stopped; preserve progress and inspect configuration/source pins. No bypass attempted."
        ) from None
    finally:
        client.logout()


if __name__ == "__main__":
    main()
