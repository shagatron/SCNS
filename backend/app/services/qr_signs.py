"""Readable, printable signs; QR encoding is performed locally, no tracking service."""

import io
import textwrap
from html import escape

import segno
from PIL import Image, ImageDraw, ImageFont

from app.core.config import get_settings


def render(marker, format):
    origin = get_settings().public_app_url
    url = f"{origin}/q/{marker.id}"
    code = segno.make(url, error="m", micro=False)
    lines = [
        "Campus navigation",
        *textwrap.wrap(marker.label, width=32),
        origin,
        "Scan with your phone camera.",
        "Confirm this location before starting.",
        "Not continuous indoor positioning.",
        "ACTIVE — verify location label"
        if marker.state == "active"
        else "NOT ACTIVE — installation verification required",
    ]
    if origin.startswith("http:"):
        lines.append("Local demo link — not a deployed campus service")
    if format == "svg":
        cells = []
        matrix = list(code.matrix_iter(border=4))
        scale = 560 / len(matrix)
        for y, row in enumerate(matrix):
            for x, cell in enumerate(row):
                if cell:
                    cells.append(
                        f'<rect x="{120 + x * scale:.3f}" y="{250 + y * scale:.3f}" width="{scale:.3f}" height="{scale:.3f}"/>'
                    )
        text = "".join(
            f'<text x="400" y="{35 + i * 30 if i < len(lines) - 6 else 860 + (i - (len(lines) - 6)) * 30}" text-anchor="middle">{escape(line)}</text>'
            for i, line in enumerate(lines)
        )
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="1100" viewBox="0 0 800 1100"><rect width="800" height="1100" fill="white"/><g fill="black">{"".join(cells)}</g><g font-family="sans-serif" font-size="22" fill="black">{text}<text x="400" y="1065" text-anchor="middle" font-size="14">{escape(url)}</text></g></svg>'.encode()
    raw = io.BytesIO()
    code.save(raw, kind="png", scale=12, border=4)
    with Image.open(io.BytesIO(raw.getvalue())) as qr:
        canvas = Image.new("RGB", (1000, 1400), "white")
        qr = qr.convert("RGB")
        qr.thumbnail((700, 700), Image.Resampling.NEAREST)
        canvas.paste(qr, ((1000 - qr.width) // 2, 300))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=24)
    for i, line in enumerate(lines):
        y = 35 + i * 34 if i < len(lines) - 6 else 1050 + (i - (len(lines) - 6)) * 34
        draw.text((500, y), line, font=font, fill="black", anchor="mt")
    draw.text((500, 1350), url, font=ImageFont.load_default(size=16), fill="black", anchor="mt")
    output = io.BytesIO()
    canvas.save(output, format="PNG" if format == "png" else "PDF", resolution=150)
    return output.getvalue()
