# LiDAR Coverage Pipeline Specification

## Objective

Identify U.S. Census county subdivisions (including towns where represented
by COUSUB features) with no modern LiDAR coverage or with modern coverage
below a configurable percentage threshold. The workflow must generalize
beyond a Rhode Island demonstration and support repeatable state batches.

The planned national expansion scope is the contiguous 48 states plus the
District of Columbia (`CONUS + DC`). Implementation status, validation
evidence, recorded decisions, and readiness work are maintained in
`Progress.md`.

## Data Sources And Scope

- Administrative boundaries: Census TIGER/Line `COUSUB` ZIP files, one file
  per state, using the project's configured TIGER release year.
- LiDAR inventory: `hobuinc/usgs-lidar` `boundaries/resources.geojson`.
- "Modern" LiDAR means a footprint with an extracted vintage year greater
  than or equal to `min_year`, defaulting to `2015`.
- The current text-based vintage extraction uses the following priority:
  1. Four-digit acquisition year embedded in the collection name or URL (regex
     `(?:19|20)\d{2}`). Tokens matching `_LAS_YYYY` are stripped first so that
     LAS processing years are not confused with acquisition years. When
     multiple four-digit years remain, the last match is used. A four-digit
     year found in either the name or the URL takes precedence over a suffix.
  2. USGS batch/delivery suffix (`_B23`, `_D22`, `_A23`, `_C23`) where the
     letter indicates Batch, Delivery, Acquisition, or Collection and the two
     digits map to `2000 + digits`.
  Collections matching neither pattern (e.g. `IA_FullState`) are excluded
  because their vintage cannot be determined.
- The inventory contains coverage footprints and metadata only. This pipeline
  must never download actual LiDAR point-cloud data.
- The current baseline validation batch is `RI`, `MA`, `PA`, `CA`, `TX`, and
  `FL`. Consult `Progress.md` before scheduling a complete `CONUS + DC` run.

## Analysis Contract

- Perform area operations in `EPSG:5070`.
- Disable optional online PROJ transformation grids during preprocessing so
  the same cached inputs produce the same result in offline and online runs.
- Repair invalid input geometries before projection and intersection.
- Dissolve multi-part COUSUB geometries by `GEOID` so that each county
  subdivision contributes exactly one row to the output.
- Use the union of intersecting modern LiDAR footprints so overlapping
  footprints are not double-counted.
- For each COUSUB calculate:
  `base_area_m2`, `covered_area_m2`, `gap_area_m2`, `coverage_pct`,
  `lidar_batch_count`, and `data_vintage_note`.
- `gap_area_m2` must be non-negative and `coverage_pct` must be bounded from
  `0` through `100`.
- A gap record satisfies `coverage_pct < coverage_threshold`; the default
  threshold is `5.0`.
- When no modern LiDAR intersects a state, all its COUSUB features have zero
  coverage and remain valid output records.

## CLI And Configuration Contract

- Keep `lidar-coverage --state RI` working.
- Add batch execution such as:

  ```bash
  lidar-coverage --states RI MA PA CA TX FL --coverage-threshold 5 --output-dir outputs
  ```

- `--state` and `--states` are mutually exclusive; if neither is supplied,
  process `RI` for backward-compatible default behavior.
- Support YAML configuration through `--config`, with command-line options
  overriding configuration values.
- Supply `configs/default.yaml` documenting normal defaults and the six-state
  example batch.

## Output Contract

Output files are written directly within the selected output directory and
use lower-case state prefixes:

- `<state>_cousub_coverage_all.csv`
- `<state>_cousub_coverage_under_threshold.csv`
- `<state>_cousub_coverage_all.geojson`
- `<state>_cousub_coverage_under_threshold.geojson`
- `<state>_coverage_summary.md`
- `batch_summary.csv`
- `batch_summary.md`

State CSV files use stable snake-case field names suitable for validation:
`GEOID`, `town_name`, `state`, `base_area_m2`, `covered_area_m2`,
`gap_area_m2`, `coverage_pct`, `lidar_batch_count`, and
`data_vintage_note`. GeoJSON files contain equivalent properties and
geometries.

Batch summaries include one row per requested state with feature count,
below-threshold count, and coverage summary statistics. Output validation
must confirm: required artifacts exist; `coverage_pct` lies within
`0` to `100`; `gap_area_m2` is non-negative; `GEOID` values are unique
in each state CSV; and every row in `under_threshold.csv` has
`coverage_pct < coverage_threshold`.

## Repository Conventions

- Python package code resides in `src/lidar_coverage/`; executable helpers
  reside in `scripts/`; tests reside in `tests/`.
- Generated input downloads live under `data/cache/`; generated reports live
  under `outputs/`. Both must remain ignored by Git.
- Source, scripts, tests, configuration, documentation, and small fixtures
  may be committed. Large downloaded or generated data must not be committed.
- Update `Progress.md` for validation results, external audits, recorded
  decisions, and unresolved work required for `CONUS + DC` expansion.
