#!/usr/bin/env python3
"""Regenerate dbt/seeds/seed_snapshot_expectations.csv from config/snapshots.json.

config/snapshots.json is the single source of truth for expected row counts
and SHA-256 checksums. Run this script whenever that file changes, before
`dbt seed`:

    poetry run python scripts/generate_snapshot_expectations_seed.py

Or via Make:

    make generate-snapshot-seed
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mastr_data_pipeline.snapshot_expectations_seed import (
    DEFAULT_SEED_PATH,
    DEFAULT_SNAPSHOTS_PATH,
    write_snapshot_expectations_seed,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate seed_snapshot_expectations.csv from config/snapshots.json"
        )
    )
    parser.add_argument(
        "--snapshots",
        type=Path,
        default=DEFAULT_SNAPSHOTS_PATH,
        help=f"Path to snapshots.json (default: {DEFAULT_SNAPSHOTS_PATH})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_SEED_PATH,
        help=f"Output CSV path (default: {DEFAULT_SEED_PATH})",
    )
    args = parser.parse_args(argv)
    dest = write_snapshot_expectations_seed(
        snapshots_path=args.snapshots,
        seed_path=args.output,
    )
    print(f"Wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
