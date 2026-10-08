import json
from pathlib import Path

from app.main import app
from app.schemas.api import GPSObservation
from app.schemas.closures import ClosureCreate, ClosureDecision
from app.schemas.connections import ConnectionsPatch
from app.schemas.dataset import Dataset
from app.schemas.floorplans import CalibrationInput, FloorInput, UploadInput
from app.schemas.imports import ImportBundle
from app.schemas.indoor import IndoorPatch
from app.schemas.publication import SourceInput
from app.schemas.qr import Installation, MarkerCreate

root = Path(__file__).resolve().parents[3]
(root / "docs/architecture/openapi.json").write_text(json.dumps(app.openapi(), indent=2) + "\n")
(root / "data/templates/dataset-v1.schema.json").write_text(
    json.dumps(Dataset.model_json_schema(), indent=2) + "\n"
)

(root / "data/templates/import-v1/bundle.schema.json").write_text(
    json.dumps(ImportBundle.model_json_schema(), indent=2) + "\n"
)

(root / "data/templates/publication-v1/source.schema.json").write_text(
    json.dumps(SourceInput.model_json_schema(), indent=2) + "\n"
)

for name, model in [
    ("floor", FloorInput),
    ("upload", UploadInput),
    ("calibration", CalibrationInput),
]:
    (root / f"data/templates/floorplan-v1/{name}.schema.json").write_text(
        json.dumps(model.model_json_schema(), indent=2) + "\n"
    )

(root / "data/templates/indoor-v1/patch.schema.json").write_text(
    json.dumps(IndoorPatch.model_json_schema(), indent=2) + "\n"
)

(root / "data/templates/connections-v1/patch.schema.json").write_text(
    json.dumps(ConnectionsPatch.model_json_schema(), indent=2) + "\n"
)

for name, model in [("marker", MarkerCreate), ("installation", Installation)]:
    (root / f"data/templates/qr-v1/{name}.schema.json").write_text(
        json.dumps(model.model_json_schema(), indent=2) + "\n"
    )

for name, model in [("closure", ClosureCreate), ("decision", ClosureDecision)]:
    (root / f"data/templates/closures-v1/{name}.schema.json").write_text(
        json.dumps(model.model_json_schema(), indent=2) + "\n"
    )

(root / "data/templates/location-v1/observation.schema.json").write_text(
    json.dumps(GPSObservation.model_json_schema(), indent=2) + "\n"
)
