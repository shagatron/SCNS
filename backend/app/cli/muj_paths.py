"""Read-only MUJ path accounting and actual-current-release preflight. No apply mode."""

import argparse
import hashlib
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

from app.cli.indoor_demo import Client, DemoError, persist, prompt_login
from app.cli.muj_naming import published, supported_changes
from app.core.config import get_settings
from app.services.muj_setup import CAMPUS_ID, ROOT
from app.services.muj_update import ROOT2, comparable, correction, graph_records, plan
from app.services.osm_conversion import encode


def preflight(client):
    """Bind actual current publication, frozen graph, review and editable draft list.

    No old release UUID is assumed; no editable draft is selected or created.
    Only GETs are issued here. Authentication/logout remain normal session actions.
    """
    try:
        owner = str(UUID(client.session["user_id"]))
    except (KeyError, TypeError, ValueError, AttributeError):
        raise DemoError("Unexpected authenticated session identity; no dataset writes.") from None
    release, artifact = published(client)
    prefix = f"/api/v1/admin/campuses/{CAMPUS_ID}"
    base = prefix + f"/drafts/{UUID(release['dataset_revision_id'])}"
    dashboard = client.request("GET", prefix + "/dashboard")
    packet = client.request("GET", base + "/review")
    graph = client.request("GET", base + "/graph")
    blockers = []
    if packet["status"] != "frozen" or packet["id"] != release["dataset_revision_id"]:
        blockers.append("Published parent is not the expected immutable frozen revision.")
    if (
        packet["edit_version"] != graph["revision_version"]
        or packet["checksum"] != release["checksum"]
    ):
        blockers.append("Frozen graph/review/publication version or checksum disagrees.")
    if dashboard["drafts_total"] != len(dashboard["drafts"]):
        blockers.append(
            "Draft list is truncated or unavailable under this account; inspect normal admin UI."
        )
    changes, _ = correction()
    _, expected = graph_records(ROOT2)
    for c in changes["changes"]:
        if c["data"] is not None:
            expected[c["entity"]][c["id"]] = c["data"]
    # E22 is the sole permitted source-supported naming overlay. Never replay it.
    names = []
    for r in supported_changes():
        entity, identity = r["entity"], r["id"]
        field = "label" if entity == "nodes" else "name"
        expected[entity][identity][field] = r["proposed_name"]
        names.append(
            {
                "entity": entity,
                "id": identity,
                "actual": graph[entity].get(identity, {}).get(field),
                "expected": r["proposed_name"],
            }
        )
    differences = []
    for entity in expected:
        for identity in sorted(set(expected[entity]) | set(graph[entity])):
            if comparable(entity, graph[entity].get(identity)) != expected[entity].get(identity):
                differences.append(
                    {
                        "entity": entity,
                        "id": identity,
                        "reason": "Current record differs from retained v2 plus authorized E22; preserve and investigate, never overwrite.",
                    }
                )
    if differences:
        blockers.append(
            "Current dataset differs from the audited preparation plus E22. No correction is authorized."
        )
    correction_state = plan(graph, release["dataset_revision_id"])["state"]
    if correction_state != "already_applied":
        blockers.append(
            "Prior correction is not already applied; do not replay it through this audit."
        )
    # Re-read every evidence boundary, including draft list. A changed restriction
    # generation is included in the release descriptor and safely stops this run.
    if (
        client.request("GET", f"/api/v1/campuses/{CAMPUS_ID}/release") != release
        or client.request("GET", base + "/graph") != graph
        or client.request("GET", base + "/review") != packet
        or client.request("GET", prefix + "/dashboard") != dashboard
    ):
        raise DemoError(
            "Evidence changed during preflight; discard this run and retry read-only. No dataset writes."
        )
    return {
        "format": "scns-muj-path-preflight-v1",
        "verified_by": owner,
        "release": release,
        "draft_version": packet["edit_version"],
        "content_checksum": packet["checksum"],
        "authenticated_graph_sha256": hashlib.sha256(encode(graph)).hexdigest(),
        "source_sha256": changes["source_sha256"],
        "editable_or_review_drafts": dashboard["drafts"],
        "sources": packet["sources"],
        "validation_history": packet["validations"],
        "graph_counts": {k: len(graph[k]) for k in expected},
        "public_counts": {k: len(artifact[k]) for k in expected},
        "naming_overlay": names,
        "differences": differences,
        "blockers": blockers,
        "prior_correction": correction_state,
        "proposed_changes": [],
        "graph_writes": 0,
        "drafts_created": 0,
        "decision": "No further unambiguous source-supported correction found. No apply action or empty draft. Existing publication remains active.",
        "evidence_limit": "Owner-run Windows API snapshot only when run there; source mapping is not physical, institutional or accessibility verification. Login/logout use normal audited sessions.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_subparsers(dest="mode", required=True)
    offline = mode.add_parser("audit", help="Offline complete source-pair accounting; no database")
    offline.add_argument("--source", type=Path, required=True)
    offline.add_argument("--output", type=Path, required=True)
    mode.add_parser("preflight", help="Authenticated actual-current-release read-only evidence")
    args = parser.parse_args()
    if args.mode == "audit":
        from app.services.muj_paths import account, write_accounting

        output = args.output.resolve()
        protected = [ROOT.resolve(), ROOT2.resolve(), args.source.resolve()]
        repo = ROOT.resolve().parents[1]
        if (
            any(output == p or output in p.parents or p in output.parents for p in protected)
            or output == repo
        ):
            parser.error(
                "Use a separate diagnostic output directory, never source/preparation/root"
            )
        with args.source.open("rb") as stream:
            raw = stream.read(5 * 1024 * 1024 + 1)
        # Verify v1 as well; existing import artifacts are not rewritten.
        account(raw, ROOT)
        report = account(raw, ROOT2)
        write_accounting(report, output)
        print(
            json.dumps(
                {
                    "counts": report["counts"],
                    "unexplained_omissions": report["unexplained_omissions"],
                    "proposed_changes": [],
                }
            )
        )
        if report["unexplained_omissions"]:
            raise SystemExit(
                "Unexplained segments require investigation; no graph patch generated."
            )
        return
    client = Client(origin=os.environ.get("PUBLIC_APP_URL", "http://localhost:5173"))
    try:
        prompt_login(client, "MUJ owner (read-only path preflight)")
        report = preflight(client)
        folder = Path(get_settings().storage_root) / "private/muj-path-audit"
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = folder / f"preflight-{uuid4()}.json"
        persist(path, report)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"Private report: {path}. No draft created, graph writes, approval or publication.")
        if report["blockers"]:
            raise DemoError("Preflight differences require inspection; preserve existing dataset.")
    except (DemoError, ValueError) as exc:
        raise SystemExit(str(exc)) from None
    finally:
        client.logout()


if __name__ == "__main__":
    main()
