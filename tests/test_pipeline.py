from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import geopandas as gpd
import pandas as pd
from pyproj import network
from shapely.geometry import box

from lidar_coverage.analysis import build_vintage_note, compute_coverage
from lidar_coverage.cli import normalize_states
from lidar_coverage.constants import CONUS_STATES, TARGET_CRS
from lidar_coverage.preprocess import (
    classify_lidar_vintage,
    extract_year_from_text,
    load_vintage_overrides,
    normalize_collection_key,
    prepare_cousub,
    prepare_lidar,
    resolve_year,
    usgs_3dep_as_inventory,
)
from lidar_coverage.reporting import (
    build_batch_markdown_summary,
    build_markdown_summary,
    summarize_state,
)


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


def build_lidar(*geometries, keys: list[str] | None = None) -> gpd.GeoDataFrame:
    keys = keys or [f"survey_{index}_2021" for index in range(len(geometries))]
    return gpd.GeoDataFrame(
        {"collection_key": keys, "year": [2021] * len(geometries)},
        geometry=list(geometries),
        crs=TARGET_CRS,
    )


def build_inventory(names: list[str]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "id": list(range(len(names))),
            "name": names,
            "url": [f"https://example.com/{name}/ept.json" for name in names],
            "count": [1] * len(names),
        },
        geometry=[box(index, 0, index + 1, 1) for index in range(len(names))],
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
        result = resolve_year("Example_D22", "https://example.com/project_2016/ept.json")
        self.assertEqual(result, (2016, "text_year"))

    def test_resolve_year_reports_unresolved(self) -> None:
        self.assertEqual(
            resolve_year("IA_FullState", "https://x/IA_FullState"), (None, "unresolved")
        )

    def test_collection_key_merges_usgs_lpc_and_las_aliases(self) -> None:
        self.assertEqual(
            normalize_collection_key("USGS_LPC_CA_NoCAL_Wildfires_PlumasNF_B2_2018"),
            normalize_collection_key("CA_NoCAL_Wildfires_PlumasNF_B2_2018"),
        )
        self.assertEqual(
            normalize_collection_key("USGS_LPC_WI_DodgeCo_2017_LAS_2019"), "wi_dodgeco_2017"
        )

    def test_collection_key_keeps_distinct_batches(self) -> None:
        self.assertNotEqual(
            normalize_collection_key("CA_NoCAL_Wildfires_PlumasNF_B1_2018"),
            normalize_collection_key("CA_NoCAL_Wildfires_PlumasNF_B2_2018"),
        )

    def test_conus_group_expands_to_48_states_plus_dc(self) -> None:
        states = normalize_states(["conus"])
        self.assertEqual(len(states), 49)
        self.assertEqual(states, list(CONUS_STATES))
        self.assertIn("DC", states)
        self.assertNotIn("AK", states)
        self.assertNotIn("HI", states)

    def test_state_list_rejects_unknown_codes(self) -> None:
        with self.assertRaises(ValueError):
            normalize_states(["PR"])

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


class CousubPreparationTest(unittest.TestCase):
    def test_undefined_placeholders_are_dropped_and_parts_dissolved(self) -> None:
        raw = gpd.GeoDataFrame(
            {
                "STATEFP": ["44", "44", "44", "25"],
                "COUNTYFP": ["001"] * 4,
                "COUSUBFP": ["09280", "09280", "00000", "09280"],
                "GEOID": ["4400109280", "4400109280", "4400100000", "2500109280"],
                "NAMELSAD": [
                    "Bristol town",
                    "Bristol town",
                    "County subdivisions not defined",
                    "X",
                ],
            },
            geometry=[box(0, 0, 1, 1), box(2, 0, 3, 1), box(5, 0, 6, 1), box(8, 0, 9, 1)],
            crs=TARGET_CRS,
        )
        towns = prepare_cousub(raw, "RI")

        self.assertEqual(towns["GEOID"].tolist(), ["4400109280"])
        self.assertAlmostEqual(towns.loc[0, "base_area_m2"], 2.0)


