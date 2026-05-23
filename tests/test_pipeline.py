from __future__ import annotations

import unittest

import geopandas as gpd
import pandas as pd
from pyproj import network
from shapely.geometry import box

from lidar_coverage.analysis import build_vintage_note, compute_coverage
from lidar_coverage.constants import TARGET_CRS
from lidar_coverage.preprocess import extract_year_from_text, prepare_lidar
from lidar_coverage.reporting import build_batch_markdown_summary, summarize_state


def build_towns() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "GEOID": ["001"],
            "town_name": ["Example town"],
            "state": ["RI"],
            "base_area_m2": [100.0],
        },
        geometry=[box(0, 0, 10, 10)],
        crs=TARGET_CRS,
    )


def build_lidar(geometry) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "id": ["modern"],
            "lidar_name": ["Survey_2021"],
            "year": [2021],
        },
        geometry=[geometry],
        crs=TARGET_CRS,
    )


class PipelineHelpersTest(unittest.TestCase):
    def test_extract_year_from_collection_name(self) -> None:
        self.assertEqual(extract_year_from_text("MA_CentralEastern_2_2021"), 2021)

    def test_extract_year_uses_latest_year_in_text(self) -> None:
        self.assertEqual(extract_year_from_text("survey_2015_reflight_2020"), 2020)

    def test_las_processing_year_is_ignored(self) -> None:
        self.assertEqual(extract_year_from_text("USGS_LPC_MD_PA_SandySupp_2014_LAS_2016"), 2014)

    def test_las_year_stripped_leaves_acquisition_year(self) -> None:
        self.assertEqual(extract_year_from_text("USGS_LPC_CA_LosAngeles_2016_LAS_2019"), 2016)

    def test_extract_year_from_usgs_delivery_suffix(self) -> None:
        self.assertEqual(extract_year_from_text("RI_Statewide_1_D22"), 2022)

    def test_extract_year_from_usgs_batch_suffix(self) -> None:
        self.assertEqual(extract_year_from_text("CA_CaliforniaGaps_1_B23"), 2023)

    def test_extract_year_from_usgs_acquisition_suffix(self) -> None:
        self.assertEqual(extract_year_from_text("TX_CentralEast_1_A23"), 2023)

    def test_four_digit_year_takes_precedence_over_suffix(self) -> None:
        self.assertEqual(extract_year_from_text("CA_LosAngeles_2016_LAS_D22"), 2016)

    def test_extract_year_from_missing_text(self) -> None:
        self.assertIsNone(extract_year_from_text("collection_without_year"))

    def test_extract_year_no_suffix_no_year(self) -> None:
        self.assertIsNone(extract_year_from_text("IA_FullState"))

    def test_url_four_digit_year_beats_name_suffix(self) -> None:
        from lidar_coverage.preprocess import _resolve_year

        result = _resolve_year("Example_D22", "https://example.com/project_2016/ept.json")
        self.assertEqual(result, 2016)

    def test_build_vintage_note_single_year(self) -> None:
        self.assertEqual(build_vintage_note([2021]), "Intersecting LiDAR year: 2021")

    def test_build_vintage_note_multiple_years(self) -> None:
        self.assertEqual(
            build_vintage_note([2021, 2018, 2021, 2015]),
            "Intersecting LiDAR years: 2015-2021 (2015, 2018, 2021)",
        )

    def test_build_vintage_note_respects_custom_min_year(self) -> None:
        result = build_vintage_note([], min_year=2022)
        self.assertEqual(result, "No intersecting 2022+ LiDAR batches")


class PreprocessingTest(unittest.TestCase):
    def test_prepare_lidar_keeps_2015_and_later_only(self) -> None:
        lidar = gpd.GeoDataFrame(
            {
                "id": ["old", "cutoff", "new"],
                "name": ["Survey_2014", "Survey_2015", "Survey_2022"],
                "url": ["old", "cutoff", "new"],
                "count": [1, 1, 1],
            },
            geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1), box(2, 0, 3, 1)],
            crs=TARGET_CRS,
        )

        prepared = prepare_lidar(lidar, min_year=2015)

        self.assertEqual(prepared["id"].tolist(), ["cutoff", "new"])
        self.assertEqual(prepared["year"].tolist(), [2015, 2022])

    def test_prepare_lidar_disables_optional_proj_network_transformations(self) -> None:
        network.set_network_enabled(True)
        lidar = gpd.GeoDataFrame(
            {
                "id": ["ri"],
                "name": ["Survey_2021"],
                "url": ["ri"],
                "count": [1],
            },
            geometry=[box(-71.5, 41.5, -71.4, 41.6)],
            crs="EPSG:4326",
        )

        prepared = prepare_lidar(lidar)

        self.assertFalse(network.is_network_enabled())
        self.assertFalse(prepared.geometry.is_empty.any())


class CoverageTest(unittest.TestCase):
    def test_coverage_is_bounded_between_zero_and_one_hundred(self) -> None:
        all_results, gap_results = compute_coverage(
            build_towns(),
            build_lidar(box(-1, -1, 11, 11)),
            coverage_threshold=5.0,
        )

        self.assertEqual(all_results.loc[0, "coverage_pct"], 100.0)
        self.assertGreaterEqual(all_results.loc[0, "coverage_pct"], 0.0)
        self.assertLessEqual(all_results.loc[0, "coverage_pct"], 100.0)
        self.assertEqual(all_results.loc[0, "gap_area_m2"], 0.0)
        self.assertTrue(gap_results.empty)

    def test_empty_lidar_produces_full_gap(self) -> None:
        empty_lidar = gpd.GeoDataFrame(geometry=gpd.GeoSeries([], crs=TARGET_CRS))

        all_results, gap_results = compute_coverage(
            build_towns(),
            empty_lidar,
            coverage_threshold=5.0,
        )

        self.assertEqual(all_results.loc[0, "coverage_pct"], 0.0)
        self.assertEqual(all_results.loc[0, "gap_area_m2"], 100.0)
        self.assertEqual(len(gap_results), 1)


class BatchSummaryTest(unittest.TestCase):
    def test_multi_state_summary_contains_each_state(self) -> None:
        uncovered, uncovered_gaps = compute_coverage(
            build_towns(),
            gpd.GeoDataFrame(geometry=gpd.GeoSeries([], crs=TARGET_CRS)),
        )
        covered, covered_gaps = compute_coverage(
            build_towns(),
            build_lidar(box(0, 0, 10, 10)),
        )
        summary = pd.DataFrame(
            [
                summarize_state("RI", uncovered, uncovered_gaps),
                summarize_state("MA", covered, covered_gaps),
            ]
        )

        markdown = build_batch_markdown_summary(summary, threshold=5.0, min_year=2015)

        self.assertEqual(summary["state"].tolist(), ["RI", "MA"])
        self.assertEqual(summary["county_subdivisions_below_threshold"].tolist(), [1, 0])
        self.assertIn("| RI | 1 | 1 |", markdown)
        self.assertIn("| MA | 1 | 0 |", markdown)


if __name__ == "__main__":
    unittest.main()
