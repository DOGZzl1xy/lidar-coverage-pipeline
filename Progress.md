# Project Progress And CONUS Status

This file is the single place for implementation status, validation results,
external quality checks, decisions, and open work. `README.md`, `agent.md`,
and `SPEC.md` cover usage, working rules, and stable contracts.

## Scope

- National scope: the contiguous 48 states plus DC (`CONUS`, 49 codes).
  Alaska, Hawaii, Puerto Rico, and other territories are excluded.
- Footprint and metadata inputs only; LiDAR point clouds are never downloaded.

## Implementation Status (v0.2.0, 2026-10-03)

Done:

- Single-state, multi-state, and `CONUS` CLI; YAML configs
  (`configs/default.yaml`, `configs/conus.yaml`).
- Per-state CSV/GeoJSON/Markdown and batch outputs.
- COUSUB multi-part dissolve by `GEOID`.
- Atomic cached downloads, `--refresh-cache`, `--skip-existing` resume.
  Reuse happens only when the previous manifest's analysis fingerprint (package
  version, `min_year`, threshold, TIGER year, inventory and override hashes)
  matches; the manifest carries `status: running|complete`, and the validator
  rejects incomplete runs.
- **Provenance (former P1 input item):** `run_manifest.json` records parameters,
  package version, timestamps, and URL/path/size/SHA-256/cache time for every
  input.
- **Output validator (former P2):** exact under-threshold set equality, CSV vs
  GeoJSON identity and numeric equivalence, empty-GeoJSON detection, batch
  statistics check, threshold/states read from the manifest and mismatches
  rejected; regression tests for each tamper case.
- `COUSUBFP = 00000` placeholder features excluded from analysis.
- **Collection identity (former P2):** `lidar_batch_count` counts distinct
  `collection_key` values (`USGS_LPC_` prefix and `_LAS_YYYY` removed).
- **CONUS operations (former P3):** `CONUS` state group, `--preflight`
  (metadata only), CONUS config.
- Optional official 3DEP work-unit footprint supplement
  (`--supplement-3dep-index`).
- `--refresh-inventory` / `refresh_inventory` re-downloads only the LiDAR
  inventory (enabled in both configs); state data-source notes in summaries.
- **Vintage reconciliation (P1):** override CSV support with `year_source`,
  `unresolved_collections.csv`, `scripts/fetch_usgs_workunits.py` (official
  3DEP attributes), `scripts/sample_ept_acquisition_dates.py` (point GPS-time
  verification), and a reviewed override table used by `configs/conus.yaml`.
- Package management moved to `uv` with a committed `uv.lock`.

## Validation (2026-10-03)

```bash
uv run ruff check src scripts tests && uv run ruff format --check src scripts tests
uv run python -m unittest discover -s tests      # 45 tests, OK (includes cached-data RI spot-check)
uv run lidar-coverage --config configs/default.yaml
uv run python scripts/validate_outputs.py --output-dir outputs_six_state
uv run lidar-coverage --states CONUS --preflight  # 49/49 TIGER URLs reachable
uv run lidar-coverage --config configs/conus.yaml
uv run python scripts/validate_outputs.py --output-dir outputs
```

Independent spot-check: 42 CONUS records (3 gap + 3 non-gap in each of MN, KY,
VA, NC, OR, ME, AZ) recomputed by per-footprint intersection and union all
match the pipeline within 0.01 percentage points.

Regression against the v0.1 six-state outputs: every `coverage_pct` is
identical across all 4,552 records. `lidar_batch_count` dropped for 13 CA and
6 TX records because inventory aliases (for example the Plumas NF B2
collection) are now counted once. No other values changed.

Inventory classification (`resources.geojson` pulled 2026-10-03, SHA-256
`7159de54b31c…`; versus the May cache: +21 collections, none removed, 43
footprints changed >1%): 2,279 records / 2,273 collection keys; 53 reviewed
overrides, 2,000 dated from a four-digit year, 224 from a USGS suffix, 2
unresolved (Alaska); 1,523 records (1,518 collections) are 2015+.

