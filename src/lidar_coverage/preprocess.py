"""Preprocessing helpers for geometry and metadata."""

from __future__ import annotations

import re
from pathlib import Path

import geopandas as gpd
import pandas as pd
from pyproj import network
from shapely import get_parts, make_valid
from shapely.errors import GEOSException
from shapely.geometry import MultiPolygon

from lidar_coverage.constants import DEFAULT_MIN_YEAR, STATE_TO_FIPS, TARGET_CRS

YEAR_PATTERN = re.compile(r"(?:19|20)\d{2}")
LAS_YEAR_PATTERN = re.compile(r"_LAS_(?:19|20)\d{2}")
USGS_SUFFIX_PATTERN = re.compile(r"_([A-Da-d])(\d{2})$")
USGS_LPC_PREFIX_PATTERN = re.compile(r"^USGS_LPC_", re.IGNORECASE)
TRAILING_LAS_PATTERN = re.compile(r"_LAS_(?:19|20)\d{2}$", re.IGNORECASE)
NON_ALNUM_PATTERN = re.compile(r"[^0-9a-z]+")

UNDEFINED_COUSUBFP = "00000"
POLYGONAL_TYPES = {"Polygon", "MultiPolygon"}

LIDAR_COLUMNS = [
    "id",
    "lidar_name",
    "collection_key",
    "year",
    "year_source",
    "url",
    "count",
    "geometry",
]


def _use_repeatable_projection() -> None:
    # Avoid a CRS result that changes when optional PROJ grid downloads are unavailable.
    network.set_network_enabled(False)


def _repair_geometry(geometry):
    """Return a valid, purely polygonal geometry (or None); only areas matter here."""
    if geometry is None or geometry.is_empty:
        return None

    try:
        repaired = make_valid(geometry)
    except GEOSException:
        # Mixed-dimension collections (e.g. from generalized source shapes).
        repaired = make_valid(geometry, method="structure", keep_collapsed=False)
    polygons = [part for part in get_parts(repaired) if part.geom_type in POLYGONAL_TYPES]
    if not polygons:
        return None
    return (
        polygons[0]
        if len(polygons) == 1
        else MultiPolygon([poly for part in polygons for poly in get_parts(part)])
    )


