"""Download and load source datasets."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
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
    USGS_WORKUNIT_QUERY_URL,
)

# ~50 m generalization keeps the national work-unit layer near 7 MB.
USGS_3DEP_SIMPLIFY_DEGREES = 0.0005
USGS_3DEP_FIELDS = "workunit,workunit_id,collect_start,collect_end,lpc_link"


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "lidar-coverage/0.2"})
    return session


def download_file(
    url: str,
    destination: Path,
    *,
    refresh: bool = False,
    timeout: tuple[int, int] = (30, 600),
) -> Path:
    """Download ``url`` to ``destination`` unless a non-empty cached copy exists.

    The response is streamed to a ``.part`` file and renamed only after the
    transfer completes, so an interrupted download never leaves a truncated
    file that later runs would silently reuse.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0 and not refresh:
        return destination

    partial = destination.with_name(destination.name + ".part")
    try:
        with build_session().get(url, stream=True, timeout=timeout) as response:
            response.raise_for_status()
            with partial.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)
        if partial.stat().st_size == 0:
            raise OSError(f"Empty response body from {url}")
        partial.replace(destination)
    finally:
        partial.unlink(missing_ok=True)

    return destination


def census_cousub_url(state_abbr: str, *, tiger_year: int = CENSUS_TIGER_YEAR) -> str:
    state_fips = STATE_TO_FIPS[state_abbr.upper()]
    return CENSUS_COUSUB_URL_TEMPLATE.format(year=tiger_year, state_fips=state_fips)


def download_census_cousub(
    state_abbr: str,
    cache_dir: Path,
    *,
    tiger_year: int = CENSUS_TIGER_YEAR,
    refresh: bool = False,
) -> Path:
    state_fips = STATE_TO_FIPS[state_abbr.upper()]
    destination = cache_dir / "census" / f"tl_{tiger_year}_{state_fips}_cousub.zip"
    return download_file(
        census_cousub_url(state_abbr, tiger_year=tiger_year), destination, refresh=refresh
    )


def download_usgs_lidar_metadata(cache_dir: Path, *, refresh: bool = False) -> Path:
    destination = cache_dir / "usgs" / "resources.geojson"
    return download_file(USGS_LIDAR_METADATA_URL, destination, refresh=refresh)


def download_usgs_3dep_index(
    cache_dir: Path, *, refresh: bool = False, page_size: int = 500
) -> Path:
    """Cache the official 3DEP work-unit footprints (generalized, no point data)."""
    destination = cache_dir / "usgs" / "3dep_workunits.geojson"
    if destination.exists() and destination.stat().st_size > 0 and not refresh:
        return destination

    session = build_session()
    features: list[dict] = []
    while True:
        response = session.get(
            USGS_WORKUNIT_QUERY_URL,
            params={
                "where": "1=1",
                "outFields": USGS_3DEP_FIELDS,
                "returnGeometry": "true",
                "outSR": 4326,
                "maxAllowableOffset": USGS_3DEP_SIMPLIFY_DEGREES,
                "orderByFields": "OBJECTID",
                "resultOffset": len(features),
                "resultRecordCount": page_size,
                "f": "geojson",
            },
            timeout=(30, 600),
        )
        response.raise_for_status()
        payload = response.json()
        page = payload.get("features", [])
        features.extend(page)
        if not page or not payload.get(
            "exceededTransferLimit", payload.get("properties", {}).get("exceededTransferLimit")
        ):
            break

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    partial.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8"
    )
    partial.replace(destination)
    return destination


def read_vector(path: Path) -> gpd.GeoDataFrame:
    return gpd.read_file(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def describe_input(path: Path, url: str | None = None) -> dict[str, object]:
    """Provenance record for one input file, stored in the run manifest."""
    stat = path.stat()
    return {
        "url": url,
        "path": str(path),
        "bytes": stat.st_size,
        "sha256": sha256_file(path),
        "cached_at_utc": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(timespec="seconds"),
    }
