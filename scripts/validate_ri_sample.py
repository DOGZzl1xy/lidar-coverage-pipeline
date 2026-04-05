from __future__ import annotations

from pathlib import Path

from shapely import union_all

from lidar_coverage.analysis import compute_coverage
from lidar_coverage.io import read_vector
from lidar_coverage.preprocess import prepare_cousub, prepare_lidar


def independent_coverage_for_town(town_row, lidar_frame) -> float:
    intersections = []
    for geom in lidar_frame.geometry:
        if geom.intersects(town_row.geometry):
            piece = geom.intersection(town_row.geometry)
            if not piece.is_empty:
                intersections.append(piece)

    if not intersections:
        return 0.0

    covered = union_all(intersections).area
    return round(covered / town_row.base_area_m2 * 100, 2)


def main() -> None:
    base = Path(__file__).resolve().parents[1]
    towns = prepare_cousub(read_vector(base / "data" / "cache" / "census" / "tl_2024_44_cousub.zip"), "RI")
    lidar = prepare_lidar(read_vector(base / "data" / "cache" / "usgs" / "resources.geojson"), min_year=2015)
    all_results, _ = compute_coverage(towns, lidar, coverage_threshold=5.0)

    sample_geoids = [
        "4400322240",  # East Greenwich town
        "4400109280",  # Bristol town
        "4400714140",  # Central Falls city
    ]

    result_lookup = all_results.set_index("GEOID")
    town_lookup = towns.set_index("GEOID")

    print("GEOID,Town,PipelineCoverage,IndependentCoverage,Match")
    for geoid in sample_geoids:
        town_row = town_lookup.loc[geoid]
        pipeline_coverage = round(float(result_lookup.loc[geoid, "coverage_pct"]), 2)
        independent_coverage = independent_coverage_for_town(town_row, lidar)
        print(
            f"{geoid},"
            f"{town_row.town_name},"
            f"{pipeline_coverage:.2f},"
            f"{independent_coverage:.2f},"
            f"{pipeline_coverage == independent_coverage}"
        )


if __name__ == "__main__":
    main()
