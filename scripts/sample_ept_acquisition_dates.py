"""Estimate when a LiDAR collection was acquired from a sample of its points.

Verification tool for vintage reconciliation, not part of the analysis
pipeline. It reads a collection's public Entwine Point Tile (EPT) index, picks
random octree nodes from the coarse levels (which hold a spatially even subset
of the whole collection), downloads only those nodes (~1 MB each), and
converts each point's ``GpsTime`` to a calendar date.

Adjusted Standard GPS time (seconds since 1980-01-06 minus 1e9) carries a full
date. GPS week time (0-604800 s) carries no date; such points are counted as
``week_time_or_ambiguous`` instead of being converted. Dates use the 1st/99th
percentiles to ignore stray outliers.

Requires the optional ``verify`` dependency group:

    uv run --group verify python scripts/sample_ept_acquisition_dates.py MN_FullState
"""

from __future__ import annotations

import argparse
import io
import json
import random
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from lidar_coverage.io import build_session

EPT_ROOT = "https://s3-us-west-2.amazonaws.com/usgs-lidar-public"
GPS_EPOCH = datetime(1980, 1, 6, tzinfo=UTC)
ADJUSTED_OFFSET = 1_000_000_000
WEEK_SECONDS = 604_800


# Adjusted Standard GPS time window for plausible acquisitions (~1998 to ~2030).
ADJUSTED_MIN, ADJUSTED_MAX = -4.2e8, 6.5e8


def classify_gps_time(gps_time: np.ndarray) -> tuple[pd.DatetimeIndex, dict[str, float]]:
    """Convert plausible Adjusted Standard GPS times to dates.

    Values in ``[0, 604800)`` are ambiguous with GPS week time (no date) and are
    counted separately rather than converted; values outside the plausible
    window are counted as invalid.
    """
    finite = gps_time[np.isfinite(gps_time)]
    week = (finite >= 0) & (finite < WEEK_SECONDS)
    adjusted = ~week & (finite >= ADJUSTED_MIN) & (finite <= ADJUSTED_MAX)
    total = max(gps_time.size, 1)
    shares = {
        "dated_pct": round(adjusted.sum() / total * 100, 1),
        "week_time_or_ambiguous_pct": round(week.sum() / total * 100, 1),
        "invalid_pct": round((gps_time.size - adjusted.sum() - week.sum()) / total * 100, 1),
    }
    seconds = finite[adjusted] + ADJUSTED_OFFSET
    # Leap seconds (~18 s) are irrelevant at the resolution we need.
    return pd.to_datetime(GPS_EPOCH) + pd.to_timedelta(seconds, unit="s"), shares


def sample_nodes(hierarchy: dict[str, int], max_depth: int, count: int, seed: int) -> list[str]:
    candidates = [
        key
        for key, points in hierarchy.items()
        if points > 0 and int(key.split("-")[0]) <= max_depth
    ]
    rng = random.Random(seed)
    return sorted(rng.sample(candidates, min(count, len(candidates))))


def sample_collection(
    name: str, *, max_depth: int = 4, nodes: int = 24, seed: int = 0
) -> dict[str, object]:
    import laspy  # optional dependency (uv --group verify)

    session = build_session()
    base = f"{EPT_ROOT}/{name}"
    info = session.get(f"{base}/ept.json", timeout=(30, 120)).json()
    if info.get("dataType") != "laszip":
        raise RuntimeError(f"{name}: unsupported EPT dataType {info.get('dataType')!r}")
    hierarchy = session.get(f"{base}/ept-hierarchy/0-0-0-0.json", timeout=(30, 120)).json()

    times: list[np.ndarray] = []
    downloaded = 0
    for key in sample_nodes(hierarchy, max_depth, nodes, seed):
        response = session.get(f"{base}/ept-data/{key}.laz", timeout=(30, 300))
        response.raise_for_status()
        downloaded += len(response.content)
        las = laspy.read(io.BytesIO(response.content))
        if "gps_time" not in las.point_format.dimension_names:
            return {"collection": name, "time_format": "no GpsTime in point format"}
        times.append(np.asarray(las.gps_time, dtype="float64"))

    gps = np.concatenate(times) if times else np.array([])
    dates, shares = classify_gps_time(gps)
    result: dict[str, object] = {
        "collection": name,
        "nodes_sampled": len(times),
        "points_sampled": int(gps.size),
        "bytes_downloaded": downloaded,
        **shares,
    }
    if dates.empty:
        return result

    series = pd.Series(dates)
    share = (series.dt.year.value_counts(normalize=True).sort_index() * 100).round(1)
    result.update(
        earliest=str(series.min().date()),
        p01=str(series.quantile(0.01).date()),
        median=str(series.quantile(0.5).date()),
        p99=str(series.quantile(0.99).date()),
        latest=str(series.max().date()),
        year_share_pct={int(year): float(pct) for year, pct in share.items() if pct >= 0.1},
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("collections", nargs="+", help="EPT collection names (inventory 'name').")
    parser.add_argument("--nodes", type=int, default=24, help="Random octree nodes per collection.")
    parser.add_argument("--max-depth", type=int, default=4, help="Deepest octree level to sample.")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    for name in args.collections:
        try:
            result = sample_collection(
                name, max_depth=args.max_depth, nodes=args.nodes, seed=args.seed
            )
        except Exception as error:  # noqa: BLE001 - keep going across collections
            result = {"collection": name, "error": str(error)}
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
