"""Preprocessing helpers for geometry and metadata."""

from __future__ import annotations

import re

import geopandas as gpd
import pandas as pd
from shapely import make_valid

from lidar_coverage.constants import STATE_TO_FIPS, TARGET_CRS

YEAR_PATTERN = re.compile(r"(?:19|20)\d{2}")


def _repair_geometry(geometry):
    if geometry is None or geometry.is_empty:
        return None

    repaired = make_valid(geometry)
    if repaired.is_empty:
        return None
    return repaired


def normalize_geometries(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    geometry_name = frame.geometry.name
    normalized = frame.copy()
    normalized[geometry_name] = normalized.geometry.map(_repair_geometry)
    normalized = normalized.dropna(subset=[geometry_name]).explode(index_parts=False)
    normalized = normalized.set_geometry(geometry_name)
    normalized = normalized[~normalized.geometry.is_empty].copy()
    return normalized


def prepare_cousub(frame: gpd.GeoDataFrame, state_abbr: str) -> gpd.GeoDataFrame:
    state_fips = STATE_TO_FIPS[state_abbr.upper()]
    renamed = frame.rename(columns=str.upper).set_geometry("GEOMETRY")
    filtered = renamed.loc[renamed["STATEFP"] == state_fips].copy()
    filtered = normalize_geometries(filtered)
    filtered = filtered.set_geometry("GEOMETRY").rename_geometry("geometry")
    filtered = filtered.to_crs(TARGET_CRS)
    filtered["town_name"] = filtered.get("NAMELSAD", filtered.get("NAME"))
    filtered["state"] = state_abbr.upper()
    filtered["base_area_m2"] = filtered.geometry.area
    return filtered[
        [
            "GEOID",
            "STATEFP",
            "COUNTYFP",
            "COUSUBFP",
            "town_name",
            "state",
            "base_area_m2",
            "geometry",
        ]
    ].reset_index(drop=True)


def extract_year_from_text(value: str | None) -> int | None:
    if not value:
        return None

    matches = YEAR_PATTERN.findall(value)
    return int(matches[-1]) if matches else None


def prepare_lidar(frame: gpd.GeoDataFrame, *, min_year: int = 2015) -> gpd.GeoDataFrame:
    renamed = frame.rename(columns=str.lower).set_geometry("geometry").copy()
    properties = {"name", "url", "id", "count"}
    missing = properties - set(renamed.columns)
    if missing:
        raise ValueError(f"LiDAR metadata missing expected columns: {sorted(missing)}")

    if "year" not in renamed.columns:
        renamed["year"] = pd.NA

    renamed["year"] = renamed["year"].where(renamed["year"].notna())
    parsed_years = renamed.apply(
        lambda row: row["year"]
        if pd.notna(row["year"])
        else extract_year_from_text(str(row["name"]))
        or extract_year_from_text(str(row["url"])),
        axis=1,
    )
    renamed["year"] = pd.to_numeric(parsed_years, errors="coerce").astype("Int64")
    renamed = renamed.loc[renamed["year"].notna() & (renamed["year"] >= min_year)].copy()
    renamed = normalize_geometries(renamed)
    renamed = renamed.set_geometry("geometry")
    renamed = renamed.to_crs(TARGET_CRS)
    renamed["lidar_name"] = renamed["name"]
    return renamed[["id", "lidar_name", "year", "url", "count", "geometry"]].reset_index(
        drop=True
    )
