"""Derive only the owner-supplied photograph, without upsampling or logo editing."""

import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "frontend/public/branding/muj"
ORIGINALS = {
    "muj.jpg": "c3cc161a863c142999bddba63a6b8d67f4d2d722246ebe9b3645764a4e72e8b1",
    "muj_logo.png": "8697ba8912441f855e233fd6e20ba327c1eedf208db8dd1207c7ddff10059a0c",
}
manifest = {
    "provenance": "Owner-supplied in muj images.zip. Authorship, licensing and institutional authorization were not supplied. Branding does not approve map data or imply university endorsement.",
    "originals": {},
    "derivatives": {},
}
for name, expected in ORIGINALS.items():
    path = DEST / "originals" / name
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, (
        "Original differs; stop rather than substitute."
    )
    with Image.open(path) as im:
        im.load()
        manifest["originals"][name] = {
            "sha256": expected,
            "dimensions": list(im.size),
            "mode": im.mode,
            "bytes": path.stat().st_size,
        }
        if "A" in im.getbands():
            manifest["originals"][name]["alpha_extrema"] = list(im.getchannel("A").getextrema())
with Image.open(DEST / "originals/muj.jpg") as photo:
    variants = {
        "campus-736.webp": (photo, None),
        "campus-480.webp": (photo, (480, 270)),
        # Symmetric original-coordinate crop retains the complete dome/finial,
        # central columns and ground. No generated pixels or image upsampling.
        "campus-mobile.webp": (photo.crop((220, 0, 516, 414)), None),
    }
    for name, (image, size) in variants.items():
        if size:
            image = image.resize(size, Image.Resampling.LANCZOS)
        path = DEST / name
        image.save(path, "WEBP", quality=82, method=6)
        with Image.open(path) as check:
            check.load()
            manifest["derivatives"][name] = {
                "dimensions": list(check.size),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "source_crop": [220, 0, 516, 414] if "mobile" in name else [0, 0, 736, 414],
            }
(DEST / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest, indent=2))
