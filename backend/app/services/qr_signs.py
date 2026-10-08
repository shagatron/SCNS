"""Readable, printable signs; local encoding without any QR tracking service."""

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
    header = ["Campus navigation", *textwrap.wrap(marker.label, width=32)]
    footer = [
        *textwrap.wrap(origin, width=45),
        "Scan with your phone camera.",
        "Confirm this location before starting.",
        "Not continuous indoor positioning.",
        *textwrap.wrap(
            "ACTIVE — verify location label"
            if marker.state == "active"
            else "NOT ACTIVE — installation verification required",
            width=45,
        ),
    ]
    if origin.startswith("http:"):
        footer.append("Local demo — not a deployed campus service")
    matrix = list(code.matrix_iter(border=4))
    if format == "svg":
        scale = 520 / len(matrix)
        cells = "".join(
            f'<rect x="{140 + x * scale:.3f}" y="{280 + y * scale:.3f}" width="{scale:.3f}" height="{scale:.3f}"/>'
            for y, row in enumerate(matrix)
            for x, cell in enumerate(row)
            if cell
        )
        text = "".join(
            f'<text x="400" y="{35 + i * 28}" text-anchor="middle">{escape(line)}</text>'
            for i, line in enumerate(header)
        )
        text += "".join(
            f'<text x="400" y="{830 + i * 23}" text-anchor="middle" font-size="17">{escape(line)}</text>'
            for i, line in enumerate(footer)
        )
        text += "".join(
            f'<text x="400" y="{1060 + i * 16}" text-anchor="middle" font-size="12">{escape(line)}</text>'
            for i, line in enumerate(textwrap.wrap(url, width=90))
        )
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="1140" viewBox="0 0 800 1140"><rect width="800" height="1140" fill="white"/><g fill="black" shape-rendering="crispEdges">{cells}</g><g font-family="sans-serif" font-size="22" fill="black">{text}</g></svg>'.encode()
    raw = io.BytesIO()
    code.save(raw, kind="png", scale=max(1, 600 // len(matrix)), border=4)
    with Image.open(io.BytesIO(raw.getvalue())) as qr:
        canvas = Image.new("RGB", (1000, 1500), "white")
        qr = qr.convert("RGB")
        canvas.paste(qr, ((1000 - qr.width) // 2, 300))
    draw = ImageDraw.Draw(canvas)
    for i, line in enumerate(header):
        draw.text(
            (500, 35 + i * 34),
            line,
            font=ImageFont.load_default(size=24),
            fill="black",
            anchor="mt",
        )
    for i, line in enumerate(footer):
        draw.text(
            (500, 950 + i * 30),
            line,
            font=ImageFont.load_default(size=20),
            fill="black",
            anchor="mt",
        )
    for i, line in enumerate(textwrap.wrap(url, width=90)):
        draw.text(
            (500, 1370 + i * 22),
            line,
            font=ImageFont.load_default(size=16),
            fill="black",
            anchor="mt",
        )
    output = io.BytesIO()
    canvas.save(output, format="PNG" if format == "png" else "PDF", resolution=150)
    return output.getvalue()
