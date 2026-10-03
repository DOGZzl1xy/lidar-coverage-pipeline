"""Strict consistency checks for a pipeline output directory."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from lidar_coverage.reporting import BATCH_COLUMNS, CSV_COLUMNS, MANIFEST_NAME, UNRESOLVED_NAME

# CSVs round areas and percentages to 2 decimals; GeoJSON keeps full precision.
NUMERIC_TOLERANCE = 0.011
COMPARED_PROPERTIES = ("coverage_pct", "gap_area_m2", "covered_area_m2", "base_area_m2")


def load_manifest(output_dir: Path) -> dict | None:
    path = output_dir / MANIFEST_NAME
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _read_state_csv(path: Path, state: str, errors: list[str]) -> pd.DataFrame | None:
    if not path.exists():
        errors.append(f"Missing output file: {path}")
        return None

    frame = pd.read_csv(path, dtype={"GEOID": str})
    missing = set(CSV_COLUMNS) - set(frame.columns)
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
    if frame["GEOID"].duplicated().any():
        errors.append(f"{path}: contains duplicate GEOIDs")
    return frame


def _read_geojson_properties(path: Path, errors: list[str]) -> pd.DataFrame | None:
    if not path.exists():
        errors.append(f"Missing output file: {path}")
        return None
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        errors.append(f"{path}: invalid GeoJSON JSON ({error})")
        return None
    if content.get("type") != "FeatureCollection":
        errors.append(f"{path}: expected a GeoJSON FeatureCollection")
        return None

    features = content.get("features") or []
    if any(not feature.get("geometry") for feature in features):
        errors.append(f"{path}: contains features without geometry")
    properties = pd.DataFrame([feature.get("properties") or {} for feature in features])
    if features and "GEOID" not in properties.columns:
        errors.append(f"{path}: features lack a GEOID property")
        return None
    if not features:
        properties = pd.DataFrame(columns=CSV_COLUMNS)
    properties["GEOID"] = properties["GEOID"].astype(str)
    return properties


def _compare_csv_geojson(
    table: pd.DataFrame,
    properties: pd.DataFrame,
    csv_path: Path,
    geojson_path: Path,
    errors: list[str],
) -> None:
    if len(table) != len(properties) or set(table["GEOID"]) != set(properties["GEOID"]):
        errors.append(
            f"{geojson_path}: {len(properties)} features do not match the "
            f"{len(table)} GEOIDs in {csv_path}"
        )
        return
    if table.empty:
        return

    joined = table.set_index("GEOID").join(
        properties.set_index("GEOID"), rsuffix="_geojson", how="inner"
    )
    for column in COMPARED_PROPERTIES:
        delta = (joined[column] - pd.to_numeric(joined[f"{column}_geojson"])).abs()
        if delta.isna().any() or (delta > NUMERIC_TOLERANCE).any():
            errors.append(f"{geojson_path}: {column} differs from {csv_path}")
    counts = pd.to_numeric(joined["lidar_batch_count_geojson"])
    if not joined["lidar_batch_count"].eq(counts).all():
        errors.append(f"{geojson_path}: lidar_batch_count differs from {csv_path}")


def _check_batch_row(
    batch: pd.DataFrame,
    state: str,
    full: pd.DataFrame,
    gaps: pd.DataFrame,
    batch_csv: Path,
    errors: list[str],
) -> None:
    rows = batch.loc[batch["state"] == state]
    if len(rows) != 1:
        errors.append(f"{batch_csv}: expected exactly one row for {state}")
        return
    row = rows.iloc[0]
    if row["county_subdivisions_analyzed"] != len(full):
        errors.append(f"{batch_csv}: total count for {state} does not match CSV")
    if row["county_subdivisions_below_threshold"] != len(gaps):
        errors.append(f"{batch_csv}: gap count for {state} does not match CSV")
    coverage = full["coverage_pct"]
    expected = {
        "mean_coverage_pct": coverage.mean(),
        "min_coverage_pct": coverage.min(),
        "max_coverage_pct": coverage.max(),
    }
    for column, value in expected.items():
        if abs(float(row[column]) - round(float(value), 2)) > NUMERIC_TOLERANCE:
            errors.append(f"{batch_csv}: {column} for {state} does not match CSV")


def validate_outputs(
    output_dir: Path,
    *,
    states: list[str] | None = None,
    coverage_threshold: float | None = None,
) -> list[str]:
    """Return a list of human-readable problems; an empty list means valid.

    Requested states and threshold default to the values persisted in
    ``run_manifest.json``. Supplying a threshold that differs from the one
    recorded for the run is itself an error.
    """
    errors: list[str] = []
    manifest = load_manifest(output_dir)
    parameters = (manifest or {}).get("parameters", {})
    if manifest is None:
        errors.append(f"Missing output file: {output_dir / MANIFEST_NAME}")
    elif manifest.get("status", "complete") != "complete":
        errors.append(f"{MANIFEST_NAME}: run status is {manifest.get('status')!r}, not 'complete'")

    run_threshold = parameters.get("coverage_threshold")
    if coverage_threshold is None:
        coverage_threshold = run_threshold
    elif run_threshold is not None and float(run_threshold) != float(coverage_threshold):
        errors.append(
            f"Requested threshold {coverage_threshold} differs from the run threshold "
            f"{run_threshold} recorded in {MANIFEST_NAME}"
        )
    if coverage_threshold is None:
        errors.append("No coverage threshold supplied and none recorded in the manifest")
        return errors

    run_states = parameters.get("states")
    states = [state.upper() for state in (states or run_states or [])]
    if not states:
        errors.append("No states supplied and none recorded in the manifest")
        return errors
    if run_states is not None and not set(states).issubset(run_states):
        errors.append(f"Requested states {states} were not all part of the run {run_states}")

    if not (output_dir / UNRESOLVED_NAME).exists():
        errors.append(f"Missing output file: {output_dir / UNRESOLVED_NAME}")
    if not (output_dir / "batch_summary.md").exists():
        errors.append(f"Missing output file: {output_dir / 'batch_summary.md'}")

    batch_csv = output_dir / "batch_summary.csv"
    batch: pd.DataFrame | None = None
    if not batch_csv.exists():
        errors.append(f"Missing output file: {batch_csv}")
    else:
        batch = pd.read_csv(batch_csv)
        if set(BATCH_COLUMNS) - set(batch.columns):
            errors.append(f"{batch_csv}: missing required batch summary columns")
            batch = None
        elif run_states is not None and set(batch["state"]) != set(run_states):
            errors.append(f"{batch_csv}: state rows do not match run states {run_states}")

    for state in states:
        prefix = output_dir / state.lower()
        all_csv = Path(f"{prefix}_cousub_coverage_all.csv")
        gap_csv = Path(f"{prefix}_cousub_coverage_under_threshold.csv")
        summary = Path(f"{prefix}_coverage_summary.md")
        if not summary.exists():
            errors.append(f"Missing output file: {summary}")

        full = _read_state_csv(all_csv, state, errors)
        gaps = _read_state_csv(gap_csv, state, errors)
        if full is None or gaps is None:
            continue

        expected_gaps = set(full.loc[full["coverage_pct"] < coverage_threshold, "GEOID"])
        actual_gaps = set(gaps["GEOID"])
        if actual_gaps != expected_gaps:
            errors.append(
                f"{gap_csv}: {len(expected_gaps - actual_gaps)} below-threshold rows missing, "
                f"{len(actual_gaps - expected_gaps)} unexpected rows "
                f"(threshold {coverage_threshold})"
            )

        for table, csv_path in ((full, all_csv), (gaps, gap_csv)):
            geojson_path = csv_path.with_suffix(".geojson")
            properties = _read_geojson_properties(geojson_path, errors)
            if properties is not None:
                _compare_csv_geojson(table, properties, csv_path, geojson_path, errors)

        if batch is not None:
            _check_batch_row(batch, state, full, gaps, batch_csv, errors)

    return errors
