"""Spatial analysis logic."""

from __future__ import annotations

import geopandas as gpd

from lidar_coverage.constants import DEFAULT_COVERAGE_THRESHOLD, DEFAULT_MIN_YEAR

RESULT_COLUMNS = [
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


def no_coverage_note(min_year: int = DEFAULT_MIN_YEAR) -> str:
    return f"No intersecting {min_year}+ LiDAR batches"


def build_vintage_note(years: list[int], *, min_year: int = DEFAULT_MIN_YEAR) -> str:
    if not years:
        return no_coverage_note(min_year)

    distinct_years = sorted(set(years))
    if len(distinct_years) == 1:
        return f"Intersecting LiDAR year: {distinct_years[0]}"

    return (
        f"Intersecting LiDAR years: {distinct_years[0]}-{distinct_years[-1]} "
        f"({', '.join(str(year) for year in distinct_years)})"
    )


def _finalize_results(
    result: gpd.GeoDataFrame,
    *,
    coverage_threshold: float,
    min_year: int,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    for column in ("covered_area_m2", "lidar_batch_count", "data_vintage_note"):
        if column not in result.columns:
            result[column] = None
    result["covered_area_m2"] = result["covered_area_m2"].astype(float).fillna(0.0).clip(lower=0.0)
    result["covered_area_m2"] = result[["covered_area_m2", "base_area_m2"]].min(axis=1)
    result["lidar_batch_count"] = result["lidar_batch_count"].fillna(0).astype(int)
    result["data_vintage_note"] = result["data_vintage_note"].fillna(no_coverage_note(min_year))
    result["gap_area_m2"] = (result["base_area_m2"] - result["covered_area_m2"]).clip(lower=0.0)
    result["coverage_pct"] = (
        (result["covered_area_m2"] / result["base_area_m2"] * 100)
        .fillna(0.0)
        .clip(lower=0.0, upper=100.0)
        .round(2)
    )

    ordered = gpd.GeoDataFrame(
        result[RESULT_COLUMNS].sort_values("GEOID").reset_index(drop=True),
        geometry="geometry",
        crs=result.crs,
    )
    under_threshold = ordered.loc[ordered["coverage_pct"] < coverage_threshold].copy()
    under_threshold = under_threshold.sort_values(["coverage_pct", "GEOID"]).reset_index(drop=True)
    return ordered, under_threshold


def compute_coverage(
    towns: gpd.GeoDataFrame,
    lidar: gpd.GeoDataFrame,
    *,
    coverage_threshold: float = DEFAULT_COVERAGE_THRESHOLD,
    min_year: int = DEFAULT_MIN_YEAR,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Measure unioned modern LiDAR coverage for each county subdivision.

    ``lidar_batch_count`` counts distinct ``collection_key`` values so that
    inventory aliases of one collection are counted once.
    """
    if towns.empty:
        raise ValueError("No county subdivisions available for analysis.")

    towns = towns.copy()
    finalize = {"coverage_threshold": coverage_threshold, "min_year": min_year}
    if lidar.empty:
        return _finalize_results(towns, **finalize)

    lidar_subset = lidar[["collection_key", "year", "geometry"]]
    town_subset = towns[["GEOID", "geometry"]]
    candidate_lidar = lidar_subset.loc[
        lidar_subset.intersects(town_subset.geometry.union_all())
    ].reset_index(drop=True)

    intersections = gpd.overlay(
        town_subset,
        candidate_lidar,
        how="intersection",
        keep_geom_type=False,
    )
    if intersections.empty:
        return _finalize_results(towns, **finalize)

    grouped = intersections.groupby("GEOID")
    coverage_area = intersections.dissolve(by="GEOID").geometry.area.rename("covered_area_m2")
    batch_counts = grouped["collection_key"].nunique().rename("lidar_batch_count")
    vintage_notes = (
        grouped["year"]
        .apply(
            lambda values: build_vintage_note(
                [int(value) for value in values.dropna()], min_year=min_year
            )
        )
        .rename("data_vintage_note")
    )

    result = (
        towns.set_index("GEOID")
        .join(coverage_area)
        .join(batch_counts)
        .join(vintage_notes)
        .reset_index()
    )
    result = gpd.GeoDataFrame(result, geometry="geometry", crs=towns.crs)
    return _finalize_results(result, **finalize)
