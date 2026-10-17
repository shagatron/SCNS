"""Real-session read-only path preflight and computed source-graph evidence.

All source-based rows and normal publication live in the rollback-only isolated
test transaction, never the retained cloud or Windows database.
"""

import base64
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.cli import muj_paths
from app.cli.indoor_demo import DemoError
from app.core.config import get_settings
from app.core.errors import DomainError
from app.models import Edge, Revision
from app.models.admin import AuditEvent, RoleAssignment
from app.routing.dijkstra import Arc, shortest_path
from app.routing.mixed import compute
from app.services.imports import stable_id
from app.services.muj_setup import CAMPUS_ID, ROOT
from app.services.muj_update import apply_reviewed as correct
from app.services.muj_update import plan
from app.services.osm_conversion import encode
from app.services.publication import public_projection, snapshot
from tests.integration.test_admin import sign_in, version
from tests.integration.test_imports import apply, preview
from tests.integration.test_muj import provision
from tests.integration.test_muj_update import Adapter
from tests.integration.test_muj_update import identity as muj_identity
from tests.integration.test_publication import reviewer as publication_reviewer

pytestmark = pytest.mark.integration


@pytest.fixture
def identity(db, bundle, seeded):
    return muj_identity.__wrapped__(db, bundle, seeded)


@pytest.fixture
def reviewer(db, bundle):
    return publication_reviewer.__wrapped__(db, bundle)


def evidence(data):
    """Production mixed/Dijkstra functions, actual PostGIS stored full lengths."""
    important = {
        "10780185180",
        "10780185181",
        "11573265515",
        "11573972967",
        "10828149259",
        "11664524407",
        "12585506492",
    }
    places = {str(stable_id(CAMPUS_ID, "places", "osm-node-" + i)) for i in important}
    # Every component with a destination has a representative in the matrix;
    # include all existing anchored entrances, not just the three known successes.
    places |= {a["place_id"] for a in data["anchors"].values()}
    rows = []
    for source in sorted(places):
        for target in sorted(places - {source}):
            for profile in ("shortest", "step_free"):
                for mode in ("metric", "directions_only"):
                    row = {
                        "source": source,
                        "source_name": data["places"][source]["name"],
                        "target": target,
                        "target_name": data["places"][target]["name"],
                        "profile": profile,
                        "objective": "distance_metres"
                        if mode == "metric"
                        else "fewest_eligible_traversals",
                    }
                    try:
                        route = compute(data, source, target, profile, mode)
                        row.update(
                            found=True,
                            distance_m=route["distance_m"],
                            stored_edge_count=len(route["segments"]),
                            edge_ids=[s["edge_id"] for s in route["segments"]],
                        )
                    except DomainError as exc:
                        row.update(
                            found=False,
                            code=exc.code,
                            distance_m=None,
                            stored_edge_count=0,
                            edge_ids=[],
                        )
                    rows.append(row)
    # Also test node-to-node reachability across ALL weak components, including
    # those without destinations. These are diagnostics, not public arrival claims.
    adjacency = {n: set() for n in data["nodes"]}
    for e in data["edges"].values():
        adjacency[e["from_node_id"]].add(e["to_node_id"])
        adjacency[e["to_node_id"]].add(e["from_node_id"])
    pending, representatives = set(adjacency), []
    while pending:
        todo, seen = [min(pending)], set()
        representatives.append(todo[0])
        while todo:
            n = todo.pop()
            if n not in seen:
                seen.add(n)
                todo.extend(adjacency[n] - seen)
        pending -= seen
    components = []
    for profile in ("shortest", "step_free"):
        for mode in ("metric", "directions_only"):
            arcs = [
                Arc(
                    i,
                    e["from_node_id"],
                    e["to_node_id"],
                    e["distance_m"] if mode == "metric" else 1,
                    e["kind"],
                    e["accessibility_status"],
                )
                for i, e in data["edges"].items()
            ]
            for source in representatives:
                for target in representatives:
                    if source == target:
                        continue
                    path = shortest_path(arcs, {source}, {target}, profile)
                    assert path is None
                    components.append(
                        {
                            "source_node": source,
                            "target_node": target,
                            "profile": profile,
                            "objective": mode,
                            "found": False,
                            "stored_edge_count": 0,
                            "distance_m": None,
                        }
                    )
    return {
        "format": "scns-muj-source-postgis-routes-v1",
        "qualification": "Isolated normal-API fixture; not actual Windows/E22 release or physical verification. Before and after are identical: no new graph changes proposed. OSM distances remain mapping estimates.",
        "destination_routes": rows,
        "component_pair_routes": components,
        "weak_components": len(representatives),
    }


