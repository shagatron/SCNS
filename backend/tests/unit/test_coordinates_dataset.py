import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.routing.coordinates import IndoorPoint, calibrated_length, indoor_to_leaflet
from app.schemas.dataset import Dataset

DEMO = Path(__file__).resolve().parents[3] / "data/demo/campus.json"


def test_calibration_axis_and_frame_separation():
    a, b = IndoorPoint("floor-1", 0, 0), IndoorPoint("floor-1", 200, 0)
    assert calibrated_length([a, b], 10 / 200) == 10
    assert indoor_to_leaflet(IndoorPoint("floor-1", 20, 30), 100) == (70, 20)
    with pytest.raises(ValueError):
        calibrated_length([a, IndoorPoint("floor-2", 200, 0)], 0.05)
    with pytest.raises(ValueError):
        calibrated_length([a, b], None)
    with pytest.raises(ValueError):
        indoor_to_leaflet(IndoorPoint("floor-1", 1, 200), 100)


def test_demo_valid_and_unknown_fields_rejected():
    data = json.loads(DEMO.read_text())
    bundle = Dataset.model_validate(data)
    assert len(bundle.buildings) == 3
    data["is_admin"] = True
    with pytest.raises(ValidationError):
        Dataset.model_validate(data)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_node",
        "duplicate",
        "swapped_endpoints",
        "invalid_range",
        "mixed_frame",
        "stairs_access",
        "unknown_building",
        "public_private",
    ],
)
def test_bundle_rejects_invalid_data(mutation):
    data = json.loads(DEMO.read_text())
    if mutation == "missing_node":
        data["edges"][0]["to_node_id"] = str(uuid4())
    if mutation == "duplicate":
        data["nodes"].append(data["nodes"][0])
    if mutation == "swapped_endpoints":
        data["edges"][0]["geometry"]["coordinates"].reverse()
    if mutation == "invalid_range":
        data["nodes"][0]["point"]["coordinates"][1] = 120
    if mutation == "mixed_frame":
        data["edges"][0]["frame_id"] = str(uuid4())
    if mutation == "stairs_access":
        data["edges"][0]["kind"] = "stairs"
    if mutation == "unknown_building":
        data["places"][0]["building_id"] = str(uuid4())
    if mutation == "public_private":
        data["nodes"][0]["visibility"] = "restricted"
    with pytest.raises(ValidationError):
        Dataset.model_validate(data)


def test_production_refuses_demo_and_unfinished_deployment():
    with pytest.raises(ValidationError):
        Settings(app_env="production")
