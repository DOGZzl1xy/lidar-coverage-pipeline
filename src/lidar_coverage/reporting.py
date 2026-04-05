"""Output generation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_csv(frame: pd.DataFrame, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(destination, index=False)
    return destination


def format_output_table(frame: pd.DataFrame) -> pd.DataFrame:
    formatted = frame.copy()
    for column in ("base_area_m2", "covered_area_m2", "gap_area_m2", "coverage_pct"):
        if column in formatted.columns:
            formatted[column] = formatted[column].round(2)

    return formatted.rename(
        columns={
            "town_name": "Town Name",
            "state": "State",
            "GEOID": "GEOID",
            "base_area_m2": "Base Area (m2)",
            "covered_area_m2": "Covered Area (m2)",
            "gap_area_m2": "Gap Area (m2)",
            "coverage_pct": "Current Coverage %",
            "lidar_batch_count": "LiDAR Batch Count",
            "data_vintage_note": "Data Vintage Note",
        }
    )


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

    if below == 0:
        lines.extend(["No county subdivisions fell below the coverage threshold.", ""])
        return "\n".join(lines)

    lines.extend(
        [
            "## Coverage Gaps",
            "",
            "| Town Name | State | GEOID | Coverage % | Gap Area (km^2) | LiDAR Batch Count | Data Vintage Note |",
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


def write_markdown(content: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    return destination
