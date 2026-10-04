"""Project constants."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

STATE_TO_FIPS = {
    "AL": "01",
    "AK": "02",
    "AZ": "04",
    "AR": "05",
    "CA": "06",
    "CO": "08",
    "CT": "09",
    "DE": "10",
    "DC": "11",
    "FL": "12",
    "GA": "13",
    "HI": "15",
    "ID": "16",
    "IL": "17",
    "IN": "18",
    "IA": "19",
    "KS": "20",
    "KY": "21",
    "LA": "22",
    "ME": "23",
    "MD": "24",
    "MA": "25",
    "MI": "26",
    "MN": "27",
    "MS": "28",
    "MO": "29",
    "MT": "30",
    "NE": "31",
    "NV": "32",
    "NH": "33",
    "NJ": "34",
    "NM": "35",
    "NY": "36",
    "NC": "37",
    "ND": "38",
    "OH": "39",
    "OK": "40",
    "OR": "41",
    "PA": "42",
    "RI": "44",
    "SC": "45",
    "SD": "46",
    "TN": "47",
    "TX": "48",
    "UT": "49",
    "VT": "50",
    "VA": "51",
    "WA": "53",
    "WV": "54",
    "WI": "55",
    "WY": "56",
}

# Contiguous 48 states plus DC; excludes AK, HI, and territories.
NON_CONUS_STATES = frozenset({"AK", "HI"})
CONUS_STATES = tuple(state for state in STATE_TO_FIPS if state not in NON_CONUS_STATES)
STATE_GROUPS = {"CONUS": CONUS_STATES}

TARGET_CRS = "EPSG:5070"
CENSUS_TIGER_YEAR = 2024
CENSUS_COUSUB_URL_TEMPLATE = (
    "https://www2.census.gov/geo/tiger/TIGER{year}/COUSUB/tl_{year}_{state_fips}_cousub.zip"
)
USGS_LIDAR_METADATA_URL = (
    "https://raw.githubusercontent.com/hobuinc/usgs-lidar/master/boundaries/resources.geojson"
)
USGS_WORKUNIT_QUERY_URL = (
    "https://index.nationalmap.gov/arcgis/rest/services/3DEPElevationIndex/MapServer/8/query"
)
DEFAULT_MIN_YEAR = 2015
# Reviewed authoritative vintages shipped with the package (see Progress.md).
REVIEWED_VINTAGE_OVERRIDES = Path(
    str(files("lidar_coverage") / "data" / "vintage_overrides_reviewed.csv")
)
DEFAULT_COVERAGE_THRESHOLD = 5.0

# Newer state-run LiDAR programs that are not (fully) in the USGS inventory.
# Reported in summaries so gap counts are read against the right source.
STATE_PROGRAM_NOTES = {
    "MN": (
        "Minnesota's statewide Gen2 LiDAR (collected 2021-2024, MnGeo: "
        "https://mn.gov/mngeo/gis-data-and-maps/info-by-topic/elevation/lidar/lidar-gen2.jsp) "
        "is only partly in the USGS inventory used here; `MN_FullState` is the 2011-2012 "
        "generation. Gaps may be covered by Gen2 data."
    ),
    "KY": (
        "KyFromAbove (https://kyfromabove.ky.gov/) has flown the state three times; Phase 2 "
        "(~2024) and Phase 3 (~2025-2026) are not in the USGS inventory used here "
        "(`KY_FullState` is the 2010-2018 Phase 1 mosaic). Gaps may be covered by state data."
    ),
}
