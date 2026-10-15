"""Preview and explicitly apply the versioned MUJ correction through authenticated graph services."""

import argparse
import os
from pathlib import Path
from uuid import UUID, uuid4

from app.cli.indoor_demo import Client, DemoError, persist, prompt_login
from app.core.config import get_settings
from app.services.muj_setup import CAMPUS_ID
from app.services.muj_update import apply_reviewed, plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", type=UUID, required=True)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    client = Client(origin=os.environ.get("PUBLIC_APP_URL", "http://localhost:5173"))
    try:
        prompt_login(client, "MUJ editor/owner")
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
            "Review all proposed geometry, additions and explicit edge removals before applying. No publication or approval occurs."
        )
        if args.plan_only or preview["state"] == "already_applied":
            return
        if (
            input(
                "Type APPLY to save this exact reviewed correction in one draft transaction (anything else stops): "
            ).strip()
            != "APPLY"
        ):
            print("Stopped after preview. Nothing applied; rerun safely.")
            return
        receipt = apply_reviewed(client, preview)
        persist(
            folder / f"receipt-{uuid4()}.json",
            {**receipt, "requested_by": client.session["user"]["id"]},
        )
        print(
            f"Correction {receipt['state']}. Normal server validation/CAS/audits enforced; MUJ remains unpublished."
        )
    except (DemoError, ValueError, OSError) as error:
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
