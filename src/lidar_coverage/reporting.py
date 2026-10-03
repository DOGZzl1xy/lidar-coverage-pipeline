"""Output generation."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

from lidar_coverage.constants import STATE_PROGRAM_NOTES

MANIFEST_NAME = "run_manifest.json"
UNRESOLVED_NAME = "unresolved_collections.csv"
UNRESOLVED_COLUMNS = ["id", "lidar_name", "collection_key", "url"]

CSV_COLUMNS = [
    "GEOID",
    "town_name",
    "state",
    "base_area_m2",
    "covered_area_m2",
    "gap_area_m2",
    "coverage_pct",
    "lidar_batch_count",
    "data_vintage_note",
]

BATCH_COLUMNS = [
    "state",
    "county_subdivisions_analyzed",
    "county_subdivisions_below_threshold",
    "mean_coverage_pct",
    "min_coverage_pct",
    "max_coverage_pct",
]


def state_output_paths(output_dir: Path, state_abbr: str) -> dict[str, Path]:
    prefix = state_abbr.lower()
    return {
        "all_csv": output_dir / f"{prefix}_cousub_coverage_all.csv",
        "gap_csv": output_dir / f"{prefix}_cousub_coverage_under_threshold.csv",
        "all_geojson": output_dir / f"{prefix}_cousub_coverage_all.geojson",
        "gap_geojson": output_dir / f"{prefix}_cousub_coverage_under_threshold.geojson",
        "markdown": output_dir / f"{prefix}_coverage_summary.md",
    }


def write_json(payload: dict, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return destination


def write_csv(frame: pd.DataFrame, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(destination, index=False)
    return destination


def format_output_table(frame: pd.DataFrame) -> pd.DataFrame:
    formatted = frame[CSV_COLUMNS].copy()
    for column in ("base_area_m2", "covered_area_m2", "gap_area_m2", "coverage_pct"):
        formatted[column] = formatted[column].round(2)
    return formatted


def write_geojson(frame: gpd.GeoDataFrame, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(frame.to_json(drop_id=True, to_wgs84=True), encoding="utf-8")
    return destination


def summarize_state(
    state_abbr: str,
    all_results: pd.DataFrame,
    gap_results: pd.DataFrame,
) -> dict[str, str | int | float]:
    total = len(all_results)
    coverage = all_results["coverage_pct"] if total else pd.Series([0.0])
    return {
        "state": state_abbr,
        "county_subdivisions_analyzed": total,
        "county_subdivisions_below_threshold": len(gap_results),
        "mean_coverage_pct": round(float(coverage.mean()), 2),
        "min_coverage_pct": round(float(coverage.min()), 2),
        "max_coverage_pct": round(float(coverage.max()), 2),
    }


def build_markdown_summary(
    state_abbr: str,
    all_results: pd.DataFrame,
    gap_results: pd.DataFrame,
    *,
    threshold: float,
) -> str:
    total = len(all_results)
    below = len(gap_results)
    avg_coverage = all_results["coverage_pct"].mean() if total else 0.0

    lines = [
        f"# {state_abbr} County Subdivision LiDAR Coverage",
        "",
        f"- Coverage threshold: `< {threshold:.1f}%`",
        f"- County subdivisions analyzed: `{total}`",
        f"- County subdivisions below threshold: `{below}`",
        f"- Mean coverage: `{avg_coverage:.2f}%`",
        "",
    ]

    if state_abbr in STATE_PROGRAM_NOTES:
        lines.extend([f"> **Data source note:** {STATE_PROGRAM_NOTES[state_abbr]}", ""])

    if below == 0:
        lines.extend(["No county subdivisions fell below the coverage threshold.", ""])
        return "\n".join(lines)

    lines.extend(
        [
            "## Coverage Gaps",
            "",
            "| Town Name | State | GEOID | Coverage % | Gap Area (km^2) | "
            "LiDAR Batch Count | Data Vintage Note |",
            "| --- | --- | --- | ---: | ---: | ---: | --- |",
        ]
    )

    for row in gap_results.itertuples(index=False):
        lines.append(
            "| "
            f"{row.town_name} | "
            f"{row.state} | "
            f"{row.GEOID} | "
            f"{row.coverage_pct:.2f} | "
            f"{row.gap_area_m2 / 1_000_000:.3f} | "
            f"{row.lidar_batch_count} | "
            f"{row.data_vintage_note} |"
        )

    lines.append("")
    return "\n".join(lines)


def build_batch_markdown_summary(
    batch_summary: pd.DataFrame,
    *,
    threshold: float,
    min_year: int,
) -> str:
    total = int(batch_summary["county_subdivisions_analyzed"].sum())
    below = int(batch_summary["county_subdivisions_below_threshold"].sum())
    lines = [
        "# Multi-State County Subdivision LiDAR Coverage",
        "",
        f"- Modern LiDAR minimum vintage: `{min_year}`",
        f"- Coverage gap threshold: `< {threshold:.1f}%`",
        f"- States analyzed: `{len(batch_summary)}`",
        f"- County subdivisions analyzed: `{total}`",
        f"- County subdivisions below threshold: `{below}`",
        "",
        "| State | County Subdivisions | Below Threshold | Mean Coverage % | "
        "Min Coverage % | Max Coverage % |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in batch_summary[BATCH_COLUMNS].itertuples(index=False):
        lines.append(
            f"| {row.state} | "
            f"{row.county_subdivisions_analyzed} | "
            f"{row.county_subdivisions_below_threshold} | "
            f"{row.mean_coverage_pct:.2f} | "
            f"{row.min_coverage_pct:.2f} | "
            f"{row.max_coverage_pct:.2f} |"
        )

    lines.append("")
    noted = [state for state in batch_summary["state"] if state in STATE_PROGRAM_NOTES]
    if noted:
        lines.extend(["## Data Source Notes", ""])
        lines.extend(f"- **{state}:** {STATE_PROGRAM_NOTES[state]}" for state in noted)
        lines.append("")
    return "\n".join(lines)


def write_markdown(content: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    return destination
