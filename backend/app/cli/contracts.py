import json
from pathlib import Path

from app.main import app
from app.schemas.dataset import Dataset
from app.schemas.imports import ImportBundle

root = Path(__file__).resolve().parents[3]
(root / "docs/architecture/openapi.json").write_text(json.dumps(app.openapi(), indent=2) + "\n")
(root / "data/templates/dataset-v1.schema.json").write_text(
    json.dumps(Dataset.model_json_schema(), indent=2) + "\n"
)

(root / "data/templates/import-v1/bundle.schema.json").write_text(
    json.dumps(ImportBundle.model_json_schema(), indent=2) + "\n"
)
