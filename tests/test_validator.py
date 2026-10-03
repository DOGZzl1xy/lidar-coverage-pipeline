from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from lidar_coverage.analysis import compute_coverage
from lidar_coverage.constants import TARGET_CRS
from lidar_coverage.pipeline import _write_state_outputs, analysis_fingerprint
from lidar_coverage.reporting import (
    BATCH_COLUMNS,
    MANIFEST_NAME,
    UNRESOLVED_COLUMNS,
    UNRESOLVED_NAME,
    state_output_paths,
    summarize_state,
    write_csv,
    write_json,
    write_markdown,
)
from lidar_coverage.validation import validate_outputs

THRESHOLD = 5.0


def write_fixture(output_dir: Path) -> None:
    towns = gpd.GeoDataFrame(
        {
            "GEOID": ["4400100001", "4400100002", "4400100003"],
            "town_name": ["Covered town", "Gap town", "Partial town"],
            "state": ["RI"] * 3,
            "base_area_m2": [100.0, 100.0, 100.0],
        },
        geometry=[box(0, 0, 10, 10), box(20, 0, 30, 10), box(40, 0, 50, 10)],
        crs=TARGET_CRS,
    )
    lidar = gpd.GeoDataFrame(
        {"collection_key": ["ri_a_2021", "ri_b_2019"], "year": [2021, 2019]},
        geometry=[box(0, 0, 10, 10), box(40, 0, 40.3, 10)],
        crs=TARGET_CRS,
    )
    all_results, gaps = compute_coverage(towns, lidar, coverage_threshold=THRESHOLD)
    paths = state_output_paths(output_dir, "RI")
    _write_state_outputs("RI", all_results, gaps, paths=paths, threshold=THRESHOLD)
    batch = pd.DataFrame([summarize_state("RI", all_results, gaps)], columns=BATCH_COLUMNS)
    write_csv(batch, output_dir / "batch_summary.csv")
    write_markdown("# batch\n", output_dir / "batch_summary.md")
    write_csv(pd.DataFrame(columns=UNRESOLVED_COLUMNS), output_dir / UNRESOLVED_NAME)
    write_json(
        {"parameters": {"states": ["RI"], "coverage_threshold": THRESHOLD, "min_year": 2015}},
        output_dir / MANIFEST_NAME,
    )


class ValidatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.output_dir = Path(self._directory.name)
        write_fixture(self.output_dir)
        self.paths = state_output_paths(self.output_dir, "RI")

    def tearDown(self) -> None:
        self._directory.cleanup()

    def assertFailsWith(self, fragment: str, **kwargs) -> None:
        errors = validate_outputs(self.output_dir, **kwargs)
        self.assertTrue(any(fragment in error for error in errors), errors)

    def test_untampered_outputs_pass_using_manifest_parameters(self) -> None:
        self.assertEqual(validate_outputs(self.output_dir), [])

    def test_omitted_gap_row_with_adjusted_batch_count_fails(self) -> None:
        gaps = pd.read_csv(self.paths["gap_csv"], dtype={"GEOID": str})
        self.assertEqual(len(gaps), 2)
        gaps.iloc[:1].to_csv(self.paths["gap_csv"], index=False)
        batch = pd.read_csv(self.output_dir / "batch_summary.csv")
        batch["county_subdivisions_below_threshold"] = 1
        batch.to_csv(self.output_dir / "batch_summary.csv", index=False)

        self.assertFailsWith("below-threshold rows missing")

    def test_empty_geojson_feature_collection_fails(self) -> None:
        self.paths["all_geojson"].write_text(
            json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8"
        )
        self.assertFailsWith("features do not match")

    def test_threshold_different_from_run_fails(self) -> None:
        self.assertFailsWith("differs from the run threshold", coverage_threshold=50.0)

    def test_geojson_numeric_tampering_fails(self) -> None:
        content = json.loads(self.paths["all_geojson"].read_text(encoding="utf-8"))
        content["features"][0]["properties"]["coverage_pct"] = 42.0
        self.paths["all_geojson"].write_text(json.dumps(content), encoding="utf-8")
        self.assertFailsWith("coverage_pct differs")

    def test_batch_statistics_must_match_csv(self) -> None:
        batch = pd.read_csv(self.output_dir / "batch_summary.csv")
        batch["mean_coverage_pct"] = 99.0
        batch.to_csv(self.output_dir / "batch_summary.csv", index=False)
        self.assertFailsWith("mean_coverage_pct")

    def test_missing_manifest_fails(self) -> None:
        (self.output_dir / MANIFEST_NAME).unlink()
        self.assertFailsWith(MANIFEST_NAME, states=["RI"], coverage_threshold=THRESHOLD)

    def test_incomplete_run_fails(self) -> None:
        manifest = json.loads((self.output_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
        manifest["status"] = "running"
        write_json(manifest, self.output_dir / MANIFEST_NAME)
        self.assertFailsWith("not 'complete'")


class FingerprintTest(unittest.TestCase):
    def manifest(self, **parameters) -> dict:
        base = {"min_year": 2015, "coverage_threshold": 5.0, "tiger_year": 2024}
        base.update(parameters)
        return {
            "package_version": "0.2.0",
            "parameters": base,
            "inputs": {"lidar_inventory": {"sha256": "abc"}, "vintage_overrides": None},
        }

    def test_identical_settings_match(self) -> None:
        self.assertEqual(
            analysis_fingerprint(self.manifest()), analysis_fingerprint(self.manifest())
        )

    def test_changed_threshold_or_year_prevents_reuse(self) -> None:
        base = analysis_fingerprint(self.manifest())
        self.assertNotEqual(base, analysis_fingerprint(self.manifest(coverage_threshold=10.0)))
        self.assertNotEqual(base, analysis_fingerprint(self.manifest(min_year=2019)))


if __name__ == "__main__":
    unittest.main()
