# LiDAR Coverage Gap Analysis

Identifies U.S. Census county subdivisions (COUSUB) with no modern LiDAR
coverage, or with modern coverage below a configurable threshold. It runs for
one state, a list of states, or the contiguous 48 states plus DC (`CONUS`).

Latest results: [CONUS LiDAR gap report](https://dogzzl1xy.github.io/lidar-coverage-pipeline/)
(source: `docs/index.html`).

Current status, validation evidence, and open work are tracked in
[`Progress.md`](Progress.md); the stable analysis and output contract is in
[`SPEC.md`](SPEC.md).

## Defaults

- Modern LiDAR: vintage `2015` or newer
- Gap: coverage below `5.0%`
- Area calculations in `EPSG:5070`, with optional online PROJ grids disabled so
  cached inputs give identical results offline and online

## Data Sources

- **Boundaries:** Census TIGER/Line 2024 `COUSUB` ZIP files, one per state.
- **LiDAR inventory:** `hobuinc/usgs-lidar` `boundaries/resources.geojson`
  (footprints and metadata only; the analysis never downloads point clouds).
- **Optional footprint supplement:** USGS 3DEP Elevation Index work units
  (generalized ~50 m; attributes and footprints only).
- **Optional authoritative vintages:** USGS 3DEP Elevation Index work-unit
  attributes, see [Vintage overrides](#vintage-overrides).

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+:

```bash
uv sync
```

Source files are downloaded to `data/cache/` on first use. Downloads are
atomic, so an interrupted transfer is never reused; `--refresh-cache` forces a
fresh download.

## Running

Single state (default `RI` when no state is given):

```bash
uv run lidar-coverage --state RI
```

State list:

```bash
uv run lidar-coverage --states RI MA PA CA TX FL --coverage-threshold 5 --output-dir outputs_six_state
```

Full CONUS + DC with the reviewed vintage overrides (about 2 minutes once
inputs are cached; ~1 GB of outputs):

```bash
uv run lidar-coverage --config configs/conus.yaml
```

Add the official USGS 3DEP work-unit footprints, which include collections not
yet converted to EPT and therefore missing from the hobuinc inventory:

```bash
uv run lidar-coverage --config configs/conus_with_3dep.yaml
```

Metadata-only preflight. It checks every TIGER URL and summarizes the inventory
vintage classification without running any spatial analysis:

```bash
uv run lidar-coverage --states CONUS --preflight
```

### Options

| Option / YAML key | Meaning |
| --- | --- |
| `--state`, `--states` / `state`, `states` | State codes; `CONUS` expands to 48 states + DC |
| `--config` | YAML file; CLI options override it |
| `--min-year` / `min_year` | Minimum modern vintage (default `2015`) |
| `--coverage-threshold` / `coverage_threshold` | Gap threshold percent (default `5.0`) |
| `--vintage-overrides` / `vintage_overrides` | Authoritative `collection_key,start_year` CSV |
| `--cache-dir`, `--output-dir` | Default `data/cache`, `outputs` |
| `--refresh-cache` / `refresh_cache` | Re-download all cached sources |
| `--supplement-3dep-index` / `supplement_3dep_index` | Also use official USGS 3DEP work-unit footprints (vintage = collect end year) |
| `--refresh-inventory` / `refresh_inventory` | Re-download only the LiDAR inventory (on in both configs, so runs use the latest upstream version) |
| `--skip-existing` / `skip_existing` | Reuse per-state outputs already written (resume) |
| `--preflight` | Metadata checks only, then exit |

Configurations: [`configs/default.yaml`](configs/default.yaml) (six-state
validation batch) and [`configs/conus.yaml`](configs/conus.yaml).

## Outputs

`<st>` is the lower-case state code.

| File | Content |
| --- | --- |
| `<st>_cousub_coverage_all.csv` / `.geojson` | One record per county subdivision |
| `<st>_cousub_coverage_under_threshold.csv` / `.geojson` | Gap records only |
| `<st>_coverage_summary.md` | State summary |
| `batch_summary.csv` / `.md` | One row per state plus totals |
| `unresolved_collections.csv` | Inventory collections whose vintage could not be determined (excluded) |
| `run_manifest.json` | Parameters, package version, timestamps, input URLs, sizes and SHA-256 hashes |

MN and KY summaries note that newer state-run LiDAR programs (Minnesota
Gen2, KyFromAbove Phases 2–3) are not fully in the USGS inventory.

Record fields: `GEOID`, `town_name`, `state`, `base_area_m2`,
`covered_area_m2`, `gap_area_m2`, `coverage_pct` (0–100),
`lidar_batch_count` (distinct collections after alias merging), and
`data_vintage_note`. GeoJSON is in WGS84.

## Vintage Overrides

A collection's vintage is its latest acquisition year, so collections spanning
2015 count as modern. Without overrides, the vintage comes from the collection
name or URL (see `SPEC.md`). To use
official USGS acquisition start years instead, fetch the 3DEP work-unit
attributes (no geometry, no point clouds) and pass the CSV:

```bash
uv run python scripts/fetch_usgs_workunits.py --output data/reference/usgs_workunit_vintage.csv
```

```bash
uv run lidar-coverage --states CONUS --vintage-overrides data/reference/usgs_workunit_vintage.csv
```

The raw official snapshot is kept at `data/reference/usgs_workunit_vintage.csv`.
`data/reference/vintage_overrides_reviewed.csv` holds the reviewed decisions,
with evidence for each row, and `configs/conus.yaml` uses it. Apply the raw
official table wholesale only after review; see `Progress.md`.

To check when a collection was actually flown, sample GPS times from a few
coarse EPT nodes (about 5-65 MB per collection; verification only, needs the
`verify` group):

```bash
uv run --group verify python scripts/sample_ept_acquisition_dates.py KY_FullState --nodes 48
```

## Validation

```bash
uv run ruff check src scripts tests
uv run python -m unittest discover -s tests
uv run python scripts/validate_outputs.py --output-dir outputs
```

The validator reads the states and threshold from `run_manifest.json`. It
checks that every artifact exists; that values are in range; that `GEOID`s are
unique; that the gap file contains exactly the records below the threshold;
that CSV and GeoJSON rows and key values match; and that batch counts and
statistics agree with the state files. A `--coverage-threshold` that differs
from the recorded run value is reported as an error.

## Project Layout

```text
configs/                     default.yaml (six states), conus.yaml, conus_with_3dep.yaml
scripts/validate_outputs.py  Output validator CLI
scripts/fetch_usgs_workunits.py  Official 3DEP vintage override builder
scripts/sample_ept_acquisition_dates.py  Point GPS-time vintage verification
data/reference/              Official vintage snapshot and reviewed overrides
src/lidar_coverage/
  cli.py          Argument and configuration handling
  pipeline.py     Batch orchestration, manifest, preflight
  preprocess.py   Geometry repair, COUSUB dissolve, vintage classification
  analysis.py     Coverage computation
  reporting.py    CSV / GeoJSON / Markdown writers
  validation.py   Strict output checks
  io.py           Cached atomic downloads and provenance hashing
tests/            Unit, validator, and cached-data RI integration tests
SPEC.md  Progress.md  agent.md
```
