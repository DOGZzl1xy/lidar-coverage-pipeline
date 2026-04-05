"""Spatial analysis logic."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

from lidar_coverage.constants import DEFAULT_COVERAGE_THRESHOLD


def build_vintage_note(years: list[int]) -> str:
    if not years:
        return "No intersecting 2015+ LiDAR batches"

    distinct_years = sorted(set(years))
    if len(distinct_years) == 1:
        return f"Intersecting LiDAR year: {distinct_years[0]}"

    return (
        f"Intersecting LiDAR years: {distinct_years[0]}-{distinct_years[-1]} "
        f"({', '.join(str(year) for year in distinct_years)})"
    )


def compute_coverage(
    towns: gpd.GeoDataFrame,
    lidar: gpd.GeoDataFrame,
    *,
    coverage_threshold: float = DEFAULT_COVERAGE_THRESHOLD,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    towns = towns.copy()
    lidar = lidar.copy()

    if towns.empty:
        raise ValueError("No county subdivisions available for analysis.")

    if lidar.empty:
        towns["covered_area_m2"] = 0.0
        towns["gap_area_m2"] = towns["base_area_m2"]
        towns["coverage_pct"] = 0.0
        towns["lidar_batch_count"] = 0
        towns["data_vintage_note"] = "No intersecting 2015+ LiDAR batches"
        result = towns.drop(columns="geometry")
        under_threshold = result.loc[result["coverage_pct"] < coverage_threshold].copy()
        return result.sort_values("GEOID"), under_threshold.sort_values("coverage_pct")

    lidar_subset = lidar[["id", "lidar_name", "year", "geometry"]].copy()
    town_subset = towns[["GEOID", "town_name", "state", "base_area_m2", "geometry"]].copy()

    town_footprint = town_subset.geometry.union_all()
    candidate_lidar = lidar_subset.loc[lidar_subset.intersects(town_footprint)].reset_index(
        drop=True
    )

    intersections = gpd.overlay(
        town_subset,
        candidate_lidar,
        how="intersection",
        keep_geom_type=False,
    )

    if intersections.empty:
        towns["covered_area_m2"] = 0.0
        towns["gap_area_m2"] = towns["base_area_m2"]
        towns["coverage_pct"] = 0.0
        towns["lidar_batch_count"] = 0
        towns["data_vintage_note"] = "No intersecting 2015+ LiDAR batches"
        result = towns.drop(columns="geometry")
        under_threshold = result.loc[result["coverage_pct"] < coverage_threshold].copy()
        return result.sort_values("GEOID"), under_threshold.sort_values("coverage_pct")

    coverage_union = intersections.dissolve(by="GEOID")
    coverage_area = coverage_union.geometry.area.rename("covered_area_m2")

    batch_counts = (
        intersections.groupby("GEOID")["lidar_name"].nunique().rename("lidar_batch_count")
    )
    vintage_notes = (
        intersections.groupby("GEOID")["year"]
        .apply(lambda values: build_vintage_note([int(value) for value in values.dropna()]))
        .rename("data_vintage_note")
    )

    result = (
        towns.set_index("GEOID")
        .join(coverage_area)
        .join(batch_counts)
        .join(vintage_notes)
        .reset_index()
    )
    result["covered_area_m2"] = result["covered_area_m2"].fillna(0.0)
    result["lidar_batch_count"] = result["lidar_batch_count"].fillna(0).astype(int)
    result["data_vintage_note"] = result["data_vintage_note"].fillna(
        "No intersecting 2015+ LiDAR batches"
    )
    result["gap_area_m2"] = (result["base_area_m2"] - result["covered_area_m2"]).clip(lower=0.0)
    result["coverage_pct"] = (result["covered_area_m2"] / result["base_area_m2"] * 100).round(2)

    ordered = result[
        [
            "GEOID",
            "town_name",
            "state",
            "base_area_m2",
            "covered_area_m2",
            "gap_area_m2",
            "coverage_pct",
            "lidar_batch_count",
            "data_vintage_note",
            "geometry",
        ]
    ].sort_values("GEOID")
    under_threshold = ordered.loc[ordered["coverage_pct"] < coverage_threshold].copy()
    return ordered.drop(columns="geometry"), under_threshold.drop(columns="geometry").sort_values(
        ["coverage_pct", "GEOID"]
    )
