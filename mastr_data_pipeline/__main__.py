"""CLI entry: poetry run python -m mastr_data_pipeline --snapshot-date YYYY-MM-DD"""

from __future__ import annotations

import argparse
import sys

from mastr_data_pipeline.ingest import ingest_snapshot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mastr_data_pipeline",
        description=(
            "Upload original MaStR CSV snapshots to GCS Bronze "
            "(create-only, SHA-256 verified)."
        ),
    )
    parser.add_argument(
        "--snapshot-date",
        required=True,
        help=(
            "Dated snapshot folder label under data/raw/ "
            "(e.g. 2026-11-09). Not necessarily the official MaStR export timestamp."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    results = ingest_snapshot(args.snapshot_date)
    for result in results:
        print(
            f"{result.status}\t{result.source_file}\t{result.gs_uri}\t{result.sha256}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
