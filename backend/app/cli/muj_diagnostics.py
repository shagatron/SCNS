"""Offline, read-only MUJ v1 connectivity review; requires the exact retained original."""

import argparse
from pathlib import Path

from app.services.muj_diagnostics import diagnose, write_diagnostics
from app.services.muj_setup import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--preparation", choices=["v1", "v2"], default="v1")
    args = parser.parse_args()
    preparation = ROOT if args.preparation == "v1" else ROOT.parent / "muj-v2"
    # Refuse replacing any pinned preparation, original or repository root with diagnostics.
    output = args.output.resolve()
    if (
        output == args.source.resolve()
        or output == ROOT.resolve()
        or output in ROOT.resolve().parents
        or ROOT.resolve() in output.parents
        or output == preparation.resolve()
        or preparation.resolve() in output.parents
    ):
        parser.error(
            "Use a separate diagnostic output directory, never the preparation/root/source"
        )
    with args.source.open("rb") as stream:
        raw = stream.read(5 * 1024 * 1024 + 1)
    report = diagnose(raw, preparation)
    write_diagnostics(report, output)
    print(
        f"Verified {len(report['components'])} components; diagnostics only, no database or preparation writes."
    )


if __name__ == "__main__":
    main()
