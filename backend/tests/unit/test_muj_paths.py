import json
import xml.etree.ElementTree as ET
from copy import deepcopy
from hashlib import sha256
from uuid import uuid4

import pytest

from app.cli import muj_paths
from app.cli.indoor_demo import DemoError
from app.cli.muj_naming import supported_changes
from app.services.muj_paths import account, draw, write_accounting
from app.services.muj_setup import CAMPUS_ID
from app.services.muj_update import ROOT2, correction, graph_records
from app.services.osm_conversion import convert, write_conversion
from tests.unit.test_osm_conversion import path, sample


def audit(raw, tmp_path):
    write_conversion(convert(raw, covered_segments_v2=True), tmp_path)
    return account(raw, tmp_path)


@pytest.mark.parametrize(
    "tag,forward",
    [
        ("", {True, False}),
        ('<tag k="oneway" v="yes"/>', {True, False}),
        ('<tag k="oneway:foot" v="yes"/>', {True}),
        ('<tag k="oneway:foot" v="-1"/>', {False}),
    ],
)
def test_every_pair_full_geometry_and_pedestrian_direction(tmp_path, tag, forward):
    raw = sample(path(tags=tag))
    report = audit(raw, tmp_path)
    assert report["counts"]["source_pairs"] == 2
    assert not report["unexplained_omissions"]
    assert all(
        {e["source_forward"] for e in r["stored_edges"]} == forward for r in report["segments"]
    )
    assert report["entrances"][0]["anchored"]
    write_accounting(report, tmp_path / "output")
    assert json.loads((tmp_path / "output/segments.json").read_bytes()) == report
    assert ET.fromstring(
        draw(report, raw, (75.56, 26.84, 75.565, 26.845), [], "Source only")
    ).tag.endswith("svg")
    assert b'"uid"' not in (tmp_path / "output/segments.json").read_bytes()


@pytest.mark.parametrize(
    "tag,reason",
    [
        ('<tag k="access" v="private"/>', "way:access_restriction"),
        ('<tag k="foot" v="no"/>', "way:foot_access"),
        ('<tag k="bridge" v="yes"/>', "way:grade_separated_requires_review"),
        ('<tag k="tunnel" v="yes"/>', "way:grade_separated_requires_review"),
        ('<tag k="level" v="0;1"/>', "way:unsupported_level_or_layer"),
        ('<tag k="indoor" v="yes"/>', "way:indoor_or_room"),
        (
            '<tag k="foot:conditional" v="yes @ (Mo)"/>',
            "way:conditional_or_directional_access_requires_review",
        ),
    ],
)
def test_access_grade_and_unknown_entrance_not_converted_to_connections(tmp_path, tag, reason):
    report = audit(sample(path(tags=tag)), tmp_path)
    assert all(not r["represented"] and reason in r["reasons"] for r in report["segments"])
    assert not report["entrances"][0]["anchored"]
    assert report["proposed_changes"] == []


def test_foot_permission_override_barrier_boundary_and_explicit_junctions(tmp_path):
    raw = sample(
        path(tags='<tag k="access" v="private"/><tag k="foot" v="yes"/>')
        + path(101, refs=(11, 15, 5, 6)),
        '<node id="15" lon="75.564" lat="26.843"/>',
    )
    report = audit(raw, tmp_path)
    assert all(r["represented"] for r in report["segments"] if r["way_id"] == 100)
    assert report["junctions"] == [{"node": 11, "ways": [100, 101], "stored_junction": True}]
    assert any(
        "pair:outside_exact_polygon_union_or_gap" in r["reasons"] for r in report["segments"]
    )
    assert not report["unexplained_omissions"]


class Fixture:
    def __init__(self):
        _, self.graph = graph_records(ROOT2)
        patch, _ = correction()
        for c in patch["changes"]:
            if c["data"]:
                self.graph[c["entity"]][c["id"]] = c["data"]
        for r in supported_changes():
            self.graph[r["entity"]][r["id"]]["label" if r["entity"] == "nodes" else "name"] = r[
                "proposed_name"
            ]
        self.graph["revision_version"] = 17
        self.session = {"user_id": str(uuid4()), "username": "owner", "csrf_token": "fixture"}
        self.raw = json.dumps(
            {**self.graph, "campus": {"id": str(CAMPUS_ID)}, "audience": "public"}
        ).encode()
        digest = sha256(self.raw).hexdigest()
        self.release = {
            "id": str(uuid4()),
            "campus_id": str(CAMPUS_ID),
            "dataset_revision_id": str(uuid4()),
            "checksum": "c" * 64,
            "artifact_checksum": digest,
        }
        self.release["artifact_url"] = (
            f"/api/v1/campuses/{CAMPUS_ID}/artifacts/{self.release['id']}/{digest}.json"
        )
        self.packet = {
            "id": self.release["dataset_revision_id"],
            "status": "frozen",
            "edit_version": 17,
            "checksum": "c" * 64,
            "sources": {},
            "validations": [],
        }
        self.dashboard = {
            "drafts_total": 1,
            "drafts": [{"id": str(uuid4()), "status": "draft", "edit_version": 9}],
        }
        self.calls = []

    def request(self, method, path, **kwargs):
        assert method == "GET", "Read-only helper cannot mutate datasets"
        self.calls.append(path)
        if path.endswith("/release"):
            return deepcopy(self.release)
        if "/artifacts/" in path:
            return self.raw
        return deepcopy(
            self.graph
            if path.endswith("/graph")
            else self.packet
            if path.endswith("/review")
            else self.dashboard
        )


def test_real_session_shape_current_release_e22_owner_drafts_and_safe_retries():
    client = Fixture()
    before = deepcopy(client.__dict__)
    first = muj_paths.preflight(client)
    assert first == muj_paths.preflight(client)
    assert not first["blockers"] and first["prior_correction"] == "already_applied"
    assert first["release"]["id"] == client.release["id"]
    assert first["proposed_changes"] == [] and first["drafts_created"] == first["graph_writes"] == 0
    assert all(r["actual"] == "TMA Pai Auditorium entrance" for r in first["naming_overlay"])
    assert client.graph == before["graph"] and client.dashboard == before["dashboard"]


def test_owner_edit_preserved_and_reported_not_silently_repaired():
    client = Fixture()
    r = supported_changes()[0]
    key = "label" if r["entity"] == "nodes" else "name"
    client.graph[r["entity"]][r["id"]][key] = "Owner custom name — preserve"
    before = deepcopy(client.graph)
    result = muj_paths.preflight(client)
    assert result["blockers"] and result["differences"]
    assert client.graph == before


@pytest.mark.parametrize("boundary", ["/release", "/graph", "/review", "/dashboard"])
def test_changed_evidence_stops_without_any_write(boundary):
    client = Fixture()
    original = client.request
    seen = 0

    def request(method, path, **kwargs):
        nonlocal seen
        result = original(method, path, **kwargs)
        if path.endswith(boundary):
            seen += 1
            if seen > (2 if boundary == "/release" else 1):
                result["changed"] = True
        return result

    client.request = request
    with pytest.raises(DemoError, match="Evidence changed"):
        muj_paths.preflight(client)


def test_no_unsafe_session_or_write_action(monkeypatch):
    client = Fixture()
    client.session = {"user": {"id": str(uuid4())}}
    with pytest.raises(DemoError, match="session identity"):
        muj_paths.preflight(client)
    assert not client.calls
    monkeypatch.setattr("sys.argv", ["muj_paths", "apply"])
    with pytest.raises(SystemExit):
        muj_paths.main()
