"""Build a vintage override CSV from the official USGS 3DEP work-unit index.

Queries attributes only (``returnGeometry=false``) from the 3DEP Elevation
Index "Lidar Point Cloud" layer; no point clouds or footprints are downloaded.
The output feeds ``lidar-coverage --vintage-overrides``. Each official work
unit is keyed by ``normalize_collection_key(workunit)`` with the years of its
``collect_start`` and ``collect_end``; the pipeline classifies a collection by
its latest acquisition year, so collections spanning ``min_year`` count as
modern.
Inventory names that do not normalize to an official work unit keep their
text-derived year; reconcile those through a reviewed crosswalk.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from lidar_coverage.constants import USGS_WORKUNIT_QUERY_URL
from lidar_coverage.io import build_session
from lidar_coverage.preprocess import normalize_collection_key

FIELDS = ["workunit", "workunit_id", "project", "collect_start", "collect_end"]
PAGE_SIZE = 1000


def fetch_workunits(url: str = USGS_WORKUNIT_QUERY_URL) -> pd.DataFrame:
    session = build_session()
    records: list[dict] = []
    offset = 0
    while True:
        response = session.get(
            url,
            params={
                "where": "1=1",
                "outFields": ",".join(FIELDS),
                "returnGeometry": "false",
                "orderByFields": "OBJECTID",
                "resultOffset": offset,
                "resultRecordCount": PAGE_SIZE,
                "f": "json",
            },
            timeout=(30, 300),
        )
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            raise RuntimeError(f"USGS index query failed: {payload['error']}")
        page = [feature["attributes"] for feature in payload.get("features", [])]
        records.extend(page)
        if not page or not payload.get("exceededTransferLimit"):
            break
        offset += len(page)
    return pd.DataFrame(records, columns=FIELDS)


def build_overrides(workunits: pd.DataFrame) -> pd.DataFrame:
    frame = workunits.dropna(subset=["workunit", "collect_start"]).copy()
    frame["collection_key"] = frame["workunit"].map(normalize_collection_key)
    frame["start_year"] = pd.to_datetime(frame["collect_start"], unit="ms", utc=True).dt.year
    end = pd.to_datetime(frame["collect_end"], unit="ms", utc=True).dt.year
    frame["end_year"] = end.fillna(frame["start_year"]).astype(int)
    frame = frame.sort_values(["collection_key", "start_year"])
    overrides = frame.groupby("collection_key", as_index=False).agg(
        start_year=("start_year", "min"),
        end_year=("end_year", "max"),
        workunit=("workunit", "first"),
        workunit_id=("workunit_id", "first"),
    )
    overrides["source"] = "USGS 3DEP Elevation Index MapServer/8 collect_start/collect_end"
    return overrides


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("usgs_workunit_vintage.csv"),
    )
    args = parser.parse_args()

    workunits = fetch_workunits()
    overrides = build_overrides(workunits)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    overrides.to_csv(args.output, index=False)
    retrieved = datetime.now(UTC).isoformat(timespec="seconds")
    print(
        f"Retrieved {len(workunits)} work units at {retrieved}; wrote "
        f"{len(overrides)} collection keys to {args.output}."
    )


if __name__ == "__main__":
    main()
