import json
from types import SimpleNamespace

import pytest

from app.schemas.imports import ImportOptions
from app.services.imports import error_csv, parse_content, safe_csv_cell, strict_json


def options(format="json"):
    return ImportOptions(
        format=format,
        campus_code="DEMO",
        timezone="Asia/Kolkata",
        source_rights="Synthetic",
        provenance="Test",
    )


@pytest.mark.parametrize(
    "value", ["=1+1", "+SUM(A1)", "-1+2", "@SUM(A1)", "\t=1+1", '  =HYPERLINK("bad")']
)
def test_spreadsheet_formula_cells_are_escaped(value):
    assert safe_csv_cell(value).startswith("'")
    job = SimpleNamespace(
        preview={
            "rows": [
                {
                    "row": 1,
                    "entity": "places",
                    "external_id": value,
                    "action": "invalid",
                    "errors": [value],
                    "warnings": [],
                }
            ]
        },
        failure=None,
    )
    assert "'" + value in error_csv(job) or value.startswith("  =")


@pytest.mark.parametrize("content", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'])
def test_duplicate_fields_and_nonfinite_json_are_rejected(content):
    with pytest.raises(ValueError):
        strict_json(content)


@pytest.mark.parametrize("content", [b"a,a\nx,y\n", b"a,b\nx\n", b"a,b\nx,y,z\n", b"a,b\nx,\x00\n"])
def test_csv_structure_rejected_before_staging(content):
    with pytest.raises(ValueError):
        parse_content(
            content, options("csv"), SimpleNamespace(code="DEMO", timezone="Asia/Kolkata")
        )


def test_geojson_crs_rejected():
    content = json.dumps(
        {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "EPSG:3857"}},
            "features": [],
        }
    ).encode()
    with pytest.raises(ValueError, match="WGS84"):
        parse_content(
            content, options("geojson"), SimpleNamespace(code="DEMO", timezone="Asia/Kolkata")
        )
