"""Download and load source datasets."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from lidar_coverage.constants import (
    CENSUS_COUSUB_URL_TEMPLATE,
    CENSUS_TIGER_YEAR,
    STATE_TO_FIPS,
    USGS_LIDAR_METADATA_URL,
)


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "lidar-coverage/0.1"})
    return session


def download_file(
    url: str,
    destination: Path,
    *,
    timeout: tuple[int, int] = (30, 600),
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return destination

    with _build_session().get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        with destination.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)

    return destination


def download_census_cousub(
    state_abbr: str,
    cache_dir: Path,
    *,
    tiger_year: int = CENSUS_TIGER_YEAR,
) -> Path:
    state_fips = STATE_TO_FIPS[state_abbr.upper()]
    url = CENSUS_COUSUB_URL_TEMPLATE.format(year=tiger_year, state_fips=state_fips)
    destination = cache_dir / "census" / f"tl_{tiger_year}_{state_fips}_cousub.zip"
    return download_file(url, destination)


def download_usgs_lidar_metadata(cache_dir: Path) -> Path:
    destination = cache_dir / "usgs" / "resources.geojson"
    return download_file(USGS_LIDAR_METADATA_URL, destination)


def read_vector(path: Path) -> gpd.GeoDataFrame:
    return gpd.read_file(path)