class VintageOverrideTest(unittest.TestCase):
    def test_override_replaces_text_year_and_records_source(self) -> None:
        inventory = build_inventory(["USGS_LPC_PA_SandySupp_2016_LAS_2018", "Survey_2021"])
        classified = classify_lidar_vintage(inventory, overrides={"pa_sandysupp_2016": 2014})

        self.assertEqual(classified["year"].tolist(), [2014, 2021])
        self.assertEqual(classified["year_source"].tolist(), ["override", "text_year"])

    def test_pre_threshold_override_is_excluded_from_modern(self) -> None:
        inventory = build_inventory(["PA_SandySupp_2016", "Survey_2021"])
        prepared = prepare_lidar(inventory, min_year=2015, overrides={"pa_sandysupp_2016": 2014})
        self.assertEqual(prepared["lidar_name"].tolist(), ["Survey_2021"])

    def test_boundary_spanning_collection_counts_as_modern(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overrides.csv"
            path.write_text(
                "collection_key,start_year,end_year\nKS_SCentral_L4_2015,2014,2015\n",
                encoding="utf-8",
            )
            overrides = load_vintage_overrides(path)
        inventory = build_inventory(["USGS_LPC_KS_SCentral_L4_2015_LAS_2017"])
        prepared = prepare_lidar(inventory, min_year=2015, overrides=overrides)
        self.assertEqual(prepared["year"].tolist(), [2015])

    def test_unresolved_collections_are_flagged_not_modern(self) -> None:
        inventory = build_inventory(["IA_FullState", "Survey_2021"])
        classified = classify_lidar_vintage(inventory)

        self.assertEqual(classified["year_source"].tolist(), ["unresolved", "text_year"])
        self.assertTrue(pd.isna(classified["year"].iloc[0]))
        self.assertEqual(prepare_lidar(inventory)["lidar_name"].tolist(), ["Survey_2021"])

    def test_override_file_keeps_latest_year_per_normalized_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overrides.csv"
            path.write_text(
                "collection_key,start_year\n"
                "USGS_LPC_PA_SandySupp_2016_LAS_2018,2016\n"
                "PA_SandySupp_2016,2014\n",
                encoding="utf-8",
            )
            self.assertEqual(load_vintage_overrides(path), {"pa_sandysupp_2016": 2016})


class Usgs3depIndexTest(unittest.TestCase):
    def test_work_units_use_collect_end_year_and_reviewed_overrides(self) -> None:
        ms = lambda text: pd.Timestamp(text, tz="UTC").value // 1_000_000  # noqa: E731
        index = gpd.GeoDataFrame(
            {
                "workunit": ["NC_Phase4_Cabarrus_2016", "IL_Boone_2018", "Old_2001"],
                "workunit_id": [1, 2, 3],
                "collect_start": [ms("2016-12-01"), ms("2011-03-01"), ms("2001-02-01")],
                "collect_end": [ms("2017-02-01"), ms("2011-04-01"), None],
                "lpc_link": ["a", "b", None],
            },
            geometry=[box(0, 0, 1, 1)] * 3,
            crs=TARGET_CRS,
        )
        classified = classify_lidar_vintage(
            usgs_3dep_as_inventory(index), overrides={"il_boone_2018": 2018}
        )

        self.assertEqual(classified["year"].tolist(), [2017, 2018, 2001])
        self.assertEqual(
            classified["year_source"].tolist(), ["usgs_3dep_index", "override", "usgs_3dep_index"]
        )
        self.assertEqual(classified["collection_key"].iloc[0], "nc_phase4_cabarrus_2016")


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
        self.assertEqual(all_results.loc[0, "lidar_batch_count"], 0)
        self.assertEqual(len(gap_results), 1)

    def test_aliases_of_one_collection_count_as_one_batch(self) -> None:
        lidar = build_lidar(
            box(0, 0, 5, 10),
            box(0, 0, 5, 10),
            box(5, 0, 10, 10),
            keys=["ca_plumasnf_b2_2018", "ca_plumasnf_b2_2018", "ca_other_2019"],
        )
        all_results, _ = compute_coverage(build_towns(), lidar)

        self.assertEqual(all_results.loc[0, "lidar_batch_count"], 2)
        self.assertEqual(all_results.loc[0, "coverage_pct"], 100.0)

    def test_overlapping_footprints_are_not_double_counted(self) -> None:
        lidar = build_lidar(box(0, 0, 6, 10), box(4, 0, 8, 10))
        all_results, _ = compute_coverage(build_towns(), lidar)

        self.assertEqual(all_results.loc[0, "covered_area_m2"], 80.0)
        self.assertEqual(all_results.loc[0, "gap_area_m2"], 20.0)


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
        self.assertNotIn("Data Source Notes", markdown)

    def test_state_program_note_is_reported_for_minnesota(self) -> None:
        towns = build_towns().assign(state="MN")
        all_results, gaps = compute_coverage(towns, build_lidar(box(0, 0, 10, 10)))
        summary = pd.DataFrame([summarize_state("MN", all_results, gaps)])

        batch_markdown = build_batch_markdown_summary(summary, threshold=5.0, min_year=2015)
        state_markdown = build_markdown_summary("MN", all_results, gaps, threshold=5.0)

        self.assertIn("Gen2", batch_markdown)
        self.assertIn("Data source note", state_markdown)


if __name__ == "__main__":
    unittest.main()
