"""Offline, bounded MUJ OSM preparation; no database or network access."""

import argparse
from pathlib import Path

from app.services.osm_conversion import convert, write_conversion


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    # Avoid reading arbitrary large sources into memory.
    with args.source.open("rb") as stream:
        raw = stream.read(5 * 1024 * 1024 + 1)
    result = convert(raw)
    write_conversion(result, args.output)
    print(result["report"]["included_counts"])
    print(
        f"Prepared {len(result['bundles'])} batches. Unpublished; independent source/release review required."
    )


if __name__ == "__main__":
    main()