## Source Completeness: USGS 3DEP Index Supplement (2026-10-03)

Several towns with 0% coverage had modern 3DEP LiDAR in the official USGS
index that is missing from `hobuinc/usgs-lidar`, which lists only collections
already converted to EPT. Examples: Concord, NC (`NC_Phase4_Cabarrus_2016`),
New Ulm, MN (`MN_RiverEast_2_B23`), and Colonial Heights, VA
(`VA_SouthamptonHenricoWMBG_2_2019`). Meredith township, NC (Wake County) has
only 2001 data in both sources and is a real gap.

`--supplement-3dep-index` (config `configs/conus_with_3dep.yaml`) adds the
official 3DEP work-unit footprints (2,850 units, generalized to ~50 m,
attributes only, vintage = `collect_end` year, reviewed overrides applied).

| Footprint source | Gap records (< 5%) | Zero coverage | Output |
| --- | ---: | ---: | --- |
| hobuinc inventory only (source named in the project brief) | 2,304 | 2,001 | `outputs/` |
| hobuinc + official 3DEP index | **396** | 288 | `outputs_with_3dep/` |

With the supplement the largest gap counts are NC 157, OR 46, MS 37, VA 28,
ND 19, TX 15, MI 15, WA 14, MN 14, and MT 12; 29 jurisdictions have none. The
supplement uses unreviewed official dates for work units outside the 53
reviewed collections, and the generalized footprints can shift coverage for
towns near a work-unit edge. The baseline results are unchanged when the
option is off.

## CONUS + DC Results (hobuinc inventory, 2026-10-03)

Command: `uv run lidar-coverage --config configs/conus.yaml` (`min_year=2015`,
threshold `< 5%`, reviewed overrides
`data/reference/vintage_overrides_reviewed.csv` with 53 collections, latest
inventory pulled automatically, `COUSUBFP=00000` placeholders excluded).
Outputs are in `outputs/` (~1 GB, not committed); the strict validator passed.

- County subdivisions analyzed: **35,309** in 49 jurisdictions.
- Below 5% modern coverage: **2,304**, of which 2,001 have zero coverage.
- Most gap records: MN 548, NC 168, VA 167, ND 143, NJ 142, PA 123, ME 111,
  OR 92, NE 87, WA 82. States with none: AL, CT, DE, DC, IN, IA, KY, NH, RI,
  VT, WV, WY.
- MN and KY summaries carry a data-source note (see below).
- Full per-state table: `outputs/batch_summary.md`.

Run history on 2026-10-03 (gap records / analyzed):

| Run | Result | Main changes versus the previous run |
| --- | --- | --- |
| Provisional | 2,690 / 35,401 | Text-derived vintages, May inventory |
| Reviewed (earliest year) | 2,519 / 35,309 | 33 reviewed collections; inventory +21 collections (AR −131, AL −10); `00000` removed; IL −48, KS +48 |
| Current (latest year) | 2,304 / 35,309 | Spanning collections count as modern: KY −124 (`KY_FullState`), KS −48, VT −17, OK −11, NY −9, MO −4; upstream footprint redraw: NE +4, MT +1, OR +1 |

### Data-source notes (reported in outputs)

- **MN:** the statewide Gen2 LiDAR (2021–2024, MnGeo) is only partly in the
  USGS inventory; `MN_FullState` is the 2011–2012 generation. MN gaps (548)
  may be covered by Gen2 data.
- **KY:** KyFromAbove Phase 2 (~2024) and Phase 3 (~2025–26) are not in the
  inventory; `KY_FullState` is the 2010–2018 Phase 1 mosaic (now counted as
  modern because it spans 2015).
- These notes live in `STATE_PROGRAM_NOTES` (`constants.py`) and are printed in
  `<st>_coverage_summary.md` and `batch_summary.md`.

### Known limitations

- Only the 53 reviewed collections use verified dates. All other collections
  use text-derived years. No unreviewed collection has a text year of 2015 or
  later with an official end year before 2015. The 20 that had the reverse
  pattern were all sampled (C1–C20).
