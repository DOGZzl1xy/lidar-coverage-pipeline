# Progress

Current results, review records, decisions and open items. Usage is in
`README.md`; the contract is in `SPEC.md`.

## Status (v0.3.0, 2026-10-12)

Installable package (`uv tool install git+https://github.com/DOGZzl1xy/lidar-coverage-pipeline`)
with `lidar-coverage` and `lidar-coverage-validate`, a Python `run()` API,
`CONUS` runs, preflight, resumable runs, run manifests, a strict validator,
an optional USGS 3DEP index supplement, and a bundled reviewed vintage table.
49 unit tests pass.

## CONUS + DC results (2026-10-06 inputs)

`min_year=2015`, threshold `< 5%`, 62 reviewed vintages, inventory SHA-256
`a625dfd46eb2…`, 3DEP index SHA-256 `c95378416f13…`. Both runs were
reproduced on 2026-10-12 from the cached inputs and passed the validator.
Report: <https://dogzzl1xy.github.io/lidar-coverage-pipeline/>.

| Footprints | Analyzed | Below 5% | Zero coverage | Largest gap counts |
| --- | ---: | ---: | ---: | --- |
| hobuinc inventory (`configs/conus.yaml`) | 35,309 | 2,306 | 2,008 | MN 549, NC 168, VA 168, ND 144, NJ 142 |
| + USGS 3DEP index (`configs/conus_with_3dep.yaml`) | 35,309 | 420 | 310 | NC 157, OR 45, MI 37, MS 37, VA 29 |

The 2026-10-03 version reported 2,304 and 396. Of the change to 420, 2 come
from the newer inventory and 22 from the D-series date corrections (+27 in
Allegan and Van Buren counties, MI; −5 around Leelanau County, MI).

The hobuinc inventory lists only collections already converted to EPT. The
official index contains modern work units it lacks, for example
`NC_Phase4_Cabarrus_2016` (Concord, NC), `MN_RiverEast_2_B23` (New Ulm, MN) and
`VA_SouthamptonHenricoWMBG_2_2019` (Colonial Heights, VA). Meredith township,
NC has only 2001 data in both sources.

### Limitations

- MN Gen2 (2021–2024) and KyFromAbove Phases 2–3 (2024–2026) are not fully in
  either source; MN and KY summaries carry a note.
- Outside the 62 reviewed collections, vintages come from names (inventory) or
  official dates (3DEP index). The 2026-10-06 point sampling checked these
  against GPS times where possible, but 578 collections (mostly 2006–2012) have
  no usable timestamps and keep their name or official year, and 3DEP-only
  collections were sampled at 4 tiles each. 3DEP footprints are generalized to
  ~50 m.
- The hobuinc inventory is regenerated almost daily (43 footprints changed by
  more than 1% between May and October 2026), so reruns on later days can
  differ slightly.
- Only 2015 has been reviewed as the modern threshold; other `min_year` values
  need a new review of text versus official years.

## Vintage review record (2026-10-03, extended 2026-10-06)

The bundled table `src/lidar_coverage/data/vintage_overrides_reviewed.csv`
holds 62 decisions with evidence:

- A1–A7: collections whose year could not be parsed (`MN_FullState` 2011–12,
  `KY_FullState` 2010–2017 mosaic, `IA_FullState` ≤2010, NYC 2014, three IL
  collections 2008–2011).
- B1–B26: collections whose parsed and official years fall on different sides
  of 2015.
- C1–C20: collections whose official end year reaches 2015 while the name year
  does not; 11 confirmed as spanning 2015, 9 not supported by the points.
- D1–D10 (2026-10-06): collections whose sampled dates fall on the other side
  of 2015 from the year the analysis used. Eight changed: `MI_LeelanauCo_2015`
  to 2015 (supersedes B20), `NY_Cl_Ess_LChamp_P2_2014` to 2014–2015,
  `MI_25County_AlleganCo_2015` and `MI_AlleganCo_2015` to 2014, and four
  `MO_AR` collections to end in 2015 or 2016. Two kept: `MO_AR_PhillipsDesha_2014`
  (3.3% of points in 2015, below the threshold) and `VA_Shenandoah_2014`
  (4 tiles too few to overrule the official 2015 end).

Evidence came from OpenTopography/USGS pages, NOAA InPort, state catalogs,
collection reports, and point GPS-time sampling. Sampling matched published
dates to the day for control collections; a collection counts as spanning
2015 when at least 5% of sampled points fall in 2015 or later. (The A–C
review recorded a 1% threshold; no A–C decision falls between 1% and 5%, so
every A–C result is the same under either. D9 is the only collection the two
thresholds would treat differently.) Official years were rejected for
B10–B14, B21, B22, B24, C1, C3, C4, C6, C7, C11, C12, C16 and C17. Two Alaska
collections (`AK_TyphoonMerbokNV5_*_F23`) remain unresolved; they are outside
CONUS.

### Point-cloud date check (2026-10-06)

GPS times were sampled from all 2,866 collections (2,274 inventory, 592
official-index only): 8–32 EPT nodes per inventory collection, the first
100,000 points of 4 LAZ tiles per 3DEP-only work unit. 2,286 yielded dates;
of those with official dates, 98.4% fall in the same years. 578 have no usable
timestamps and 2 could not be read. Most of the 37 mismatches trace to the
official index (single-day dates that look like publication dates, years off by
one or two with matching month and day, and one shared Illinois District 7
range). The sampling scripts and raw results lived on the `vintage-sampling`
branch (last commit `5e2b59d`), which was deleted after the review; the
evidence for each decision is in the table.

## Decisions

- Collections spanning 2015 count as modern (latest acquisition year); from
  point samples, spanning means at least 5% of points in 2015 or later.
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
