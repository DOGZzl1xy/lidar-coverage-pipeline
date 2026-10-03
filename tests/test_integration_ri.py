"""Independent spot-check of RI coverage against a per-footprint calculation.

Runs only when the RI TIGER/Line file and the LiDAR inventory are cached
under ``data/cache`` (created by any pipeline run).
"""

from __future__ import annotations

import unittest
from pathlib import Path

from shapely import union_all

from lidar_coverage.analysis import compute_coverage
from lidar_coverage.io import read_vector
from lidar_coverage.preprocess import prepare_cousub, prepare_lidar

CACHE = Path(__file__).resolve().parents[1] / "data" / "cache"
CENSUS_ZIP = CACHE / "census" / "tl_2024_44_cousub.zip"
INVENTORY = CACHE / "usgs" / "resources.geojson"
SAMPLE_GEOIDS = ["4400322240", "4400109280", "4400714140"]  # East Greenwich, Bristol, Central Falls


@unittest.skipUnless(CENSUS_ZIP.exists() and INVENTORY.exists(), "RI source data not cached")
class RhodeIslandSpotCheck(unittest.TestCase):
    def test_pipeline_matches_independent_union(self) -> None:
        towns = prepare_cousub(read_vector(CENSUS_ZIP), "RI")
        lidar = prepare_lidar(read_vector(INVENTORY))
        all_results, _ = compute_coverage(towns, lidar)
        results = all_results.set_index("GEOID")
        town_lookup = towns.set_index("GEOID")

        for geoid in SAMPLE_GEOIDS:
            town = town_lookup.loc[geoid]
            pieces = [
                geometry.intersection(town.geometry)
                for geometry in lidar.geometry
                if geometry.intersects(town.geometry)
            ]
            covered = union_all(pieces).area if pieces else 0.0
            expected = round(min(covered / town.base_area_m2 * 100, 100.0), 2)
            with self.subTest(geoid=geoid):
                self.assertAlmostEqual(results.loc[geoid, "coverage_pct"], expected, places=2)


if __name__ == "__main__":
    unittest.main()
