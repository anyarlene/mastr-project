#!/usr/bin/env python3
"""Regenerate snapshot-related dbt seeds from config/snapshots.json.

Writes:
  - dbt/seeds/seed_snapshot_expectations.csv
  - dbt/seeds/seed_snapshot_metadata.csv

config/snapshots.json is the single source of truth. Run before `dbt seed`:

    poetry run python scripts/generate_snapshot_expectations_seed.py

Or via Make:

    make generate-snapshot-seed
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mastr_data_pipeline.snapshot_expectations_seed import (
    DEFAULT_METADATA_SEED_PATH,
    DEFAULT_SEED_PATH,
    DEFAULT_SNAPSHOTS_PATH,
    write_all_snapshot_seeds,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate snapshot expectation and metadata seeds from config/snapshots.json"
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
        help=f"Expectations CSV path (default: {DEFAULT_SEED_PATH})",
    )
    parser.add_argument(
        "--metadata-output",
        type=Path,
        default=DEFAULT_METADATA_SEED_PATH,
        help=f"Metadata CSV path (default: {DEFAULT_METADATA_SEED_PATH})",
    )
    args = parser.parse_args(argv)
    expectations, metadata = write_all_snapshot_seeds(
        snapshots_path=args.snapshots,
        expectations_seed_path=args.output,
        metadata_seed_path=args.metadata_output,
    )
    print(f"Wrote {expectations}")
    print(f"Wrote {metadata}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
