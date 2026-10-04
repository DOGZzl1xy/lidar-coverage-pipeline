# Specification

Stable analysis and output contract for `lidar-coverage`. Results, review
records and open items live in `Progress.md`.

## Scope

- Units: Census TIGER/Line COUSUB features, one file per state, TIGER 2024.
  Features with `COUSUBFP = 00000` ("County subdivisions not defined") are
  excluded. Multi-part features are dissolved by `GEOID`.
- National scope: `CONUS` = 48 contiguous states plus DC (49 codes; no AK, HI
  or territories).
- Inputs are footprints and metadata only. The analysis never downloads point
  clouds; `scripts/sample_ept_acquisition_dates.py` may sample small EPT nodes
  for vintage verification.

## Footprints

- Default: `hobuinc/usgs-lidar` `boundaries/resources.geojson`, downloaded on
  every run unless `--offline`.
- Optional (`supplement_3dep_index`): USGS 3DEP Elevation Index work units
  (MapServer/8), geometry generalized to 0.0005 degrees, attributes only.

## Vintage

- Every record gets a `collection_key`: the name without a `USGS_LPC_` prefix
  or trailing `_LAS_YYYY`, lower-cased, non-alphanumeric runs collapsed to `_`.
- A collection's vintage is its latest acquisition year; collections spanning
  `min_year` count as modern.
- Priority: (1) override table (`collection_key,start_year[,end_year]`, latest
  year wins; the reviewed table in `src/lidar_coverage/data/` is the default);
  (2) a `year` field in the source (`collect_end` year for 3DEP work units);
  (3) the last four-digit year in the name or URL after removing `_LAS_YYYY`;
  (4) a USGS suffix `_[A-D]YY` meaning `20YY`.
- Records without a vintage are excluded and listed in
  `unresolved_collections.csv`.
- Modern means vintage ≥ `min_year` (default 2015).

## Analysis

- Repair geometries (polygonal parts only) and compute areas in EPSG:5070,
  with optional online PROJ grids disabled for repeatable results.
- Covered area is the union of intersecting modern footprints.
- Per record: `base_area_m2`, `covered_area_m2`, `gap_area_m2 ≥ 0`,
  `coverage_pct` in 0–100 (2 decimals), `lidar_batch_count` (distinct
  `collection_key`s), `data_vintage_note`.
- A gap is `coverage_pct < coverage_threshold` (default 5.0).

## Outputs

In the output directory, with `<st>` the lower-case state code:

- `<st>_cousub_coverage_all.csv|.geojson`,
  `<st>_cousub_coverage_under_threshold.csv|.geojson`, `<st>_coverage_summary.md`
- `batch_summary.csv|.md`, `unresolved_collections.csv`
- `run_manifest.json`: `status` (`running`/`complete`), package version,
  timestamps, parameters, and URL, path, size, SHA-256 and cache time of every
  input.

CSV and GeoJSON (WGS84) share the fields `GEOID`, `town_name`, `state`,
`base_area_m2`, `covered_area_m2`, `gap_area_m2`, `coverage_pct`,
`lidar_batch_count`, `data_vintage_note`. MN and KY summaries note state LiDAR
programs missing from the sources (`STATE_PROGRAM_NOTES`).

`--skip-existing` reuses a state's files only when the previous manifest has
the same package version, `min_year`, threshold, TIGER year and input hashes.

## Validation

`lidar-coverage-validate DIR` reads the run parameters from the manifest and
fails unless: the run is complete; all files exist; values are in range;
`GEOID`s are unique; the gap file equals exactly the records below the
threshold; CSV and GeoJSON have the same GEOIDs and key values; batch counts
and statistics match the state files. A requested threshold that differs from
the run's is an error.

## Repository

- Package in `src/lidar_coverage/`, maintainer scripts in `scripts/`, tests in
  `tests/`, report page in `docs/`. Managed with uv (`uv.lock` committed).
- `data/cache/` and `outputs*/` are generated and never committed.
