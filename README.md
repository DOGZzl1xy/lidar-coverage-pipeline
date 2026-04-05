# LiDAR Coverage Gap Analysis

This project packages the county-subdivision LiDAR gap pipeline as a reusable Python project. It downloads U.S. Census `COUSUB` boundaries, intersects them with the public `hobuinc/usgs-lidar` inventory, and reports places where modern LiDAR coverage falls below a configurable threshold.

## Features

- Downloads Census `COUSUB` boundaries from TIGER/Line for any state in the 50 states plus DC.
- Downloads the USGS LiDAR metadata index from `hobuinc/usgs-lidar`.
- Repairs and reprojects both datasets into `EPSG:5070`.
- Intersects Rhode Island county subdivisions with valid 2015+ LiDAR footprints.
- Calculates base area, covered area, gap area, and coverage percentage.
- Exports both a full coverage table and a below-threshold gap list.

## Installation

With `uv`:

```bash
uv sync
```

With `pip`:

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -e .
```

## Usage

Run the default Rhode Island example:

```bash
lidar-coverage --state RI
```

Run another state with a custom threshold and output directory:

```bash
lidar-coverage --state MA --coverage-threshold 5 --output-dir outputs_ma
```

## Project Layout

```text
src/lidar_coverage/
  analysis.py
  cli.py
  constants.py
  io.py
  preprocess.py
  reporting.py
scripts/
  validate_ri_sample.py
tests/
  test_pipeline.py
```

## Outputs

- `outputs/ri_cousub_coverage_all.csv`
- `outputs/ri_cousub_coverage_under_threshold.csv`
- `outputs/ri_coverage_summary.md`

## Rhode Island Test Snapshot

The current Rhode Island test run produced:

- `40` county subdivisions analyzed
- `14` county subdivisions below the `5%` threshold
- independent validation across all `40` Rhode Island county subdivisions with `0` coverage mismatches against a second calculation path

The gap list includes the requested fields plus audit-friendly extras:

- `Town Name`
- `State`
- `GEOID`
- `Base Area (m2)`
- `Covered Area (m2)`
- `Gap Area (m2)`
- `Current Coverage %`
- `LiDAR Batch Count`
- `Data Vintage Note`

## Data Sources

- Census TIGER/Line county subdivisions
- `hobuinc/usgs-lidar` `boundaries/resources.geojson`

## Validation

- `scripts/validate_ri_sample.py` cross-checks representative Rhode Island towns with an independent area calculation.
- A full Rhode Island second-pass recomputation also matched the main pipeline with `0` mismatches.

## Development

Run the lightweight unit tests:

```bash
python -m unittest discover -s tests
```

## Notes

- The current implementation uses `GEOID` as the county subdivision FIPS identifier.
- Coverage gaps are defined as records where `coverage_pct < 5.0` by default.
- The LiDAR inventory stores vintage information in collection names, so the parser extracts years from the collection metadata when explicit year fields are absent.
