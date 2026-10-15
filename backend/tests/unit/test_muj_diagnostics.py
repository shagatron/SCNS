import xml.etree.ElementTree as ET

import pytest

from app.services.muj_diagnostics import diagnose, diagnostic_svg, write_diagnostics
from app.services.osm_conversion import convert, encode, write_conversion
from tests.unit.test_osm_conversion import path, sample


def test_diagnostics_trace_internal_source_nodes_without_proximity_connections(tmp_path):
    extra = '<node id="13" lon="75.5615" lat="26.8415"/><node id="14" lon="75.5635" lat="26.843"/>'
    raw = sample(
        path()
        + path(101, refs=(11, 14), tags='<tag k="bridge" v="yes"/>')
        + path(102, refs=(13, 14)),
        extra,
    )
    write_conversion(convert(raw), tmp_path)
    original = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    report = diagnose(raw, tmp_path)
    assert len(report["components"]) == 2
    # Internal vertex 11 is not a stored junction, but its original identity is traced.
    assert 11 in report["components"][0]["source_node_ids"]
    excluded = report["excluded_highways"][0]
    assert excluded["way"] == 101
    assert excluded["retained_components_touched"] == [1, 2]
    assert excluded["shared_source_nodes"] == [
        {"node": 11, "components": [1]},
        {"node": 14, "components": [2]},
    ]
    assert "private-contributor" not in encode(report).decode()
    assert encode(diagnose(raw, tmp_path)) == encode(report)
    output = tmp_path / "diagnostic"
    write_diagnostics(report, output)
    assert (output / "diagnostic.json").read_bytes() == encode(report)
    for filename in ["components.svg", "subway.svg"]:
        figure = ET.fromstring((output / filename).read_bytes())
        assert figure.tag.endswith("svg")
        assert "EXCLUDED source path" in (output / filename).read_text()
    assert original == {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}


def test_changed_original_or_derivative_fails_before_diagnostic_output(tmp_path):
    raw = sample(path())
    write_conversion(convert(raw), tmp_path)
    with pytest.raises(ValueError, match="Original checksum"):
        diagnose(raw + b" ", tmp_path)
    (tmp_path / "batch-001.json").write_text("{}")
    with pytest.raises(ValueError, match="derivative checksum"):
        diagnose(raw, tmp_path)


def test_diagnostics_refuse_changed_converter_without_mutating_pinned_data(tmp_path, monkeypatch):
    from app.services import muj_diagnostics

    raw = sample(path())
    write_conversion(convert(raw), tmp_path)
    changed = convert(raw)
    changed["bundles"][0]["records"].pop()
    monkeypatch.setattr(muj_diagnostics, "convert", lambda raw: changed)
    with pytest.raises(ValueError, match="version separately"):
        diagnose(raw, tmp_path)


def test_diagnostic_svg_has_no_invented_candidate_connections(tmp_path):
    raw = sample(path())
    write_conversion(convert(raw), tmp_path)
    report = diagnose(raw, tmp_path)
    figure = diagnostic_svg(report)
    # Only the one physical source polyline, rather than both directed copies.
    assert figure.count("<polyline") == 1
    assert "no survey, access or accessibility verification" in figure


@pytest.mark.parametrize("location", ["root", "inside", "ancestor", "source"])
def test_diagnostic_cli_refuses_preparation_and_source_destinations(
    tmp_path, monkeypatch, location
):
    from app.cli import muj_diagnostics

    root = tmp_path / "preparation"
    source = tmp_path / "original.osm"
    output = {"root": root, "inside": root / "nested", "ancestor": tmp_path, "source": source}[
        location
    ]
    monkeypatch.setattr(muj_diagnostics, "ROOT", root)
    monkeypatch.setattr("sys.argv", ["muj_diagnostics", str(source), "--output", str(output)])
    with pytest.raises(SystemExit) as error:
        muj_diagnostics.main()
    assert error.value.code == 2
    assert not root.exists() and not source.exists()
