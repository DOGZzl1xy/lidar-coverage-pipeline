"""Command-line entry point."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from lidar_coverage.analysis import compute_coverage
from lidar_coverage.constants import DEFAULT_COVERAGE_THRESHOLD, STATE_TO_FIPS
from lidar_coverage.io import (
    download_census_cousub,
    download_usgs_lidar_metadata,
    ensure_directory,
    read_vector,
)
from lidar_coverage.preprocess import prepare_cousub, prepare_lidar
from lidar_coverage.reporting import (
    BATCH_COLUMNS,
    build_batch_markdown_summary,
    build_markdown_summary,
    format_output_table,
    summarize_state,
    write_csv,
    write_geojson,
    write_markdown,
)


@dataclass(frozen=True)
class RunOptions:
    states: list[str]
    cache_dir: Path
    output_dir: Path
    min_year: int
    coverage_threshold: float


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Identify county subdivisions lacking modern LiDAR coverage."
    )
    state_group = parser.add_mutually_exclusive_group()
    state_group.add_argument("--state", help="Two-letter state abbreviation.")
    state_group.add_argument(
        "--states",
        nargs="+",
        help="Two-letter state abbreviations to process as a batch.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="YAML configuration file; command-line arguments take precedence.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        help="Directory used for downloaded source data.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory used for CSV and Markdown outputs.",
    )
    parser.add_argument(
        "--min-year",
        type=int,
        help="Minimum LiDAR vintage year to retain.",
    )
    parser.add_argument(
        "--coverage-threshold",
        type=float,
        help="Coverage percentage threshold for reporting gaps.",
    )
    return parser


def load_config(path: Path | None) -> dict[str, object]:
    if path is None:
        return {}
    with path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    if not isinstance(config, dict):
        raise ValueError("Configuration root must be a YAML mapping.")
    return config


def _normalize_states(states: list[str]) -> list[str]:
    if not states:
        raise ValueError("At least one state abbreviation is required.")
    normalized: list[str] = []
    for state in states:
        state_abbr = str(state).upper()
        if state_abbr not in STATE_TO_FIPS:
            raise ValueError(f"Unknown state abbreviation: {state_abbr}")
        if state_abbr not in normalized:
            normalized.append(state_abbr)
    return normalized


def resolve_options(args: argparse.Namespace) -> RunOptions:
    config = load_config(args.config)
    if args.state:
        states = [args.state]
    elif args.states:
        states = args.states
    elif "states" in config:
        configured_states = config["states"]
        if not isinstance(configured_states, list):
            raise ValueError("Configuration value 'states' must be a list.")
        states = [str(state) for state in configured_states]
    elif "state" in config:
        states = [str(config["state"])]
    else:
        states = ["RI"]

    min_year = args.min_year if args.min_year is not None else int(config.get("min_year", 2015))
    coverage_threshold = (
        args.coverage_threshold
        if args.coverage_threshold is not None
        else float(config.get("coverage_threshold", DEFAULT_COVERAGE_THRESHOLD))
    )
    if min_year < 0:
        raise ValueError("Minimum LiDAR vintage year must be non-negative.")
    if not 0.0 <= coverage_threshold <= 100.0:
        raise ValueError("Coverage threshold must be within 0-100.")

    return RunOptions(
        states=_normalize_states(states),
        cache_dir=args.cache_dir or Path(str(config.get("cache_dir", "data/cache"))),
        output_dir=args.output_dir or Path(str(config.get("output_dir", "outputs"))),
        min_year=min_year,
        coverage_threshold=coverage_threshold,
    )


def _write_state_outputs(
    state_abbr: str,
    all_results: pd.DataFrame,
    gap_results: pd.DataFrame,
    *,
    output_dir: Path,
    threshold: float,
) -> None:
    state_prefix = state_abbr.lower()
    full_csv = output_dir / f"{state_prefix}_cousub_coverage_all.csv"
    gap_csv = output_dir / f"{state_prefix}_cousub_coverage_under_threshold.csv"
    full_geojson = output_dir / f"{state_prefix}_cousub_coverage_all.geojson"
    gap_geojson = output_dir / f"{state_prefix}_cousub_coverage_under_threshold.geojson"
    markdown_path = output_dir / f"{state_prefix}_coverage_summary.md"

    write_csv(format_output_table(all_results), full_csv)
    write_csv(format_output_table(gap_results), gap_csv)
    write_geojson(all_results, full_geojson)
    write_geojson(gap_results, gap_geojson)
    write_markdown(
        build_markdown_summary(
            state_abbr,
            all_results,
            gap_results,
            threshold=threshold,
        ),
        markdown_path,
    )


def run_pipeline(options: RunOptions) -> pd.DataFrame:
    cache_dir = ensure_directory(options.cache_dir)
    output_dir = ensure_directory(options.output_dir)
    lidar_path = download_usgs_lidar_metadata(cache_dir)
    lidar = prepare_lidar(read_vector(lidar_path), min_year=options.min_year)

    summaries: list[dict[str, str | int | float]] = []
    for state_abbr in options.states:
        census_path = download_census_cousub(state_abbr, cache_dir)
        towns = prepare_cousub(read_vector(census_path), state_abbr)
        all_results, gap_results = compute_coverage(
            towns,
            lidar,
            coverage_threshold=options.coverage_threshold,
            min_year=options.min_year,
        )
        _write_state_outputs(
            state_abbr,
            all_results,
            gap_results,
            output_dir=output_dir,
            threshold=options.coverage_threshold,
        )
        summaries.append(summarize_state(state_abbr, all_results, gap_results))
        print(
            f"{state_abbr}: analyzed {len(all_results)} county subdivisions; "
            f"{len(gap_results)} below {options.coverage_threshold:.1f}%."
        )

    batch_summary = pd.DataFrame(summaries, columns=BATCH_COLUMNS)
    write_csv(batch_summary, output_dir / "batch_summary.csv")
    write_markdown(
        build_batch_markdown_summary(
            batch_summary,
            threshold=options.coverage_threshold,
            min_year=options.min_year,
        ),
        output_dir / "batch_summary.md",
    )
    return batch_summary


def main() -> None:
    parser = build_parser()
    try:
        options = resolve_options(parser.parse_args())
    except (OSError, TypeError, ValueError, yaml.YAMLError) as error:
        parser.error(str(error))
    run_pipeline(options)


if __name__ == "__main__":
    main()
