from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from lidar_coverage import run
from lidar_coverage.cli import build_parser, resolve_options
from lidar_coverage.constants import REVIEWED_VINTAGE_OVERRIDES
from lidar_coverage.preprocess import load_vintage_overrides


def options(*argv: str):
    return resolve_options(build_parser().parse_args(list(argv)))


class DefaultsTest(unittest.TestCase):
    def test_reviewed_overrides_ship_with_package(self) -> None:
        self.assertTrue(REVIEWED_VINTAGE_OVERRIDES.exists())
        overrides = load_vintage_overrides(REVIEWED_VINTAGE_OVERRIDES)
        self.assertEqual(len(overrides), 62)
        self.assertEqual(overrides["ky_fullstate"], 2017)

    def test_cli_defaults_use_reviewed_overrides_and_latest_inventory(self) -> None:
        resolved = options("--state", "RI")
        self.assertEqual(resolved.vintage_overrides, REVIEWED_VINTAGE_OVERRIDES)
        self.assertTrue(resolved.refresh_inventory)
        self.assertFalse(resolved.supplement_3dep_index)

    def test_cli_can_disable_overrides_and_go_offline(self) -> None:
        resolved = options("--state", "RI", "--no-vintage-overrides", "--offline")
        self.assertIsNone(resolved.vintage_overrides)
        self.assertFalse(resolved.refresh_inventory)

    def test_run_builds_options_for_python_callers(self) -> None:
        with mock.patch("lidar_coverage.pipeline.run_pipeline", return_value="summary") as pipeline:
            self.assertEqual(run("conus", output_dir="out", offline=True), "summary")
        built = pipeline.call_args.args[0]
        self.assertEqual(len(built.states), 49)
        self.assertEqual(built.output_dir, Path("out"))
        self.assertFalse(built.refresh_inventory)
        self.assertEqual(built.vintage_overrides, REVIEWED_VINTAGE_OVERRIDES)


if __name__ == "__main__":
    unittest.main()
