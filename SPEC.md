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
- Optional supplement (`supplement_3dep_index`): official USGS 3DEP Elevation
  Index work units (MapServer/8), fetched with geometry generalized to
  0.0005 degrees; vintage is the `collect_end` year (fallback
  `collect_start`), `year_source = usgs_3dep_index`; reviewed overrides apply
  by `collection_key`. Records sharing a key with the inventory are counted
  once in `lidar_batch_count`.
- "Modern" LiDAR means a footprint with a vintage year greater than or equal
  to `min_year`, defaulting to `2015`.
- Each inventory record receives a `collection_key`: the name with any
  `USGS_LPC_` prefix and trailing `_LAS_YYYY` token removed, lower-cased, with
  non-alphanumeric runs collapsed to `_`. Aliases of one collection share a key.
- A collection's vintage is its latest acquisition year, so collections
  spanning `min_year` count as modern.
- Vintage priority: (a) an authoritative override CSV
  (`collection_key,start_year[,end_year]`; the latest year is used), (b) a `year`
  column already present in the inventory, (c) text extraction below. The
  chosen source is recorded as `year_source`.
- The text-based vintage extraction uses the following priority:
  1. Four-digit acquisition year embedded in the collection name or URL (regex
     `(?:19|20)\d{2}`). Tokens matching `_LAS_YYYY` are stripped first so that
     LAS processing years are not confused with acquisition years. When
     multiple four-digit years remain, the last match is used. A four-digit
     year found in either the name or the URL takes precedence over a suffix.
  2. USGS batch/delivery suffix (`_B23`, `_D22`, `_A23`, `_C23`) where the
     letter indicates Batch, Delivery, Acquisition, or Collection and the two
     digits map to `2000 + digits`.
  Collections matching neither pattern (e.g. `IA_FullState`) are excluded
  because their vintage cannot be determined, and are listed in
  `unresolved_collections.csv` for review.
- The inventory contains coverage footprints and metadata only. The analysis
  pipeline must never download LiDAR point-cloud data. The separate
  verification script may sample small EPT nodes to read acquisition GPS
  times, only with the user's approval.
- `CONUS` denotes the 48 contiguous states plus DC (49 codes; excludes AK, HI,
  and territories). Consult `Progress.md` for the status of CONUS results.

## Analysis Contract

- Perform area operations in `EPSG:5070`.
- Disable optional online PROJ transformation grids during preprocessing so
  the same cached inputs produce the same result in offline and online runs.
- Repair invalid input geometries before projection and intersection, keeping
  only polygonal parts.
- Exclude TIGER placeholder features with `COUSUBFP = 00000` ("County
  subdivisions not defined", mostly water areas); they are not towns.
- Dissolve multi-part COUSUB geometries by `GEOID` so that each county
  subdivision contributes exactly one row to the output.
- Use the union of intersecting modern LiDAR footprints so overlapping
  footprints are not double-counted.
- For each COUSUB calculate:
  `base_area_m2`, `covered_area_m2`, `gap_area_m2`, `coverage_pct`,
  `lidar_batch_count` (distinct `collection_key` values), and
  `data_vintage_note`.
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
  process `RI` for backward-compatible default behavior. The group name
  `CONUS` expands to the 49 CONUS codes.
- Support YAML configuration through `--config`, with command-line options
  overriding configuration values. Keys: `state`/`states`, `min_year`,
  `coverage_threshold`, `cache_dir`, `output_dir`, `vintage_overrides`,
  `refresh_cache`, `refresh_inventory`, `supplement_3dep_index`,
  `skip_existing`.
- `configs/default.yaml` holds the six-state validation batch and
  `configs/conus.yaml` the national run.
- `--preflight` performs metadata-only checks (TIGER URL availability,
  inventory vintage statistics) and never runs spatial analysis.
- Cached downloads are written atomically; `--refresh-inventory` re-downloads
  only the LiDAR inventory (enabled in the shipped configs); `--refresh-cache`
  forces a re-download of everything and `--skip-existing` reuses complete per-state outputs only
  when the existing manifest was produced with identical analysis settings
  and inputs.

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
- `unresolved_collections.csv` (`id`, `lidar_name`, `collection_key`, `url`)
- `run_manifest.json`: run `status` (`running`/`complete`), package version, start/finish timestamps, all run
  parameters (including TIGER year), the vintage policy, and for every input
  its URL, local path, byte size, SHA-256, and cache timestamp, plus inventory
  classification statistics.

State and batch Markdown summaries include a data-source note for states whose
newer state-run LiDAR programs are absent from the inventory (currently MN and
KY; `STATE_PROGRAM_NOTES`).

State CSV files use stable snake-case field names suitable for validation:
`GEOID`, `town_name`, `state`, `base_area_m2`, `covered_area_m2`,
`gap_area_m2`, `coverage_pct`, `lidar_batch_count`, and
`data_vintage_note`. GeoJSON files contain equivalent properties and
geometries.

Batch summaries include one row per requested state with feature count,
below-threshold count, and mean/min/max coverage. Output validation reads the
run parameters from `run_manifest.json` and must confirm: required artifacts
exist; `coverage_pct` lies within `0` to `100`; `gap_area_m2` is non-negative;
`GEOID` values are unique; the under-threshold set equals exactly the records
in `all.csv` with `coverage_pct < coverage_threshold`; CSV and GeoJSON contain
the same GEOIDs with matching key numeric values; batch counts and statistics
match the state files; and a requested threshold differing from the recorded
run threshold is an error.

## Repository Conventions

- Python package code resides in `src/lidar_coverage/`; executable helpers
  reside in `scripts/`; tests reside in `tests/`. Dependencies are managed with
  `uv` (`pyproject.toml` + committed `uv.lock`).
- Generated input downloads live under `data/cache/`; generated reports live
  under `outputs*/`. Both must remain ignored by Git.
- Source, scripts, tests, configuration, documentation, and small fixtures
  may be committed. Large downloaded or generated data must not be committed.
- Update `Progress.md` for validation results, external audits, recorded
  decisions, and unresolved work required for `CONUS + DC` expansion.
