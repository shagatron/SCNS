"""Reproduce original SCNS rectangular educational illustrations, no source plans.

Coordinates are arbitrary illustration pixels. No architecture, measurements,
title blocks or room identities are copied from the supplied reference PDF.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "frontend/public/demos/indoor-school/v1"


def room(x, y, label, bottom=False, isolated=False, stairs=False):
    width, height = 220, 180 if not bottom else 190
    if isolated:
        height = 140
        path = f"M{x},{y}h{width}v{height}h-{width}Z"
    elif bottom:
        path = f"M{x},{y}h85m50,0h85v{height}h-220v-{height}"
    else:
        path = f"M{x + 85},{y + height}h-85v-{height}h220v{height}h-85"
    fill = "#fee9e7" if isolated else "#fff1d6" if stairs else "#ffffff"
    lines = "".join(
        f'<tspan x="{x + 110}" dy="{0 if i == 0 else 28}">{text}</tspan>'
        for i, text in enumerate(label)
    )
    door = (
        ""
        if isolated
        else f'<path d="M{x + 85},{y if bottom else y + height}h50" stroke="#208469" stroke-width="5" stroke-dasharray="5 5"/>'
    )
    glyph = (
        ""
        if not stairs
        else "".join(
            f'<path d="M{x + 70},{y + 95 + i * 12}h80" stroke="#9a5219" stroke-width="4"/>'
            for i in range(6)
        )
    )
    return f'<path d="{path}" fill="{fill}" stroke="#273746" stroke-width="5"/>{door}<text x="{x + 110}" y="{y + 58}" text-anchor="middle" fill="#172c3b" font-size="23" font-weight="600">{lines}</text>{glyph}'


for floor in ("ground", "first"):
    upper = floor == "first"
    rooms = room(80, 90, ["Demo Classroom C" if upper else "Demo Classroom A"])
    rooms += room(390, 90, ["Demo Reading" if upper else "Demo Library", "Room" if upper else ""])
    rooms += room(80, 350, ["Demo Studio" if upper else "Demo Classroom B"], bottom=True)
    rooms += room(700, 350, ["Demo Stairs"], bottom=True, stairs=True)
    if not upper:
        rooms += room(390, 400, ["Demo Disconnected", "Room · no connection"], isolated=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / f"{floor}.svg").write_text(
        f"""<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="620" viewBox="0 0 1000 620" role="img" aria-labelledby="title description">
<title id="title">Original SCNS demonstration — {"First" if upper else "Ground"} floor</title>
<desc id="description">Unscaled fictional rectangular learning building. A horizontal corridor connects generic rooms to Demo Stairs on the right. {"The stairs connect to Ground floor." if upper else "A separate closed room has no graph connection. Stairs connect to First floor."} Not an actual MUJ floorplan.</desc>
<rect width="1000" height="620" fill="#f6f2e8"/>
<g font-family="Arial,sans-serif"><text x="60" y="42" fill="#172c3b" font-size="25" font-weight="700">{"First" if upper else "Ground"} floor · Demo Learning Building</text>
<text x="940" y="42" text-anchor="end" fill="#4b5c67" font-size="16">UNSCALED ILLUSTRATION</text>
<rect x="60" y="70" width="880" height="490" rx="12" fill="#e8e5da" stroke="#687b85" stroke-width="3"/>
<rect x="80" y="270" width="840" height="80" fill="#cce9df"/>
<text x="865" y="305" fill="#365c50" text-anchor="end" font-size="16">Demo corridor</text>
{rooms}
<text x="60" y="597" fill="#4b5c67" font-size="17">Dashed green = authored doorway · Stairs = floor connection · No scale or accessibility evidence</text></g></svg>""",
        encoding="utf-8",
    )
