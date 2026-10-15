import xml.etree.ElementTree as ET

import pytest
from shapely.geometry import shape

from app.services.osm_conversion import convert, encode, write_conversion


def sample(ways="", extra_nodes="", relations=""):
    # Invented coordinates only. Real pinned data is tested separately through staged imports.
    return (
        """<osm version="0.6">
      <node id="1" lon="75.56" lat="26.84"/><node id="2" lon="75.565" lat="26.84"/>
      <node id="3" lon="75.565" lat="26.845"/><node id="4" lon="75.56" lat="26.845"/>
      <node id="5" lon="75.566" lat="26.84"/><node id="6" lon="75.568" lat="26.84"/>
      <node id="7" lon="75.568" lat="26.845"/><node id="8" lon="75.566" lat="26.845"/>
      <node id="10" lon="75.561" lat="26.841" user="private-contributor" uid="999"><tag k="entrance" v="yes"/><tag k="name" v="Test entrance"/></node>
      <node id="11" lon="75.562" lat="26.842"/><node id="12" lon="75.563" lat="26.841"/>
      <way id="495716022"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="1"/></way>
      <way id="1158554635"><nd ref="5"/><nd ref="6"/><nd ref="7"/><nd ref="8"/><nd ref="5"/></way>
    """
        + extra_nodes
        + ways
        + relations
        + "</osm>"
    ).encode()


def path(identity=100, tags="", refs=(10, 11, 12)):
    return (
        f'<way id="{identity}">'
        + "".join(f'<nd ref="{r}"/>' for r in refs)
        + '<tag k="highway" v="footway"/>'
        + tags
        + "</way>"
    )


def records(result, entity):
    return [r for b in result["bundles"] for r in b["records"] if r["entity"] == entity]


def test_determinism_shared_node_polylines_unknown_and_no_contributor_metadata(tmp_path):
    raw = sample(path(tags='<tag k="oneway" v="yes"/><tag k="wheelchair" v="yes"/>'))
    a, b = convert(raw), convert(raw)
    assert encode(a) == encode(b)
    edge = records(a, "edges")
    assert len(edge) == 2  # Motor direction does not constrain walking.
    assert len(edge[0]["data"]["geometry"]["coordinates"]) == 3
    assert all(r["data"]["accessibility_status"] == "unknown" for r in edge)
    assert b"private-contributor" not in encode(a) and b'"uid"' not in encode(a)
    assert shape(a["report"]["scope"]["coverage"]).geom_type == "MultiPolygon"
    assert len(a["report"]["components"]) == 1
    write_conversion(a, tmp_path)
    old = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    write_conversion(b, tmp_path)
    assert old == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize(
    "tags,expected",
    [
        ('<tag k="foot" v="no"/>', 0),
        ('<tag k="access" v="private"/>', 0),
        ('<tag k="access" v="private"/><tag k="foot" v="yes"/>', 2),
        ('<tag k="oneway:foot" v="yes"/>', 1),
        ('<tag k="oneway:foot" v="-1"/>', 1),
        ('<tag k="indoor" v="yes"/>', 0),
        ('<tag k="level" v="0;1"/>', 0),
        ('<tag k="level" v="1"/>', 0),
        ('<tag k="level" v="0"/>', 2),
        ('<tag k="bridge" v="yes"/>', 0),
        ('<tag k="tunnel" v="yes"/>', 0),
        ('<tag k="area" v="yes"/>', 0),
        ('<tag k="foot:conditional" v="yes @ (Mo)"/>', 0),
    ],
)
def test_access_direction_and_levels(tags, expected):
    result = convert(sample(path(tags=tags)))
    assert len(records(result, "edges")) == expected
    if '"-1"' in tags:
        assert records(result, "edges")[0]["data"]["from_node_id"] == "osm-node-12"


def test_crossing_lines_dont_connect_and_barriers_dont_disappear():
    extra = '<node id="13" lon="75.561" lat="26.842"/><node id="14" lon="75.563" lat="26.842"/>'
    result = convert(sample(path(refs=(10, 12)) + path(101, refs=(13, 14)), extra))
    assert len(result["report"]["components"]) == 2
    raw = sample(path()).replace(
        b'<node id="11" lon="75.562" lat="26.842"/>',
        b'<node id="11" lon="75.562" lat="26.842"><tag k="barrier" v="gate"/></node>',
    )
    result = convert(raw)
    assert not records(result, "edges")
    assert any(
        x["reason"] == "blocked_or_level_node_segment" for x in result["report"]["decisions"]
    )


def test_missing_references_offcampus_and_rooms_are_reported():
    result = convert(
        sample(
            path(refs=(10, 999))
            + path(101, refs=(2, 5))
            + '<way id="102"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="1"/><tag k="building" v="yes"/><tag k="room" v="classroom"/></way>'
        )
    )
    reasons = result["report"]["exclusion_reason_counts"]
    assert reasons["missing_node_reference"] == 1
    assert reasons["path_outside_exact_campus_coverage_or_cross_campus_gap"] == 1
    assert reasons["room_or_level_tagged_building_quarantined"] == 1
    assert not records(result, "buildings")


