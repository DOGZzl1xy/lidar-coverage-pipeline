# Progress

Current results, review records, decisions and open items. Usage is in
`README.md`; the contract is in `SPEC.md`.

## Status (v0.3.0, 2026-10-03)

Installable package (`uv tool install git+https://github.com/DOGZzl1xy/lidar-coverage-pipeline`)
with `lidar-coverage` and `lidar-coverage-validate`, a Python `run()` API,
`CONUS` runs, preflight, resumable runs, run manifests, a strict validator,
an optional USGS 3DEP index supplement, and a bundled reviewed vintage table.
49 unit tests pass.

## CONUS + DC results (2026-10-03)

`min_year=2015`, threshold `< 5%`, reviewed vintages, inventory SHA-256
`7159de54b31c…`. Both runs passed the validator. Report:
<https://dogzzl1xy.github.io/lidar-coverage-pipeline/>.

| Footprints | Analyzed | Below 5% | Zero coverage | Largest gap counts |
| --- | ---: | ---: | ---: | --- |
| hobuinc inventory (`configs/conus.yaml`) | 35,309 | 2,304 | 2,001 | MN 548, NC 168, VA 167, ND 143, NJ 142 |
| + USGS 3DEP index (`configs/conus_with_3dep.yaml`) | 35,309 | 396 | 288 | NC 157, OR 46, MS 37, VA 28, ND 19 |

The hobuinc inventory lists only collections already converted to EPT. The
official index contains modern work units it lacks, for example
`NC_Phase4_Cabarrus_2016` (Concord, NC), `MN_RiverEast_2_B23` (New Ulm, MN) and
`VA_SouthamptonHenricoWMBG_2_2019` (Colonial Heights, VA). Meredith township,
NC has only 2001 data in both sources.

### Limitations

- MN Gen2 (2021–2024) and KyFromAbove Phases 2–3 (2024–2026) are not fully in
  either source; MN and KY summaries carry a note.
- Outside the 53 reviewed collections, vintages come from names (inventory) or
  unreviewed official dates (3DEP index). 3DEP footprints are generalized to
  ~50 m.
- The hobuinc inventory is regenerated almost daily (43 footprints changed by
  more than 1% between May and October 2026), so reruns on later days can
  differ slightly.
- Only 2015 has been reviewed as the modern threshold; other `min_year` values
  need a new review of text versus official years.

## Vintage review record (2026-10-03)

The bundled table `src/lidar_coverage/data/vintage_overrides_reviewed.csv`
holds 53 decisions with evidence:

- A1–A7: collections whose year could not be parsed (`MN_FullState` 2011–12,
  `KY_FullState` 2010–2017 mosaic, `IA_FullState` ≤2010, NYC 2014, three IL
  collections 2008–2011).
- B1–B26: collections whose parsed and official years fall on different sides
  of 2015.
- C1–C20: collections whose official end year reaches 2015 while the name year
  does not; 11 confirmed as spanning 2015, 9 not supported by the points.

Evidence came from OpenTopography/USGS pages, NOAA InPort, state catalogs,
collection reports, and point GPS-time sampling. Sampling matched published
dates to the day for control collections; a collection counts as spanning
2015 when at least 1% of sampled points fall in 2015 or later. Official years
were rejected for B10–B14, B21, B22, B24, C1, C3, C4, C6, C7, C11, C12, C16
and C17. Two Alaska collections (`AK_TyphoonMerbokNV5_*_F23`) remain
unresolved; they are outside CONUS.

## Decisions

- Collections spanning 2015 count as modern (latest acquisition year).
- `COUSUBFP = 00000` placeholder features are excluded.
- State programs outside the USGS sources are noted, not added as sources.
- The latest inventory is downloaded on every run; input hashes go to the
  manifest.
- The 3DEP supplement is optional because the brief named the hobuinc
  inventory.
- Point-cloud downloads are limited to small, user-approved verification
  samples.

## Open items

- PI decision: present the hobuinc-only result or the 3DEP-supplemented result
  as primary.

## References

- USGS 3DEP Elevation Index, Lidar Point Cloud layer:
  <https://index.nationalmap.gov/arcgis/rest/services/3DEPElevationIndex/MapServer/8>
- USGS 3DEP spatial metadata: <https://www.usgs.gov/3d-elevation-program/3dep-spatial-metadata>
- Census TIGER/Line: <https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html>
