"""Boundary/security checks use only invented images and synthetic PDFs."""

import io
import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter

from app.core.errors import DomainError
from app.routing.coordinates import IndoorPoint, calibrated_length, indoor_to_leaflet
from app.schemas.floorplans import CalibrationInput, UploadInput
from app.services.floorplans import calibration, decode

FIXTURES = Path(__file__).resolve().parents[3] / "data/demo/floorplans"


def options(name="synthetic-ground.png", page=1):
    return {
        "filename": name,
        "page": page,
        "redactions": [{"x": 480, "y": 320, "width": 100, "height": 60}],
    }


def measure():
    return {
        "primary": {"start": {"x": 100, "y": 100}, "end": {"x": 300, "y": 100}, "distance_m": 10},
        "checks": [{"start": {"x": 100, "y": 100}, "end": {"x": 100, "y": 300}, "distance_m": 10}],
        "measured_on": "2026-10-01",
        "evidence": "Invented known 200px lines each represent 10m; synthetic only.",
        "uncertainty_m": 0.05,
        "plan_quality": "uniform",
    }


@pytest.mark.parametrize(
    "name,page",
    [
        ("synthetic-ground.png", 1),
        ("synthetic-basement.jpg", 1),
        ("synthetic-two-pages.pdf", 1),
        ("synthetic-two-pages.pdf", 2),
    ],
)
def test_isolated_supported_decode_masks_pixels_and_strips_metadata(name, page):
    raw = (FIXTURES / name).read_bytes()
    png, meta = decode(raw, options(name, page))
    assert (meta["width_px"], meta["height_px"]) == (600, 400)
    assert meta["page_count"] == (2 if name.endswith(".pdf") else 1)
    image = Image.open(io.BytesIO(png))
    assert image.size == (600, 400) and image.mode == "RGB" and not image.info
    assert image.getpixel((520, 350)) == (255, 255, 255)
    assert image.getpixel((200, 100)) != (255, 255, 255)
    assert raw != png and b"PRIVATE-ORIGINAL-METADATA" not in png


def test_isolation_denies_files_network_and_inherited_credentials():
    result = subprocess.run(
        [sys.executable, "-m", "app.cli.render_floorplan", "--probe"],
        env={"PATH": os.defpath},
        capture_output=True,
        check=True,
    )
    assert json.loads(result.stdout) == {
        "filesystem_denied": True,
        "network_denied": True,
        "database_env_absent": True,
    }


@pytest.mark.parametrize(
    "content,name,page",
    [
        (b"%PDF-not a pdf", "bad.pdf", 1),
        (b"\x89PNG\r\n\x1a\ntruncated", "bad.png", 1),
        (b"<svg/>", "bad.png", 1),
        ((FIXTURES / "synthetic-ground.png").read_bytes(), "bad.jpg", 1),
        ((FIXTURES / "synthetic-two-pages.pdf").read_bytes(), "plan.pdf", 3),
        ((FIXTURES / "synthetic-ground.png").read_bytes(), "plan.png", 2),
    ],
)
def test_decode_rejects_malformed_mismatched_and_missing_pages(content, name, page):
    with pytest.raises(ValueError):
        decode(content, options(name, page))


def test_pdf_encryption_page_and_dimension_budgets():
    original = PdfReader(FIXTURES / "synthetic-two-pages.pdf")
    writer = PdfWriter()
    writer.append_pages_from_reader(original)
    writer.encrypt("secret-fixture-only")
    output = io.BytesIO()
    writer.write(output)
    with pytest.raises(ValueError):
        decode(output.getvalue(), options("encrypted.pdf"))
    many = PdfWriter()
    for _ in range(31):
        many.add_blank_page(width=100, height=100)
    output = io.BytesIO()
    many.write(output)
    with pytest.raises(ValueError):
        decode(output.getvalue(), options("many.pdf"))
    enormous = PdfWriter()
    enormous.add_blank_page(width=10000, height=10000)
    output = io.BytesIO()
    enormous.write(output)
    with pytest.raises(ValueError):
        decode(output.getvalue(), options("large.pdf"))