def normalize_geometries(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    geometry_name = frame.geometry.name
    normalized = frame.copy()
    normalized[geometry_name] = normalized.geometry.map(_repair_geometry)
    normalized = normalized.dropna(subset=[geometry_name]).explode(index_parts=False)
    normalized = normalized.set_geometry(geometry_name)
    normalized = normalized[~normalized.geometry.is_empty].copy()
    return normalized


def prepare_cousub(frame: gpd.GeoDataFrame, state_abbr: str) -> gpd.GeoDataFrame:
    _use_repeatable_projection()
    state_fips = STATE_TO_FIPS[state_abbr.upper()]
    renamed = frame.rename(columns=str.upper).set_geometry("GEOMETRY")
    # COUSUBFP 00000 marks "County subdivisions not defined" placeholders (mostly water).
    keep = (renamed["STATEFP"] == state_fips) & (renamed["COUSUBFP"] != UNDEFINED_COUSUBFP)
    filtered = renamed.loc[keep].copy()
    filtered = normalize_geometries(filtered)
    filtered = filtered.set_geometry("GEOMETRY").rename_geometry("geometry")
    filtered = filtered.to_crs(TARGET_CRS)
    filtered["town_name"] = filtered.get("NAMELSAD", filtered.get("NAME"))
    filtered["state"] = state_abbr.upper()

    # Merge multi-part fragments back into one row per GEOID.
    keep_first = ["STATEFP", "COUNTYFP", "COUSUBFP", "town_name", "state"]
    filtered = filtered.dissolve(by="GEOID", aggfunc=dict.fromkeys(keep_first, "first"))
    filtered = filtered.reset_index()
    filtered = gpd.GeoDataFrame(filtered, geometry="geometry", crs=TARGET_CRS)
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


def normalize_collection_key(name: str) -> str:
    """Stable identity for a LiDAR collection across inventory aliases.

    Strips the ``USGS_LPC_`` publication prefix and a trailing ``_LAS_YYYY``
    processing token, then lower-cases and collapses separators, so that
    ``USGS_LPC_CA_NoCAL_Wildfires_PlumasNF_B2_2018`` and
    ``CA_NoCAL_Wildfires_PlumasNF_B2_2018`` share one key. Official USGS
    work-unit names normalize to the same form.
    """
    stripped = TRAILING_LAS_PATTERN.sub("", USGS_LPC_PREFIX_PATTERN.sub("", name.strip()))
    return NON_ALNUM_PATTERN.sub("_", stripped.lower()).strip("_")


def _extract_year_from_usgs_suffix(value: str) -> int | None:
    """Parse USGS batch/delivery suffixes like _D22 -> 2022, _B23 -> 2023."""
    match = USGS_SUFFIX_PATTERN.search(value)
    if match:
        return 2000 + int(match.group(2))
    return None


def _extract_four_digit_year(value: str | None) -> int | None:
    """Return a four-digit acquisition year, ignoring _LAS_ processing years."""
    if not value:
        return None
    cleaned = LAS_YEAR_PATTERN.sub("", value)
    matches = YEAR_PATTERN.findall(cleaned)
    return int(matches[-1]) if matches else None


def extract_year_from_text(value: str | None) -> int | None:
    if not value:
        return None
    four_digit = _extract_four_digit_year(value)
    if four_digit is not None:
        return four_digit
    return _extract_year_from_usgs_suffix(value)


def resolve_year(name: str, url: str) -> tuple[int | None, str]:
    """Pick the best text-derived vintage year across name and URL fields.

    Four-digit acquisition years (from either field) take precedence over
    USGS batch/delivery suffixes. Returns ``(year, source)``.
    """
    four_digit = _extract_four_digit_year(name) or _extract_four_digit_year(url)
    if four_digit is not None:
        return four_digit, "text_year"
    suffix = _extract_year_from_usgs_suffix(name) or _extract_year_from_usgs_suffix(url)
    if suffix is not None:
        return suffix, "usgs_suffix"
    return None, "unresolved"


def load_vintage_overrides(path: Path) -> dict[str, int]:
    """Read authoritative vintages from a ``collection_key,start_year[,end_year]`` CSV.

    A collection counts as acquired in its **latest** acquisition year
    (``end_year`` when given, otherwise ``start_year``), so a collection that
    spans the ``min_year`` boundary is treated as modern. Keys are
    re-normalized, so the file may contain raw inventory or official work-unit
    names; when a key repeats, the latest year wins.
    """
    table = pd.read_csv(path, dtype={"collection_key": str})
    missing = {"collection_key", "start_year"} - set(table.columns)
    if missing:
        raise ValueError(f"{path}: vintage override file missing columns {sorted(missing)}")
    table = table.dropna(subset=["collection_key", "start_year"])
    table["collection_key"] = table["collection_key"].map(normalize_collection_key)
    latest = table["start_year"].astype(int)
    if "end_year" in table.columns:
        end = pd.to_numeric(table["end_year"], errors="coerce")
        latest = end.where(end.notna() & (end > latest), latest).astype(int)
    table["vintage_year"] = latest
    return table.groupby("collection_key")["vintage_year"].max().to_dict()


def usgs_3dep_as_inventory(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Reshape official 3DEP work units into the inventory schema.

    ``year`` is the year of ``collect_end`` (falling back to ``collect_start``),
    consistent with the latest-acquisition-year policy.
    """

    def year_of(column: str) -> pd.Series:
        return pd.to_datetime(frame[column], unit="ms", utc=True, errors="coerce").dt.year

    return gpd.GeoDataFrame(
        {
            "id": "3dep:" + frame["workunit_id"].astype(str),
            "name": frame["workunit"].astype(str),
            "url": frame["lpc_link"].fillna(""),
            "count": 0,
            "year": year_of("collect_end").fillna(year_of("collect_start")).astype("Int64"),
            "year_source_hint": "usgs_3dep_index",
        },
        geometry=frame.geometry.values,
        crs=frame.crs,
    )


def classify_lidar_vintage(
    frame: gpd.GeoDataFrame,
    *,
    overrides: dict[str, int] | None = None,
) -> gpd.GeoDataFrame:
    """Attach ``collection_key``, ``year``, and ``year_source`` to every record.

    Priority: authoritative override, then a ``year`` column already present in
    the inventory, then text parsing of the name/URL. No rows are dropped.
    """
    renamed = frame.rename(columns=str.lower).set_geometry("geometry").copy()
    missing = {"name", "url", "id", "count"} - set(renamed.columns)
    if missing:
        raise ValueError(f"LiDAR metadata missing expected columns: {sorted(missing)}")

    overrides = overrides or {}
    inventory_years = renamed["year"] if "year" in renamed.columns else None
    source_hints = renamed["year_source_hint"] if "year_source_hint" in renamed.columns else None
    keys: list[str] = []
    years: list[int | None] = []
    sources: list[str] = []
    for position, (name, url) in enumerate(zip(renamed["name"], renamed["url"], strict=True)):
        key = normalize_collection_key(str(name))
        keys.append(key)
        if key in overrides:
            years.append(overrides[key])
            sources.append("override")
        elif inventory_years is not None and pd.notna(inventory_years.iloc[position]):
            years.append(int(inventory_years.iloc[position]))
            sources.append(source_hints.iloc[position] if source_hints is not None else "inventory")
        else:
            year, source = resolve_year(str(name), str(url))
            years.append(year)
            sources.append(source)

    renamed["lidar_name"] = renamed["name"]
    renamed["collection_key"] = keys
    renamed["year"] = pd.array(years, dtype="Int64")
    renamed["year_source"] = sources
    return renamed[LIDAR_COLUMNS]


def select_modern_lidar(
    classified: gpd.GeoDataFrame, *, min_year: int = DEFAULT_MIN_YEAR
) -> gpd.GeoDataFrame:
    """Keep footprints with a known vintage >= ``min_year`` in the analysis CRS."""
    _use_repeatable_projection()
    modern = classified.loc[classified["year"].notna() & (classified["year"] >= min_year)].copy()
    modern = normalize_geometries(modern).set_geometry("geometry").to_crs(TARGET_CRS)
    return modern[LIDAR_COLUMNS].reset_index(drop=True)


def prepare_lidar(
    frame: gpd.GeoDataFrame,
    *,
    min_year: int = DEFAULT_MIN_YEAR,
    overrides: dict[str, int] | None = None,
) -> gpd.GeoDataFrame:
    return select_modern_lidar(
        classify_lidar_vintage(frame, overrides=overrides), min_year=min_year
    )
