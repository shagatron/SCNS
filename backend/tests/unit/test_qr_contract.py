import io
from types import SimpleNamespace
from uuid import uuid4
from xml.etree import ElementTree

import pypdfium2
import pytest
import zxingcpp
from PIL import Image
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.errors import DomainError
from app.routing.mixed import compute
from app.schemas.api import RouteRequest
from app.services import qr_signs
from app.services.qr import target, target_hash
from tests.unit.test_connection_costs import outdoor


@pytest.mark.parametrize("format", ["svg", "png", "pdf"])
def test_printable_sign_is_readable_and_encoded_locally(monkeypatch, format):
    monkeypatch.setenv("PUBLIC_APP_URL", "https://campus.example")
    get_settings.cache_clear()
    marker = SimpleNamespace(id=uuid4(), label="Synthetic <Gate> & entrance", state="active")
    result = qr_signs.render(marker, format)
    expected = f"https://campus.example/q/{marker.id}"
    if format == "svg":
        root = ElementTree.fromstring(result)
        content = "".join(root.itertext())
        assert expected in content and marker.label in content
        assert "Confirm this location" in content
    else:
        if format == "pdf":
            with pypdfium2.PdfDocument(result) as doc:
                assert len(doc) == 1
                page = doc[0]
                image = page.render(scale=2).to_pil()
                decoded = zxingcpp.read_barcodes(image)
                page.close()
        else:
            with Image.open(io.BytesIO(result)) as image:
                image.load()
                decoded = zxingcpp.read_barcodes(image)
        assert [code.text for code in decoded] == [expected]
    get_settings.cache_clear()


@pytest.mark.parametrize(
    "url",
    [
        "http://campus.example",
        "https://user:pass@campus.example",
        "https://campus.example/x",
        "https://campus.example?tracking=1",
        "https://campus.example/#x",
    ],
)
def test_sign_origin_cannot_be_spoofed_or_use_nonlocal_http(url):
    with pytest.raises(ValidationError):
        Settings(public_app_url=url)


def test_qr_start_uses_exact_stored_node_without_inventing_a_place_or_anchor():
    data = outdoor()
    del data["places"]["a"]
    del data["anchors"]["aa"]
    result = compute(data, None, "b", start_node=("outdoor", "x"))
    assert result["distance_m"] == 256.88 and result["source_anchor_id"] is None
    assert result["segments"][0]["from_node_id"] == "x"
    assert compute(data, None, "b", start_node=("outdoor", "y"))["distance_m"] == 0
    with pytest.raises(DomainError):
        compute(data, None, "b", start_node=("outdoor", "missing"))
    data["edges"]["e"]["accessibility_status"] = "unknown"
    with pytest.raises(DomainError, match="eligible route"):
        compute(data, None, "b", "step_free", start_node=("outdoor", "x"))


def test_physical_fingerprint_ignores_labels_but_detects_moved_nodes():
    node = {"id": "x", "label": "X", "point": {"coordinates": [0, 0]}}
    data = {"nodes": {"x": node}}
    initial = target_hash(target(data, "outdoor", "x"))
    node["label"] = "New name"
    assert target_hash(target(data, "outdoor", "x")) == initial
    node["point"]["coordinates"][0] = 0.001
    assert target_hash(target(data, "outdoor", "x")) != initial


def test_qr_request_requires_explicit_confirmation_and_version():
    base = {
        "campus_id": str(uuid4()),
        "source": {
            "kind": "qr",
            "marker_id": str(uuid4()),
            "expected_marker_version": 2,
            "confirmed": True,
        },
        "destination": {"place_id": str(uuid4())},
    }
    assert RouteRequest.model_validate(base).source.kind == "qr"
    for field, value in [("confirmed", False), ("expected_marker_version", 0)]:
        with pytest.raises(ValidationError):
            RouteRequest.model_validate({**base, "source": {**base["source"], field: value}})
    with pytest.raises(ValidationError):
        RouteRequest.model_validate(
            {**base, "source": {k: v for k, v in base["source"].items() if k != "confirmed"}}
        )


def test_previous_place_source_default_kind_remains_compatible():
    value = RouteRequest.model_validate(
        {
            "campus_id": str(uuid4()),
            "source": {"place_id": str(uuid4())},
            "destination": {"place_id": str(uuid4())},
        }
    )
    assert value.source.kind == "place"
