"""Offline, bounded MUJ OSM preparation; no database or network access."""

import argparse
from pathlib import Path

from app.services.osm_conversion import convert, write_conversion


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--covered-segments-v2",
        action="store_true",
        help="Separate v2 preparation; never replace imported v1 in-place",
    )
    args = parser.parse_args()
    # Avoid reading arbitrary large sources into memory.
    with args.source.open("rb") as stream:
        raw = stream.read(5 * 1024 * 1024 + 1)
    result = convert(raw, covered_segments_v2=args.covered_segments_v2)
    write_conversion(result, args.output)
    print(result["report"]["included_counts"])
    print(
        f"Prepared {len(result['bundles'])} batches. Unpublished; independent source/release review required."
    )


if __name__ == "__main__":
    main()
