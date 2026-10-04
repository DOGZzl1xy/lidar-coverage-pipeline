"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from lidar_coverage.constants import (
    DEFAULT_COVERAGE_THRESHOLD,
    DEFAULT_MIN_YEAR,
    REVIEWED_VINTAGE_OVERRIDES,
)
from lidar_coverage.pipeline import RunOptions, normalize_states, run_pipeline, run_preflight


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Identify county subdivisions lacking modern LiDAR coverage."
    )
    state_group = parser.add_mutually_exclusive_group()
    state_group.add_argument("--state", help="Two-letter state abbreviation.")
    state_group.add_argument(
        "--states",
        nargs="+",
        help="State abbreviations to process as a batch; 'CONUS' expands to the 48 states + DC.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="YAML configuration file; command-line arguments take precedence.",
    )
    parser.add_argument("--cache-dir", type=Path, help="Directory for downloaded source data.")
    parser.add_argument("--output-dir", type=Path, help="Directory for generated outputs.")
    parser.add_argument("--min-year", type=int, help="Minimum LiDAR vintage year to retain.")
    parser.add_argument(
        "--coverage-threshold",
        type=float,
        help="Coverage percentage threshold for reporting gaps.",
    )
    parser.add_argument(
        "--vintage-overrides",
        type=Path,
        help="CSV of collection_key,start_year[,end_year] (default: bundled reviewed table).",
    )
    parser.add_argument(
        "--no-vintage-overrides",
        action="store_true",
        help="Use only years parsed from collection names and URLs.",
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        default=None,
        help="Re-download source files even when cached copies exist.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        default=None,
        help="Use the cached LiDAR inventory instead of downloading the latest one.",
    )
    parser.add_argument(
        "--supplement-3dep-index",
        action="store_true",
        default=None,
        help="Add official USGS 3DEP work-unit footprints to the hobuinc inventory.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=None,
        help="Reuse per-state outputs already present in the output directory.",
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Run metadata-only readiness checks and exit without spatial analysis.",
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


def _configured_states(config: dict[str, object]) -> list[str]:
    if "states" in config:
        configured = config["states"]
        if isinstance(configured, str):
            return [configured]
        if not isinstance(configured, list):
            raise ValueError("Configuration value 'states' must be a list or a group name.")
        return [str(state) for state in configured]
    if "state" in config:
        return [str(config["state"])]
    return ["RI"]


def _pick(cli_value, config: dict[str, object], key: str, default):
    return cli_value if cli_value is not None else config.get(key, default)


def resolve_options(args: argparse.Namespace) -> RunOptions:
    config = load_config(args.config)
    if args.state:
        states = [args.state]
    elif args.states:
        states = args.states
    else:
        states = _configured_states(config)

    min_year = int(_pick(args.min_year, config, "min_year", DEFAULT_MIN_YEAR))
    coverage_threshold = float(
        _pick(args.coverage_threshold, config, "coverage_threshold", DEFAULT_COVERAGE_THRESHOLD)
    )
    if min_year < 0:
        raise ValueError("Minimum LiDAR vintage year must be non-negative.")
    if not 0.0 <= coverage_threshold <= 100.0:
        raise ValueError("Coverage threshold must be within 0-100.")

    overrides = _pick(
        args.vintage_overrides, config, "vintage_overrides", REVIEWED_VINTAGE_OVERRIDES
    )
    if args.no_vintage_overrides or overrides is False:
        overrides = None
    if overrides is not None and not Path(overrides).exists():
        raise ValueError(f"Vintage override file not found: {overrides}")

    return RunOptions(
        states=normalize_states(states),
        cache_dir=Path(str(_pick(args.cache_dir, config, "cache_dir", "data/cache"))),
        output_dir=Path(str(_pick(args.output_dir, config, "output_dir", "outputs"))),
        min_year=min_year,
        coverage_threshold=coverage_threshold,
        vintage_overrides=Path(overrides) if overrides is not None else None,
        refresh_cache=bool(_pick(args.refresh_cache, config, "refresh_cache", False)),
        refresh_inventory=not bool(_pick(args.offline, config, "offline", False)),
        supplement_3dep_index=bool(
            _pick(args.supplement_3dep_index, config, "supplement_3dep_index", False)
        ),
        skip_existing=bool(_pick(args.skip_existing, config, "skip_existing", False)),
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        options = resolve_options(args)
    except (OSError, TypeError, ValueError, yaml.YAMLError) as error:
        parser.error(str(error))

    if args.preflight:
        problems = run_preflight(options)
        if problems:
            print("Preflight failed:\n- " + "\n- ".join(problems), file=sys.stderr)
            raise SystemExit(1)
        print("Preflight passed.")
        return
    run_pipeline(options)


if __name__ == "__main__":
    main()