def test_holes_duplicate_members_and_incomplete_relations():
    outer = '<way id="20"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="1"/><tag k="building" v="yes"/></way>'
    inner = '<way id="21"><nd ref="10"/><nd ref="11"/><nd ref="12"/><nd ref="10"/></way>'
    relation = '<relation id="30"><member type="way" ref="20" role="outer"/><member type="way" ref="21" role="inner"/><tag k="type" v="multipolygon"/><tag k="building" v="yes"/><tag k="name" v="Courtyard building"/></relation>'
    result = convert(sample(outer + inner, relations=relation))
    buildings = records(result, "buildings")
    assert len(buildings) == 1 and len(buildings[0]["data"]["footprint"]["coordinates"]) == 2
    assert not records(result, "anchors")  # A representative point never becomes a door.
    broken = convert(sample(outer + inner, relations=relation.replace('ref="21"', 'ref="999"')))
    assert not records(broken, "buildings")
    assert (
        broken["report"]["exclusion_reason_counts"]["missing_or_unsupported_relation_member"] == 1
    )


def test_invalid_campus_and_xml_are_rejected_without_repair():
    with pytest.raises(ValueError, match="DTD"):
        convert(b"<!DOCTYPE osm><osm/>")
    root = ET.fromstring(sample())
    root.remove(root.find("way"))
    with pytest.raises(ValueError, match="missing"):
        convert(ET.tostring(root))


def test_element_order_does_not_change_import_identities_or_graph():
    raw = sample(path())
    root = ET.fromstring(raw)
    root[:] = list(reversed(root[:]))
    assert convert(raw)["bundles"] == convert(ET.tostring(root))["bundles"]


def test_prepared_manifest_rejects_tampering_and_unlisted_batches(tmp_path):
    from app.services.muj_setup import prepared

    write_conversion(convert(sample(path())), tmp_path)
    prepared(tmp_path)
    (tmp_path / "batch-999.json").write_text("{}")
    with pytest.raises(ValueError, match="Unlisted"):
        prepared(tmp_path)
    (tmp_path / "batch-999.json").unlink()
    (tmp_path / "batch-001.json").write_text("{}")
    with pytest.raises(ValueError, match="checksum"):
        prepared(tmp_path)


@pytest.mark.parametrize(
    "raw",
    [b"<osm", '<!DOCTYPE osm [<!ENTITY x "entity">]><osm/>'.encode("utf-16"), b"\xff\xfe\x00"],
)
def test_malformed_or_encoded_xml_cannot_bypass_input_guard(raw):
    with pytest.raises(ValueError, match="XML"):
        convert(raw)


def test_mapped_repeated_node_loops_split_without_inventing_crossings_or_losing_curves():
    # One OSM way explicitly revisits its junction; both arcs of its loop are real geometry.
    result = convert(sample(path(refs=(10, 11, 12, 10))))
    edges = records(result, "edges")
    assert len(edges) == 4
    assert len({e["external_id"] for e in edges}) == 4
    assert len(records(result, "nodes")) == 2
    assert sum(len(e["data"]["geometry"]["coordinates"]) - 1 for e in edges) == 6
    # Repeated tracing of the same mapped physical segment must not duplicate import identities.
    repeated = convert(sample(path(refs=(10, 11, 12, 10, 11))))
    all_ids = [(r["entity"], r["external_id"]) for b in repeated["bundles"] for r in b["records"]]
    assert len(all_ids) == len(set(all_ids))
    assert repeated["report"]["exclusion_reason_counts"]["duplicate_directed_way_segment"] > 0


def test_v2_retains_only_covered_source_runs_without_changing_v1_or_inventing_clipping():
    raw = sample(path(refs=(10, 11, 12, 20)), '<node id="20" lon="75.57" lat="26.848"/>')
    assert not records(convert(raw), "edges")
    v2 = convert(raw, covered_segments_v2=True)
    edges = records(v2, "edges")
    assert len(edges) == 2
    assert all(len(e["data"]["geometry"]["coordinates"]) == 3 for e in edges)
    assert {n["external_id"] for n in records(v2, "nodes")} == {"osm-node-10", "osm-node-12"}
    assert all(e["data"]["accessibility_status"] == "unknown" for e in edges)
    assert v2["report"]["converter"] != convert(raw)["report"]["converter"]
    # Both campus endpoints are real, but the pair between them crosses the gap.
    gap = convert(sample(path(refs=(2, 5))), covered_segments_v2=True)
    assert not records(gap, "edges")


@pytest.mark.parametrize(
    "tag",
    [
        '<tag k="tunnel" v="yes"/>',
        '<tag k="layer" v="-1"/>',
        '<tag k="access" v="private"/>',
        '<tag k="indoor" v="yes"/>',
    ],
)
def test_v2_does_not_weaken_access_or_grade_guards(tag):
    assert not records(convert(sample(path(tags=tag)), covered_segments_v2=True), "edges")


def test_v2_covered_run_respects_explicit_reverse_pedestrian_direction():
    raw = sample(
        path(refs=(10, 11, 12, 20), tags='<tag k="oneway:foot" v="-1"/>'),
        '<node id="20" lon="75.57" lat="26.848"/>',
    )
    edges = records(convert(raw, covered_segments_v2=True), "edges")
    assert len(edges) == 1
    assert edges[0]["data"]["from_node_id"] == "osm-node-12"
    assert edges[0]["data"]["to_node_id"] == "osm-node-10"
