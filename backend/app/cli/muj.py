"""Local, authenticated, resumable staged MUJ import. Never approves or publishes."""

import argparse
import base64
import hashlib
import json
import os
import time
from pathlib import Path
from urllib.parse import urlencode

from app.cli.indoor_demo import Client, DemoError, prompt_login
from app.core.config import get_settings
from app.services.muj_setup import ROOT, prepared
from app.services.osm_conversion import encode


def stage(client, preparation, *, confirm=input, sleep=time.sleep):
    """All writes use supported HTTP services. Safe retry IDs bind draft, source and batch."""
    account = client.session
    grants = [g for g in account["grants"] if "user_admin" in g["permissions"]]
    if not grants:
        raise DemoError(
            "An existing campus system administrator is required. No new accounts/default passwords created."
        )
    source = grants[0]["campus_id"]
    state = client.request("POST", f"/api/v1/admin/campuses/{source}/muj-setup")
    campus = f"/api/v1/admin/campuses/{state['campus_id']}"
    draft = campus + f"/drafts/{state['draft_id']}"
    print(f"MUJ unpublished draft {state['draft_id']} (campus {state['campus_id']}).")
    report = json.loads((preparation / "report.json").read_bytes())
    print(
        f"Prepared counts: {report['included_counts']}; {len(report['components'])} weak components; {report['unanchored_destination_count']} unanchored destinations."
    )
    opts = base64.b64encode((preparation / "options.json").read_bytes()).decode()
    for path in sorted(preparation.glob("batch-*.json")):
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        key = hashlib.sha256(f"muj:{state['draft_id']}:{sha}".encode()).hexdigest()
        job = client.request(
            "POST",
            draft + "/imports?" + urlencode({"filename": path.name}),
            raw=raw,
            headers={
                "Content-Type": "application/octet-stream",
                "X-Import-Options": opts,
                "Idempotency-Key": key,
            },
        )
        base = campus + f"/imports/{job['id']}"
        if job["state"] == "committed":
            print(f"{path.name}: already committed, no duplicate write.")
            continue
        if job["state"] in {"preview_ready", "validated"}:
            # Explicit retry refreshes only the preview, never applies a stale version.
            job = client.request("POST", base + "/refresh")
        elif job["state"] == "failed":
            raise DemoError(
                f"{path.name}: processing failed. Inspect import history/errors in admin; retry there after resolving, then rerun."
            )
        elif job["state"] == "cancelled":
            raise DemoError(
                "Previously cancelled MUJ job; no automatic replacement. Resolve explicitly with owner."
            )
        for _ in range(120):
            if job["state"] in {"preview_ready", "validated", "failed", "cancelled", "committed"}:
                break
            sleep(1)
            job = client.request("GET", base)
        if job["state"] not in {"preview_ready", "validated"}:
            raise DemoError(
                f"{path.name}: {job['state']}. Partial progress preserved; inspect worker/history and rerun."
            )
        print(
            f"{path.name}: {job['counts']}; preview draft version {job['preview_version']}; job {job['id']}"
        )
        if (
            any(row["errors"] for row in job["rows"])
            or job["counts"].get("invalid", 0)
            or job["counts"].get("conflict", 0)
        ):
            raise DemoError(
                "Preview has invalid/conflicting rows. Download error report in admin; no apply attempted."
            )
        if (
            confirm(
                "Inspect full preview in admin Imports. Type APPLY to apply only this batch to the unpublished draft: "
            ).strip()
            != "APPLY"
        ):
            raise DemoError(
                "Stopped before apply; staged preview and earlier batches retained. Rerun safely."
            )
        client.request("POST", base + "/validate")
        client.request("POST", base + "/apply", headers={"If-Match": f'"{job["preview_version"]}"'})
        print(f"{path.name}: applied transactionally to draft only.")
    diagnostics = client.request("GET", draft + "/graph/validation")
    folder = Path(get_settings().storage_root) / "private/muj"
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    out = folder / "latest-validation.json"
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(encode(diagnostics))
    print(
        f"Draft graph diagnostics saved privately: {out}. Review disconnected paths, unanchored destinations and mapping gaps. No warnings acknowledged, sources approved, review submitted or release published."
    )
    return state


class LocalClient(Client):
    # Base 3C helper intentionally disallows query strings. This helper permits only encoded filename.
    def request(self, method, path, *args, **kwargs):
        if "?" not in path:
            return super().request(method, path, *args, **kwargs)
        # Use the base opener/security behavior with an encoded filename in the URL temporarily.
        base, query = path.split("?", 1)
        from urllib.parse import parse_qs

        if set(parse_qs(query)) != {"filename"} or not base.endswith("/imports"):
            raise DemoError("Unexpected query refused")
        # Base's '?' guard applies to path; URL is local, query is exclusively a checked filename.
        original_url = self.url
        # Implement dedicated binary upload without relaxing the general client guard.
        from urllib.error import HTTPError, URLError
        from urllib.request import Request

        h = {"Origin": self.origin, "X-CSRF-Token": self.session["csrf_token"], **kwargs["headers"]}
        try:
            with self.opener.open(
                Request(original_url + path, data=kwargs["raw"], method=method, headers=h),
                timeout=60,
            ) as response:
                return json.loads(response.read())
        except (HTTPError, URLError, OSError):
            raise DemoError(
                "MUJ upload failed. Inspect admin history; rerun reconciles exact upload identity without saving credentials."
            ) from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, help="Original attached OSM file, read-only; required first run"
    )
    args = parser.parse_args()
    client = LocalClient()
    try:
        manifest, _ = prepared()
        account = prompt_login(client, "existing system administrator")
        if not any("user_admin" in g["permissions"] for g in account["grants"]):
            raise DemoError("Existing system administrator required")
        folder = Path(get_settings().storage_root) / "private/muj"
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = folder / (manifest["source_sha256"] + ".osm")
        source = args.source or target
        with source.open("rb") as stream:
            raw = stream.read(5 * 1024 * 1024 + 1)
        if hashlib.sha256(raw).hexdigest() != manifest["source_sha256"]:
            raise DemoError(
                "OSM checksum differs from pinned owner source. No campus/draft changes. Convert/review a new source explicitly."
            )
        if not target.exists():
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
        stage(client, ROOT)
    except (DemoError, OSError, ValueError, KeyboardInterrupt) as exc:
        # Never output arbitrary filesystem/HTTP exceptions, which could include local/private details.
        print(
            str(exc)
            if isinstance(exc, DemoError)
            else "Setup stopped; partial progress retained. Check source availability, worker and admin import history, then rerun."
        )
        raise SystemExit(2) from None
    finally:
        client.logout()


if __name__ == "__main__":
    main()