def test_actual_cli_current_e22_release_permissions_retries_and_no_dataset_writes(
    client, db, bundle, identity, reviewer, monkeypatch, tmp_path
):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    headers = sign_in(client, identity)
    result = provision(client, bundle, headers)
    draft = result["draft_id"]
    base = f"/api/v1/admin/campuses/{CAMPUS_ID}/drafts/{draft}"
    fixture = SimpleNamespace(campus=SimpleNamespace(id=CAMPUS_ID))
    for batch in sorted(ROOT.glob("batch-*.json")):
        r = client.post(
            base + "/imports",
            params={"filename": batch.name},
            content=batch.read_bytes(),
            headers={
                **headers,
                "Content-Type": "application/octet-stream",
                "X-Import-Options": base64.b64encode((ROOT / "options.json").read_bytes()).decode(),
                "Idempotency-Key": batch.stem + "-path-audit-fixture",
            },
        )
        apply(client, fixture, {"id": draft}, headers, preview(db, r))
    adapter = Adapter(client, headers)
    correct(adapter, plan(adapter.request("GET", base + "/graph"), draft))
    db.add(RoleAssignment(user_id=reviewer[0].id, campus_id=CAMPUS_ID, role="reviewer_publisher"))
    db.flush()
    rh = sign_in(client, reviewer)
    p = client.get(base + "/review").json()
    r = client.post(
        base + f"/sources/{next(iter(p['sources']))}/approve",
        headers=version(rh, p["edit_version"]),
    )
    assert r.status_code == 200
    headers = sign_in(client, identity)
    # Apply the authorized E22 naming overlay before fixture publication, using
    # the existing naming API guard. Public artifact does not exist yet; provide
    # its unmodified source graph solely to the naming preview in this fixture.
    graph = client.get(base + "/graph").json()
    from app.cli.muj_naming import supported_changes, writable

    for row in supported_changes():
        entity, node = row["entity"], row["id"]
        fields = writable(entity, graph[entity][node])
        fields["label" if entity == "nodes" else "name"] = row["proposed_name"]
        if entity == "nodes":
            r = client.post(
                base + "/graph",
                json={"changes": [{"entity": entity, "id": node, "data": fields}]},
                headers=version(headers, graph["revision_version"]),
            )
        else:
            r = client.put(
                base + f"/catalog/places/{node}",
                json={"entity": "places", "data": fields},
                headers=version(headers, graph["revision_version"]),
            )
        assert r.status_code == 200, r.text
        graph = client.get(base + "/graph").json()
    p = client.get(base + "/review").json()
    r = client.post(
        base + "/validations",
        json={
            "routes": [
                {
                    "source": str(stable_id(CAMPUS_ID, "places", "osm-node-10780185181")),
                    "target": str(stable_id(CAMPUS_ID, "places", "osm-node-11573265515")),
                    "profile": profile,
                    "expected_found": profile == "shortest",
                    "cost_mode": "directions_only",
                    "maximum_distance_m": None,
                    "reason": "Isolated source-only fixture, not field verification.",
                }
                for profile in ("shortest", "step_free")
            ]
        },
        headers=version(headers, p["edit_version"]),
    )
    assert r.status_code == 200, r.text
    validation = r.json()
    assert validation["report"]["errors"] == 0
    reasons = {
        d[
            "id"
        ]: "Explicit isolated software-fixture review of source-only limitation; no physical/accessibility/institutional approval."
        for d in validation["report"]["diagnostics"]
    }
    p = client.get(base + "/review").json()
    r = client.post(
        base + "/submissions",
        json={"validation_id": validation["id"], "acknowledgements": reasons},
        headers=version(headers, p["edit_version"]),
    )
    assert r.status_code == 200, r.text
    submission = r.json()
    rh = sign_in(client, reviewer)
    r = client.post(
        base + f"/submissions/{submission['id']}/decision",
        json={
            "decision": "approve",
            "notes": "Different test application account, no independent human claim.",
            "acknowledgements": reasons,
        },
        headers=version(rh, submission["edit_version"]),
    )
    assert r.status_code == 200, r.text
    r = client.post(
        base + "/publish",
        json={
            "submission_id": submission["id"],
            "expected_release_id": None,
            "key": "isolated-path-e22-fixture",
        },
        headers=version(rh, r.json()["edit_version"]),
    )
    assert r.status_code == 200, r.text
    headers = sign_in(client, identity)
    # Publish a normally created clone as well: the actual Windows current E22
    # release has a parent and cannot be reconstructed from its small diff alone.
    first_release = client.get(f"/api/v1/campuses/{CAMPUS_ID}/release").json()
    created = client.post(
        f"/api/v1/admin/campuses/{CAMPUS_ID}/drafts",
        headers={**headers, "Idempotency-Key": "isolated-path-clone-fixture"},
    )
    assert created.status_code == 201, created.text
    draft = created.json()["id"]
    base = f"/api/v1/admin/campuses/{CAMPUS_ID}/drafts/{draft}"
    cloned = client.get(base + "/review").json()
    assert cloned["diff"] == []
    validation_payload = {
        "routes": [
            {
                "source": str(stable_id(CAMPUS_ID, "places", "osm-node-10780185181")),
                "target": str(stable_id(CAMPUS_ID, "places", "osm-node-11573265515")),
                "profile": profile,
                "expected_found": profile == "shortest",
                "cost_mode": "directions_only",
                "maximum_distance_m": None,
                "reason": "Explicit disposable source fixture expectation; unknown accessibility stays unknown.",
            }
            for profile in ("shortest", "step_free")
        ]
    }
    validation = client.post(
        base + "/validations",
        json=validation_payload,
        headers=version(headers, cloned["edit_version"]),
    )
    assert validation.status_code == 200, validation.text
    reasons = {
        d[
            "id"
        ]: "Explicit isolated fixture reviewer finding assessment, not an owner/publication recommendation or physical verification."
        for d in validation.json()["report"]["diagnostics"]
    }
    submission = client.post(
        base + "/submissions",
        json={"validation_id": validation.json()["id"], "acknowledgements": reasons},
        headers=version(headers, cloned["edit_version"]),
    )
    assert submission.status_code == 200, submission.text
    rh = sign_in(client, reviewer)
    approved = client.post(
        base + f"/submissions/{submission.json()['id']}/decision",
        json={
            "decision": "approve",
            "notes": "Separate test application account only, no independent human review.",
            "acknowledgements": reasons,
        },
        headers=version(rh, submission.json()["edit_version"]),
    )
    assert approved.status_code == 200, approved.text
    published = client.post(
        base + "/publish",
        json={
            "submission_id": submission.json()["id"],
            "expected_release_id": first_release["id"],
            "key": "isolated-path-clone-publication",
        },
        headers=version(rh, approved.json()["edit_version"]),
    )
    assert published.status_code == 200, published.text
    headers = sign_in(client, identity)
    old_release = client.get(f"/api/v1/campuses/{CAMPUS_ID}/release").json()
    from uuid import UUID

    before_graph = snapshot(db, db.get(Revision, UUID(draft)))
    before_drafts = db.scalar(select(func.count()).select_from(Revision))
    before_audits = db.scalar(
        select(func.count()).select_from(AuditEvent).where(~AuditEvent.action.like("auth.%"))
    )

    class HTTP:
        session = client.get("/api/v1/admin/session").json()

        def request(self, method, path, payload=None, *, binary=False, **kwargs):
            assert method == "GET"
            response = client.get(path, params=kwargs.get("query"))
            if not response.is_success:
                raise DemoError(f"Normal API refused HTTP {response.status_code}")
            return response.content if binary else response.json()

        def logout(self):
            assert client.post("/api/v1/admin/logout", headers=headers).status_code == 204

    http = HTTP()
    assert "user_id" in http.session and "user" not in http.session
    report = muj_paths.preflight(http)
    assert not report["blockers"], report["blockers"]
    assert report == muj_paths.preflight(http)
    assert report["release"]["id"] == old_release["id"] and report["graph_writes"] == 0
    assert len(report["frozen_ancestry"]) == 2
    assert report["naming_overlay"][0]["actual"] == "TMA Pai Auditorium entrance"
    monkeypatch.setattr(muj_paths, "Client", lambda **kwargs: http)
    monkeypatch.setattr(muj_paths, "prompt_login", lambda *_: None)
    monkeypatch.setattr("sys.argv", ["muj_paths", "preflight"])
    muj_paths.main()
    saved = list((tmp_path / "private/muj-path-audit").glob("preflight-*.json"))
    assert len(saved) == 1 and json.loads(saved[0].read_bytes())["release"] == old_release
    assert client.get(base + "/graph").status_code == 401
    headers = sign_in(client, identity)
    assert snapshot(db, db.get(Revision, UUID(draft))) == before_graph
    assert db.scalar(select(func.count()).select_from(Revision)) == before_drafts
    assert (
        db.scalar(
            select(func.count()).select_from(AuditEvent).where(~AuditEvent.action.like("auth.%"))
        )
        == before_audits
    )
    assert client.get(f"/api/v1/campuses/{CAMPUS_ID}/release").json() == old_release
    # Permission removal is itself inside a nested rollback, not a retained edit.
    with db.begin_nested() as tx:
        for role in list(
            db.scalars(
                select(RoleAssignment).where(
                    RoleAssignment.user_id == identity[0].id, RoleAssignment.campus_id == CAMPUS_ID
                )
            )
        ):
            db.delete(role)
        db.flush()
        with pytest.raises(DemoError, match="403"):
            muj_paths.preflight(http)
        tx.rollback()
    data = public_projection(snapshot(db, db.get(Revision, UUID(draft))))
    routes = evidence(data)
    metric = next(
        r
        for r in routes["destination_routes"]
        if r["source_name"] == "University Entrance"
        and r["target_name"] == "Mapped entrance 10828149259"
        and r["objective"] == "distance_metres"
        and r["profile"] == "shortest"
    )
    assert (
        metric["distance_m"] == pytest.approx(513.10, abs=0.01)
        and metric["stored_edge_count"] == 13
    )
    if output := os.environ.get("SCNS_PATH_EVIDENCE"):
        Path(output).write_bytes(encode(routes))
    assert db.scalar(select(func.count()).select_from(Edge)) > 700
