# LiDAR Coverage Gap Analysis

This project identifies U.S. Census county subdivisions with missing or
outdated LiDAR coverage. It is designed for repeatable state-level analysis,
including multi-state batches, rather than a Rhode Island-only demonstration.

The planned national expansion scope is the contiguous 48 states plus the
District of Columbia (`CONUS + DC`). Current implementation progress,
validation results, and tracked readiness work are maintained in
[`Progress.md`](Progress.md).

## Goal

For each county subdivision, the pipeline measures how much of its area is
covered by modern LiDAR inventory footprints. A record is reported as a gap
when its modern coverage is below a configurable threshold.

Defaults:

- Modern LiDAR vintage: `2015` or newer
- Gap threshold: coverage below `5.0%`
- Analysis projection: `EPSG:5070` for area calculations

The preprocessing step disables optional online PROJ transformation grids so
that cached source files produce the same coverage results with or without
network access.

## Data Sources

- **Boundaries:** U.S. Census TIGER/Line `COUSUB` files, downloaded per state.
- **LiDAR inventory:** `hobuinc/usgs-lidar` `boundaries/resources.geojson`.

The LiDAR source is a footprint metadata inventory. This workflow does not
download LiDAR point clouds.

## Installation

Python `3.12` or later is required. From the repository root:

```bash
python -m pip install -e .
```

Downloads are cached under `data/cache/` when the pipeline first runs.

## Single-State Run

The original Rhode Island CLI remains supported:

```bash
lidar-coverage --state RI
```

Run another state or change the gap threshold:

```bash
lidar-coverage --state MA --coverage-threshold 10 --output-dir outputs
```

## Multi-State Run

Run the required six-state batch:

```bash
lidar-coverage --states RI MA PA CA TX FL --coverage-threshold 5 --output-dir outputs
```

`--state` and `--states` are mutually exclusive. Without either argument, the
pipeline defaults to `RI`.

## Configuration

[`configs/default.yaml`](configs/default.yaml) contains a reproducible
six-state configuration. Run it with:

```bash
lidar-coverage --config configs/default.yaml
```

CLI options override matching YAML values:

```bash
lidar-coverage --config configs/default.yaml --states RI MA --output-dir outputs_small
```

Configuration keys are `states` (or `state`), `min_year`,
`coverage_threshold`, `cache_dir`, and `output_dir`.

## Outputs

For each processed state, `<state>` is the lower-case abbreviation:

| File | Content |
| --- | --- |
| `<state>_cousub_coverage_all.csv` | One record per county subdivision |
| `<state>_cousub_coverage_under_threshold.csv` | Only reported coverage gaps |
| `<state>_cousub_coverage_all.geojson` | Full spatial results in WGS84 |
| `<state>_cousub_coverage_under_threshold.geojson` | Spatial gap results in WGS84 |
| `<state>_coverage_summary.md` | Human-readable state summary |
| `batch_summary.csv` | One aggregate row per requested state |
| `batch_summary.md` | Human-readable batch summary |

Per-state CSV and GeoJSON properties:

| Field | Meaning |
| --- | --- |
| `GEOID` | Census county subdivision identifier |
| `town_name` | Census feature name |
| `state` | Two-letter state abbreviation |
| `base_area_m2` | Total feature area in square meters |
| `covered_area_m2` | Area covered by unioned modern LiDAR footprints |
| `gap_area_m2` | Non-negative uncovered area |
| `coverage_pct` | Modern coverage percent, bounded to `0-100` |
| `lidar_batch_count` | Number of intersecting modern collections |
| `data_vintage_note` | Intersecting collection year summary |

Batch summaries contain feature and below-threshold counts plus mean, minimum,
and maximum coverage percentage for each state.

## Validation

Run unit tests:

```bash
python -m unittest discover -s tests
```

After producing a multi-state output directory, check required artifacts and
numeric invariants:

```bash
python scripts/validate_outputs.py --output-dir outputs --states RI MA PA CA TX FL --coverage-threshold 5
```

The validation script confirms that each requested state's CSV, GeoJSON, and
Markdown files exist; that the batch summary contains all requested states;
that `coverage_pct` is within `0-100`; that `gap_area_m2` is non-negative;
that `GEOID` values are unique in both all and under-threshold CSVs; and that
every under-threshold row has `coverage_pct` below the given threshold.

The earlier Rhode Island independent spot-check utility remains available once
RI source data has been cached:

```bash
python scripts/validate_ri_sample.py
```

## Project Layout

```text
configs/default.yaml       Six-state configuration example
scripts/validate_outputs.py
scripts/validate_ri_sample.py
src/lidar_coverage/        Package implementation and CLI
tests/test_pipeline.py     Unit tests with synthetic geometries
agent.md                   Implementation checklist
SPEC.md                    Analysis and output contract
Progress.md                Validation status and CONUS readiness work
```

## Project Status

The six-state workflow is the current validated baseline. See
[`Progress.md`](Progress.md) for validation evidence, external quality checks,
recorded decisions, and the readiness work required before a complete
`CONUS + DC` analysis.
