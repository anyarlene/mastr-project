"""CLI entry for Bronze ingest and BigQuery Raw load."""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mastr_data_pipeline",
        description="MaStR Bronze ingestion and BigQuery Raw loading.",
    )
    subparsers = parser.add_subparsers(dest="command")

    bronze = subparsers.add_parser(
        "ingest-bronze",
        help=(
            "Validate Data Contract then upload original CSVs to GCS Bronze "
            "(create-only, SHA-256 verified)."
        ),
    )
    bronze.add_argument(
        "--snapshot-date",
        required=True,
        help="Dated snapshot folder label (e.g. 2026-11-09).",
    )

    validate = subparsers.add_parser(
        "validate-snapshot",
        help="Run MaStR Data Contract checks on local CSVs (no upload).",
    )
    validate.add_argument(
        "--snapshot-date",
        required=True,
        help="Dated snapshot folder label (e.g. 2026-11-16).",
    )

    raw = subparsers.add_parser(
        "load-raw",
        help=(
            "Load GCS Bronze CSVs into BigQuery Raw "
            "(validate staging, then atomically replace snapshot)."
        ),
    )
    raw.add_argument(
        "--snapshot-date",
        required=True,
        help="Dated snapshot folder label (e.g. 2026-11-09).",
    )
    raw.add_argument(
        "--keep-staging",
        action="store_true",
        help="Keep the staging table after a successful replace (debug).",
    )

    return parser


def _normalize_argv(argv: list[str]) -> list[str]:
    """Allow legacy ` --snapshot-date DATE` as ingest-bronze."""
    if not argv:
        return argv
    if argv[0] in {"ingest-bronze", "load-raw", "validate-snapshot", "-h", "--help"}:
        return argv
    if argv[0].startswith("-"):
        return ["ingest-bronze", *argv]
    return argv


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(_normalize_argv(raw_argv))

    if args.command is None:
        build_parser().error(
            "command required: ingest-bronze | validate-snapshot | load-raw"
        )

    if args.command == "validate-snapshot":
        from mastr_data_pipeline.config import get_settings
        from mastr_data_pipeline.data_contract import validate_snapshot_contract

        cfg = get_settings()
        result = validate_snapshot_contract(args.snapshot_date, cfg.raw_dir)
        print(
            f"{result.status}\t{result.snapshot_date}\t"
            f"export_scope={result.export_scope}\t"
            f"cdc_baseline={result.cdc_baseline}\t"
            f"row_counts={result.row_counts}"
        )
        return 0

    if args.command == "ingest-bronze":
        from mastr_data_pipeline.ingest import ingest_snapshot

        results = ingest_snapshot(args.snapshot_date)
        for result in results:
            print(
                f"{result.status}\t{result.source_file}\t"
                f"{result.gs_uri}\t{result.sha256}"
            )
        return 0

    if args.command == "load-raw":
        from mastr_data_pipeline.load_raw import load_raw_snapshot

        result = load_raw_snapshot(
            args.snapshot_date,
            keep_staging=args.keep_staging,
        )
        print(
            f"{result.status}\t{result.snapshot_date}\t"
            f"{result.destination_table}\t{result.row_counts}\t{result.ingested_at}"
        )
        return 0

    build_parser().error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
