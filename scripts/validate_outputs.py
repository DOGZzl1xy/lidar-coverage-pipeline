"""Validate artifacts written by a state or multi-state pipeline run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {
    "GEOID",
    "town_name",
    "state",
    "base_area_m2",
    "covered_area_m2",
    "gap_area_m2",
    "coverage_pct",
    "lidar_batch_count",
    "data_vintage_note",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--states", nargs="+", required=True)
    parser.add_argument(
        "--coverage-threshold", type=float, default=5.0,
        help="Gap threshold used during the run (default 5.0).",
    )
    return parser


def validate_csv(path: Path, state: str, errors: list[str]) -> pd.DataFrame | None:
    if not path.exists():
        errors.append(f"Missing output file: {path}")
        return None

    frame = pd.read_csv(path, dtype={"GEOID": str})
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        errors.append(f"{path}: missing columns {sorted(missing)}")
        return None

    if not frame["state"].eq(state).all():
        errors.append(f"{path}: includes records outside state {state}")
    coverage = pd.to_numeric(frame["coverage_pct"], errors="coerce")
    gap_area = pd.to_numeric(frame["gap_area_m2"], errors="coerce")
    if coverage.isna().any() or not coverage.between(0.0, 100.0).all():
        errors.append(f"{path}: coverage_pct must be numeric and within 0-100")
    if gap_area.isna().any() or not gap_area.ge(0.0).all():
        errors.append(f"{path}: gap_area_m2 must be numeric and non-negative")
    return frame


def validate_geojson(path: Path, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"Missing output file: {path}")
        return
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        errors.append(f"{path}: invalid GeoJSON JSON ({error})")
        return
    if content.get("type") != "FeatureCollection":
        errors.append(f"{path}: expected a GeoJSON FeatureCollection")


def validate_threshold_subset(
    full: pd.DataFrame,
    gaps: pd.DataFrame,
    threshold: float,
    gap_csv: Path,
    all_csv: Path,
    errors: list[str],
) -> None:
    gap_above = gaps.loc[gaps["coverage_pct"] >= threshold]
    if len(gap_above):
        errors.append(
            f"{gap_csv}: {len(gap_above)} rows have coverage_pct >= {threshold} "
            f"(should only contain rows below threshold)"
        )
    gap_geoids = set(gaps["GEOID"])
    full_geoids = set(full["GEOID"])
    if not gap_geoids.issubset(full_geoids):
        extra = gap_geoids - full_geoids
        errors.append(f"{gap_csv}: {len(extra)} GEOIDs not present in {all_csv}")
    if full["GEOID"].duplicated().any():
        errors.append(f"{all_csv}: contains duplicate GEOIDs")
    if gaps["GEOID"].duplicated().any():
        errors.append(f"{gap_csv}: contains duplicate GEOIDs")


def main() -> None:
    args = build_parser().parse_args()
    output_dir = args.output_dir
    states = [state.upper() for state in args.states]
    threshold = args.coverage_threshold
    errors: list[str] = []

    batch_csv = output_dir / "batch_summary.csv"
    batch_markdown = output_dir / "batch_summary.md"
    batch: pd.DataFrame | None = None
    if not batch_csv.exists():
        errors.append(f"Missing output file: {batch_csv}")
    else:
        batch = pd.read_csv(batch_csv)
        required_batch = {
            "state",
            "county_subdivisions_analyzed",
            "county_subdivisions_below_threshold",
        }
        if not required_batch.issubset(batch.columns):
            errors.append(f"{batch_csv}: missing required batch summary columns")
        elif set(batch["state"]) != set(states):
            errors.append(f"{batch_csv}: state rows do not match requested states {states}")
    if not batch_markdown.exists():
        errors.append(f"Missing output file: {batch_markdown}")

    for state in states:
        prefix = state.lower()
        all_csv = output_dir / f"{prefix}_cousub_coverage_all.csv"
        gap_csv = output_dir / f"{prefix}_cousub_coverage_under_threshold.csv"
        summary = output_dir / f"{prefix}_coverage_summary.md"
        full = validate_csv(all_csv, state, errors)
        gaps = validate_csv(gap_csv, state, errors)
        if full is not None and gaps is not None:
            if len(gaps) > len(full):
                errors.append(f"{gap_csv}: contains more records than {all_csv}")
            validate_threshold_subset(full, gaps, threshold, gap_csv, all_csv, errors)
        if full is not None and gaps is not None and batch is not None and "state" in batch:
            state_summary = batch.loc[batch["state"] == state]
            if len(state_summary) == 1:
                row = state_summary.iloc[0]
                if row.get("county_subdivisions_analyzed") != len(full):
                    errors.append(f"{batch_csv}: total count for {state} does not match CSV")
                if row.get("county_subdivisions_below_threshold") != len(gaps):
                    errors.append(f"{batch_csv}: gap count for {state} does not match CSV")
        if not summary.exists():
            errors.append(f"Missing output file: {summary}")
        validate_geojson(output_dir / f"{prefix}_cousub_coverage_all.geojson", errors)
        validate_geojson(
            output_dir / f"{prefix}_cousub_coverage_under_threshold.geojson",
            errors,
        )

    if errors:
        raise SystemExit("Output validation failed:\n- " + "\n- ".join(errors))

    print(f"Validated {len(states)} states and batch outputs in {output_dir}.")


if __name__ == "__main__":
    main()
