"""Command-line entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from lidar_coverage.analysis import compute_coverage
from lidar_coverage.constants import DEFAULT_COVERAGE_THRESHOLD
from lidar_coverage.io import (
    download_census_cousub,
    download_usgs_lidar_metadata,
    ensure_directory,
    read_vector,
)
from lidar_coverage.preprocess import prepare_cousub, prepare_lidar
from lidar_coverage.reporting import (
    build_markdown_summary,
    format_output_table,
    write_csv,
    write_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Identify county subdivisions lacking modern LiDAR coverage."
    )
    parser.add_argument("--state", default="RI", help="Two-letter state abbreviation.")
    parser.add_argument(
        "--cache-dir",
        default="data/cache",
        help="Directory used for downloaded source data.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Directory used for CSV and Markdown outputs.",
    )
    parser.add_argument(
        "--min-year",
        type=int,
        default=2015,
        help="Minimum LiDAR vintage year to retain.",
    )
    parser.add_argument(
        "--coverage-threshold",
        type=float,
        default=DEFAULT_COVERAGE_THRESHOLD,
        help="Coverage percentage threshold for reporting gaps.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    state_abbr = args.state.upper()
    cache_dir = ensure_directory(Path(args.cache_dir))
    output_dir = ensure_directory(Path(args.output_dir))

    census_path = download_census_cousub(state_abbr, cache_dir)
    lidar_path = download_usgs_lidar_metadata(cache_dir)

    towns = prepare_cousub(read_vector(census_path), state_abbr)
    lidar = prepare_lidar(read_vector(lidar_path), min_year=args.min_year)
    all_results, gap_results = compute_coverage(
        towns,
        lidar,
        coverage_threshold=args.coverage_threshold,
    )

    state_prefix = state_abbr.lower()
    full_csv = output_dir / f"{state_prefix}_cousub_coverage_all.csv"
    gap_csv = output_dir / f"{state_prefix}_cousub_coverage_under_threshold.csv"
    markdown_path = output_dir / f"{state_prefix}_coverage_summary.md"

    write_csv(format_output_table(all_results), full_csv)
    write_csv(format_output_table(gap_results), gap_csv)
    write_markdown(
        build_markdown_summary(
            state_abbr,
            all_results,
            gap_results,
            threshold=args.coverage_threshold,
        ),
        markdown_path,
    )


if __name__ == "__main__":
    main()
