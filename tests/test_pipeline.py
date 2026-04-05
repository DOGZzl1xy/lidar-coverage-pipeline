from __future__ import annotations

import unittest

from lidar_coverage.analysis import build_vintage_note
from lidar_coverage.preprocess import extract_year_from_text


class PipelineHelpersTest(unittest.TestCase):
    def test_extract_year_from_collection_name(self) -> None:
        self.assertEqual(extract_year_from_text("MA_CentralEastern_2_2021"), 2021)

    def test_extract_year_from_missing_text(self) -> None:
        self.assertIsNone(extract_year_from_text("collection_without_year"))

    def test_build_vintage_note_single_year(self) -> None:
        self.assertEqual(build_vintage_note([2021]), "Intersecting LiDAR year: 2021")

    def test_build_vintage_note_multiple_years(self) -> None:
        self.assertEqual(
            build_vintage_note([2021, 2018, 2021, 2015]),
            "Intersecting LiDAR years: 2015-2021 (2015, 2018, 2021)",
        )


if __name__ == "__main__":
    unittest.main()
