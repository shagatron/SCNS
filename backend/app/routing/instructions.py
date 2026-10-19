"""Public outdoor wording only; stored labels/IDs and route selection stay intact."""

import re


def outdoor_instruction(kind: str, target_label: str) -> str:
    verb = {"stairs": "Take the stairs", "ramp": "Follow the ramp"}.get(kind, "Follow the path")
    # Exact converter placeholders only. Named gates, OSM refs, indoor labels and
    # owner-authored junction names keep their meaningful destination text.
    if re.fullmatch(r"OSM junction [0-9]+", target_label):
        return "Continue along the walkway." if kind == "walkway" else f"{verb}."
    return f"{verb} to {target_label}."