- Collections absent from the official USGS index cannot be checked for
  spanning acquisitions.
- The upstream inventory is regenerated almost daily. With
  `refresh_inventory: true`, each run uses the latest version and records its
  SHA-256 in `run_manifest.json`, so a rerun on a later day can differ
  slightly (for example, 43 footprints changed by more than 1% between May and
  October).

## P1 Review Record (resolved 2026-10-03)

- Reviewed with the user: 7 unresolved collections (A1–A7) and 26 boundary
  flips (B1–B26). After the user's policy change to the latest acquisition
  year, 20 more collections were checked (C1–C20): their name year is before
  2015 but the official end year is 2015 or later. Point sampling confirmed 11
  as spanning 2015 (modern). For 9, the points do not support the official end
  year, so they stay old. Evidence for every row is in
  `data/reference/vintage_overrides_reviewed.csv` (`start_year`, `end_year`,
  `review_id`, `evidence`).
- Official years were used unless contradicted by stronger evidence; official
  years were rejected for B10–B14, B21, B22, B24, C1, C3, C4, C6, C7, C11,
  C12, C16, and C17.
- Evidence sources: OpenTopography/USGS dataset pages, NOAA InPort, state
  catalogs, collection reports, and point-cloud GPS-time sampling.
- **Point-cloud sampling (user-approved exception, verification only):**
  `scripts/sample_ept_acquisition_dates.py` downloads ~24–96 coarse EPT octree
  nodes (5–65 MB per collection) and converts `GpsTime` to dates. Control
  collections with published dates (IL Boone, OR Harney Silver 1, AZ USFS,
  RI Statewide) matched to the day. A collection counts as spanning 2015 when
  at least 1% of sampled points fall in 2015 or later. Collections stored in
  GPS week time (IA_FullState, MN Jackson Co, MN Lincoln Co) or without
  GpsTime (ID Emerald Creek) carry no date in the points; those decisions rely
  on documentary evidence. The analysis pipeline itself never downloads point
  clouds.
- Raw official snapshot: `data/reference/usgs_workunit_vintage.csv` (2,850 work
  units with `start_year`/`end_year`, retrieved 2026-10-03; not applied
  wholesale).
- Unresolved: 2 Alaska collections (`AK_TyphoonMerbokNV5_*_F23`, outside
  CONUS; the `F` suffix letter is not parsed).

### Resolved - Undefined county subdivisions

TIGER placeholder `County subdivisions not defined` features (COUSUB code
`00000`, mostly water areas; 92 nationally) are excluded from analysis as of
2026-10-03 (user decision).

## Decisions Recorded

- **Changed 2026-10-03 (user decision):** a collection that spans the
  `min_year` boundary is treated as modern; it is classified by its latest
  acquisition year. Footprints are not split by date. This replaces the
  earlier conservative earliest-year policy, and override files now carry
  `end_year`.
- Collections without a determinable vintage are excluded from modern
  coverage and listed for review, never silently treated as modern.
- Earlier CONUS runs on 2026-10-03 (provisional, then earliest-year reviewed)
  were superseded by the current run above.
- State-run programs outside the USGS inventory (MN Gen2, KyFromAbove) are
  noted in outputs rather than added as sources (user decision).
- The LiDAR inventory is refreshed on every configured run to stay current.
- The official 3DEP index supplement is opt-in; the default remains the
  `hobuinc/usgs-lidar` source specified for the project. Which result to
  present as primary is a decision for the PI.
- Point-cloud downloads are allowed only for small verification samples with
  the user's approval; never inside the analysis pipeline.

## Reference Sources

- USGS 3DEP spatial metadata: `https://www.usgs.gov/3d-elevation-program/3dep-spatial-metadata`
- 3DEP Elevation Index, Lidar Point Cloud layer:
  `https://index.nationalmap.gov/arcgis/rest/services/3DEPElevationIndex/MapServer/8`
- Census TIGER/Line: `https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html`
