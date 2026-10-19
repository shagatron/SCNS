import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.indoor import IndoorPatch
from app.services.indoor import pixel_length


def fixture():
    rows = json.loads(
        (Path(__file__).resolve().parents[3] / "data/demo/indoor/synthetic-ground.json").read_text()
    )["records"]
    return {
        "layer_id": str(uuid4()),
        "changes": [
            {"entity": e, "id": id, "data": r}
            for e, items in rows.items()
            for id, r in items.items()
        ],
    }


def test_strict_typed_pixel_fixture_and_full_polyline_length():
    payload = IndoorPatch.model_validate(fixture())
    assert len(payload.changes) == 22
    assert pixel_length([[0, 0], [3, 0], [3, 4]]) == 7


@pytest.mark.parametrize(
    "bad", ["duplicate", "geographic", "cost", "frame", "missing_layer", "nan", "crossfloor"]
)
def test_pixel_patch_rejects_client_scope_metric_and_malformed_geometry(bad):
    data = fixture()
    edge = next(c for c in data["changes"] if c["entity"] == "edges")["data"]
    if bad == "duplicate":
        data["changes"].append(data["changes"][0])
    elif bad == "geographic":
        edge["geometry"] = {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}
    elif bad == "cost":
        edge["distance_m"] = 99
    elif bad == "frame":
        edge["frame_id"] = str(uuid4())
    elif bad == "missing_layer":
        del data["layer_id"]
    elif bad == "nan":
        edge["polyline"][1][0] = float("nan")
    elif bad == "crossfloor":
        edge["floor_id"] = str(uuid4())
    with pytest.raises(ValidationError):
        IndoorPatch.model_validate(data)
