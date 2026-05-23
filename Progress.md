# Project Progress And CONUS Readiness

This document is the single location for implementation status, validation
results, external quality checks, and work still required before a full CONUS
analysis. Update this file when readiness findings or completion status change;
keep `README.md`, `agent.md`, and `SPEC.md` focused on usage, working rules, and
stable contracts.

## Target Expansion Scope

- Target national scope: the contiguous 48 states plus the District of Columbia
  (`CONUS + DC`).
- Excluded from the planned national run: Alaska, Hawaii, Puerto Rico, and
  other U.S. territories.
- Current validation batch: `RI`, `MA`, `PA`, `CA`, `TX`, and `FL`. These
  states exercise the multi-state workflow but are not sufficient evidence for
  full CONUS readiness.
- No analysis run may download LiDAR point clouds. Footprint and metadata inputs
  only are permitted.

## Completed Implementation

- Standardized project configuration and Ruff formatting configuration.
- Preserved `lidar-coverage --state RI`.
- Added multi-state CLI execution and YAML configuration support.
- Added per-state CSV, GeoJSON, and Markdown outputs.
- Added batch summary CSV and Markdown outputs.
- Added unit tests for parsing, filtering, coverage ranges, empty LiDAR input,
  and batch reporting.
- Added `scripts/validate_outputs.py` for output artifact checks.
- Added conservative parsing behavior for `_LAS_YYYY` processing tokens and
  USGS suffix-style years.
- Dissolved multi-part COUSUB input features by `GEOID` to keep one output row
  per county subdivision.

## Validated Baseline

Validation completed on 2026-05-23 for the six-state test batch:

```bash
ruff check --no-cache src scripts tests
python -B -m unittest discover -s tests
lidar-coverage --states RI MA PA CA TX FL --coverage-threshold 5 --output-dir outputs
python -B scripts/validate_outputs.py --output-dir outputs --states RI MA PA CA TX FL --coverage-threshold 5
```

- Ruff check passed.
- Unit tests passed: `19` tests.
- Fresh six-state batch run and artifact validation passed.
- Census TIGER/Line files cached for the six test states were byte-checked
  against official Census downloads.
- The cached `resources.geojson` was byte-checked against its configured
  `hobuinc/usgs-lidar` upstream source.

| State | County subdivisions analyzed | Below 5% coverage |
| --- | ---: | ---: |
| RI | 40 | 0 |
| MA | 357 | 3 |
| PA | 2,573 | 123 |
| CA | 404 | 8 |
| TX | 862 | 28 |
| FL | 316 | 29 |

## External Quality Review

To assess whether the six-state implementation can be extended to CONUS, the
inventory was compared with the official USGS 3DEP Elevation Index `Lidar Point
Cloud Feature Layer` attributes. Only work-unit attributes were retrieved for
this review; no point-cloud data and no nationwide spatial overlay were
downloaded or run.

Official reference sources:

- USGS 3DEP spatial metadata and WESM guidance:
  `https://www.usgs.gov/3d-elevation-program/3dep-spatial-metadata`
- USGS 3DEP Elevation Index service, Lidar Point Cloud layer:
  `https://index.nationalmap.gov/arcgis/rest/services/3DEPElevationIndex/MapServer/8`
- Census TIGER/Line county subdivision reference:
  `https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html`

The metadata audit compared inventory collection names with official work units
using deterministic normalization of `USGS_LPC_` and `_LAS_YYYY` name wrappers.

| Audit item | Count |
| --- | ---: |
| Inventory footprint records | 2,258 |
| Official USGS work-unit records | 2,797 |
| Collections with comparable parsed and official dates | 1,801 |
| Parsed year differs from official acquisition start year | 447 |
| Classification disagreements at `min_year=2015` | 26 |
| Classification disagreements at `min_year=2019` | 130 |
| Classification disagreements at `min_year=2020` | 69 |
| Official 2015+ work units not matched by deterministic name normalization | 299 |

The `299` unmatched records are a required reconciliation queue, not a proven
claim that the configured footprint source omits all of them: aliases, splits,
or source-version differences must be resolved through a documented crosswalk.

## Decisions Recorded

- A collection spanning a `min_year` boundary is treated conservatively at the
  inventory unit level using its earliest authoritative acquisition year. The
  footprint is not split by acquisition date. This can understate modern
  coverage, but avoids overstating it.
- For example, the official acquisition range for the PA Sandy Supplemental
  collection crosses the 2015 boundary; it remains excluded for
  `min_year=2015` under the conservative policy.
- This decision requires authoritative acquisition date integration before it
  can be enforced consistently across CONUS; text-only name parsing is not
  sufficient evidence of earliest acquisition year.

## CONUS Readiness Work

The following items must be resolved before results are represented as a full
CONUS coverage-gap analysis.

### P1 - Authoritative vintage classification

Current preprocessing filters modern coverage from years inferred from
collection names or URLs. The official metadata audit found collection-level
classification disagreements even at the default `min_year=2015`, including
records in MA and TX from the six-state batch.

Required work:

- Join or crosswalk footprints to official USGS acquisition dates.
- Use authoritative acquisition start dates for the conservative `min_year`
  policy.
- Emit a reviewable list of unresolved or ambiguous collections and do not
  silently classify them as modern.
- Add tests for official-date overrides and boundary-spanning collections.

### P1 - Input provenance and completeness

The configured footprint inventory is not currently accompanied by a documented
official work-unit reconciliation, and cached inputs do not record source
snapshot metadata.

Required work:

- Resolve the `299` unmatched official 2015+ work units through a crosswalk or
  formally documented exclusion rationale.
- Store input URLs, download timestamps, content hashes, configured TIGER
  release, parameters, and official metadata snapshot information with each
  published run.
- Define explicit cached-snapshot and refresh behavior.

### P2 - Output validator completeness

Read-only tamper checks showed that the current validator accepts:

- a missing real gap row when the batch count is adjusted to match;
- an empty GeoJSON `FeatureCollection`; and
- incomplete gaps when validation is invoked with a threshold higher than the
  one used for the output.

Required work:

- Require `under_threshold` GEOIDs to equal exactly the records in `all.csv`
  below the supplied threshold.
- Require CSV and GeoJSON row identity and key numeric property equivalence.
- Persist the actual run parameters and validate against them.
- Add validator regression tests for omitted rows and empty/inconsistent
  GeoJSON outputs.

### P2 - Collection identity for batch counts

The inventory contains multiple names that normalize to one official work unit.
For example, the California Plumas National Forest B2 record appears under two
inventory aliases and intersects 13 California COUSUB records in the six-state
output. Coverage area is unioned and is therefore not doubled, but
`lidar_batch_count` can be overstated.

Required work:

- Establish a stable collection/work-unit identifier before counting batches.
- Add duplicate-alias tests and document how merged collections are reported.

### P3 - Scale and operational validation

Required work:

- Add a CONUS state-list configuration representing the contiguous 48 states
  plus DC.
- Add metadata-only preflight checks before any complete spatial batch.
- Run representative spatial tests beyond the current six states after P1 and
  P2 items are resolved.
- Run the complete CONUS batch only after the readiness gates above pass.

## Next Recommended Milestone

Implement authoritative USGS acquisition-date reconciliation together with a
strict output validator and source manifest. Once these checks pass on the
six-state batch and several additional representative CONUS states, schedule
the full `CONUS + DC` run.