def test_image_pixel_dimensions_and_redaction_bounds():
    large = io.BytesIO()
    Image.new("RGB", (10001, 10)).save(large, format="PNG")
    with pytest.raises(ValueError):
        decode(large.getvalue(), {"filename": "large.png", "page": 1, "redactions": []})
    with pytest.raises(ValueError):
        decode(
            (FIXTURES / "synthetic-ground.png").read_bytes(),
            {
                "filename": "plan.png",
                "page": 1,
                "redactions": [{"x": 580, "y": 390, "width": 100, "height": 20}],
            },
        )


def test_resized_display_preserves_reference_and_exif_orientation():
    output = io.BytesIO()
    Image.new("RGB", (3000, 1000)).save(output, format="PNG")
    png, meta = decode(output.getvalue(), {"filename": "wide.png", "page": 1, "redactions": []})
    assert meta["width_px"] == 3000 and Image.open(io.BytesIO(png)).width == 2048
    output = io.BytesIO()
    image = Image.new("RGB", (600, 400))
    exif = Image.Exif()
    exif[274] = 6
    image.save(output, format="JPEG", exif=exif)
    png, meta = decode(output.getvalue(), {"filename": "rotated.jpg", "page": 1, "redactions": []})
    assert (meta["width_px"], meta["height_px"]) == (400, 600) and not Image.open(
        io.BytesIO(png)
    ).info


def test_uniform_scale_known_coordinates_and_rotated_lines():
    data = measure()
    value = calibration(CalibrationInput.model_validate(data), 600, 400, uuid4(), True)
    assert value["metres_per_pixel"] == 0.05 and value["quality"] == "synthetic_calibrated"
    assert indoor_to_leaflet(IndoorPoint("floor", 100, 100), 400) == (300, 100)
    assert (
        calibrated_length(
            [IndoorPoint("floor", 100, 100), IndoorPoint("floor", 300, 100)],
            value["metres_per_pixel"],
        )
        == 10
    )
    data["primary"]["end"] = {"x": 220, "y": 260}
    data["checks"][0]["end"] = {"x": 260, "y": 0}
    data["checks"][0]["distance_m"] = (160**2 + 100**2) ** 0.5 * 0.05
    assert (
        calibration(CalibrationInput.model_validate(data), 600, 400, uuid4(), True)[
            "metres_per_pixel"
        ]
        == 0.05
    )


@pytest.mark.parametrize(
    "change",
    ["degenerate", "outside", "parallel", "inconsistent", "distorted", "future", "uncertain"],
)
def test_invalid_calibration_never_invents_metric_scale(change):
    value = deepcopy(measure())
    if change == "degenerate":
        value["primary"]["end"] = value["primary"]["start"]
    elif change == "outside":
        value["primary"]["end"]["x"] = 900
    elif change == "parallel":
        value["checks"][0]["end"] = {"x": 400, "y": 100}
    elif change == "inconsistent":
        value["checks"][0]["distance_m"] = 15
    elif change == "distorted":
        value["plan_quality"] = "distorted"
    elif change == "future":
        value["measured_on"] = "2099-01-01"
    else:
        value["uncertainty_m"] = 2
    with pytest.raises(DomainError):
        calibration(CalibrationInput.model_validate(value), 600, 400, uuid4(), True)


@pytest.mark.parametrize(
    "filename", ["../plan.pdf", "/plan.png", ".hidden.png", "active.svg", 'bad".png']
)
def test_upload_filename_and_formats_allowlist(filename):
    with pytest.raises(ValueError):
        UploadInput.model_validate(
            {
                "floor_id": str(uuid4()),
                "key": "safe-fixture-key",
                "filename": filename,
                "title": "Synthetic",
                "rights": "synthetic",
                "provenance": "Invented image only",
                "attribution": "Synthetic",
            }
        )
