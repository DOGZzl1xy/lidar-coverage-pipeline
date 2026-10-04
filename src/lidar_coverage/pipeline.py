"""Batch orchestration, provenance manifest, and metadata-only preflight."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import geopandas as gpd
import pandas as pd

from lidar_coverage.analysis import compute_coverage
from lidar_coverage.constants import (
    CENSUS_TIGER_YEAR,
    DEFAULT_COVERAGE_THRESHOLD,
    DEFAULT_MIN_YEAR,
    REVIEWED_VINTAGE_OVERRIDES,
    STATE_GROUPS,
    STATE_TO_FIPS,
    USGS_LIDAR_METADATA_URL,
    USGS_WORKUNIT_QUERY_URL,
)
from lidar_coverage.io import (
    build_session,
    census_cousub_url,
    describe_input,
    download_census_cousub,
    download_usgs_3dep_index,
    download_usgs_lidar_metadata,
    ensure_directory,
    read_vector,
    sha256_file,
)
from lidar_coverage.preprocess import (
    classify_lidar_vintage,
    load_vintage_overrides,
    prepare_cousub,
    select_modern_lidar,
    usgs_3dep_as_inventory,
)
from lidar_coverage.reporting import (
    BATCH_COLUMNS,
    MANIFEST_NAME,
    UNRESOLVED_COLUMNS,
    UNRESOLVED_NAME,
    build_batch_markdown_summary,
    build_markdown_summary,
    format_output_table,
    state_output_paths,
    summarize_state,
    write_csv,
    write_geojson,
    write_json,
    write_markdown,
)


@dataclass(frozen=True)
class RunOptions:
    states: list[str]
    cache_dir: Path
    output_dir: Path
    min_year: int
    coverage_threshold: float
    vintage_overrides: Path | None = None
    refresh_cache: bool = False
    refresh_inventory: bool = True
    supplement_3dep_index: bool = False
    skip_existing: bool = False


def normalize_states(states: list[str]) -> list[str]:
    if not states:
        raise ValueError("At least one state abbreviation is required.")
    normalized: list[str] = []
    for state in states:
        state_abbr = str(state).upper()
        expanded = STATE_GROUPS.get(state_abbr, (state_abbr,))
        for code in expanded:
            if code not in STATE_TO_FIPS:
                raise ValueError(f"Unknown state abbreviation: {code}")
            if code not in normalized:
                normalized.append(code)
    return normalized


def run(
    states: list[str] | str = "RI",
    *,
    output_dir: str | Path = "outputs",
    cache_dir: str | Path = "data/cache",
    min_year: int = DEFAULT_MIN_YEAR,
    coverage_threshold: float = DEFAULT_COVERAGE_THRESHOLD,
    vintage_overrides: str | Path | None = REVIEWED_VINTAGE_OVERRIDES,
    supplement_3dep_index: bool = False,
    offline: bool = False,
    skip_existing: bool = False,
) -> pd.DataFrame:
    """Python entry point, e.g. ``run(["RI", "MA"])`` or ``run("CONUS")``.

    Returns the batch summary (one row per state); files go to ``output_dir``.
    """
    return run_pipeline(
        RunOptions(
            states=normalize_states([states] if isinstance(states, str) else list(states)),
            cache_dir=Path(cache_dir),
            output_dir=Path(output_dir),
            min_year=min_year,
            coverage_threshold=coverage_threshold,
            vintage_overrides=Path(vintage_overrides) if vintage_overrides else None,
            refresh_inventory=not offline,
            supplement_3dep_index=supplement_3dep_index,
            skip_existing=skip_existing,
        )
    )


def package_version() -> str:
    try:
        return version("lidar-coverage")
    except PackageNotFoundError:
        return "unknown"


def _load_classified_lidar(options: RunOptions) -> tuple[dict[str, Path], gpd.GeoDataFrame]:
    """Load and classify footprints: the hobuinc inventory, optionally plus 3DEP work units."""
    refresh = options.refresh_cache or options.refresh_inventory
    overrides = (
        load_vintage_overrides(options.vintage_overrides) if options.vintage_overrides else None
    )
    paths = {"lidar_inventory": download_usgs_lidar_metadata(options.cache_dir, refresh=refresh)}
    frames = [classify_lidar_vintage(read_vector(paths["lidar_inventory"]), overrides=overrides)]
    if options.supplement_3dep_index:
        paths["usgs_3dep_index"] = download_usgs_3dep_index(options.cache_dir, refresh=refresh)
        index = usgs_3dep_as_inventory(read_vector(paths["usgs_3dep_index"]))
        frames.append(classify_lidar_vintage(index, overrides=overrides).to_crs(frames[0].crs))
    classified = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs)
    return paths, classified


def inventory_stats(classified: gpd.GeoDataFrame, min_year: int) -> dict[str, object]:
    modern = classified["year"].notna() & (classified["year"] >= min_year)
    return {
        "records": len(classified),
        "distinct_collections": int(classified["collection_key"].nunique()),
        "year_source_counts": classified["year_source"].value_counts().sort_index().to_dict(),
        "modern_records": int(modern.sum()),
        "modern_distinct_collections": int(classified.loc[modern, "collection_key"].nunique()),
        "unresolved_records": int(classified["year"].isna().sum()),
    }


def _write_state_outputs(
    state_abbr: str,
    all_results: gpd.GeoDataFrame,
    gap_results: gpd.GeoDataFrame,
    *,
    paths: dict[str, Path],
    threshold: float,
) -> None:
    write_csv(format_output_table(all_results), paths["all_csv"])
    write_csv(format_output_table(gap_results), paths["gap_csv"])
    write_geojson(all_results, paths["all_geojson"])
    write_geojson(gap_results, paths["gap_geojson"])
    write_markdown(
        build_markdown_summary(state_abbr, all_results, gap_results, threshold=threshold),
        paths["markdown"],
    )


def _read_existing_state(paths: dict[str, Path]) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    if not all(path.exists() for path in paths.values()):
        return None
    read = {"dtype": {"GEOID": str}}
    return pd.read_csv(paths["all_csv"], **read), pd.read_csv(paths["gap_csv"], **read)


def analysis_fingerprint(manifest: dict) -> dict[str, object]:
    """Everything that changes per-state results; outputs are reusable only on a match."""
    parameters = manifest.get("parameters", {})
    inputs = manifest.get("inputs", {})
    overrides = inputs.get("vintage_overrides") or {}
    return {
        "package_version": manifest.get("package_version"),
        "min_year": parameters.get("min_year"),
        "coverage_threshold": parameters.get("coverage_threshold"),
        "tiger_year": parameters.get("tiger_year"),
        "lidar_inventory_sha256": (inputs.get("lidar_inventory") or {}).get("sha256"),
        "usgs_3dep_index_sha256": (inputs.get("usgs_3dep_index") or {}).get("sha256"),
        "vintage_overrides_sha256": overrides.get("sha256"),
    }


def _previous_manifest(output_dir: Path) -> dict | None:
    path = output_dir / MANIFEST_NAME
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def run_pipeline(options: RunOptions) -> pd.DataFrame:
    started = datetime.now(UTC)
    ensure_directory(options.cache_dir)
    output_dir = ensure_directory(options.output_dir)
    input_paths, classified = _load_classified_lidar(options)
    lidar = select_modern_lidar(classified, min_year=options.min_year)

    parameters = asdict(options)
    parameters.update(
        cache_dir=str(options.cache_dir),
        output_dir=str(options.output_dir),
        vintage_overrides=str(options.vintage_overrides) if options.vintage_overrides else None,
        tiger_year=CENSUS_TIGER_YEAR,
    )
    manifest: dict[str, object] = {
        "package": "lidar-coverage",
        "package_version": package_version(),
        "status": "running",
        "started_at_utc": started.isoformat(timespec="seconds"),
        "finished_at_utc": None,
        "parameters": parameters,
        "vintage_policy": (
            "override CSV (latest acquisition year; collections spanning min_year count as "
            "modern) > inventory year column > four-digit year in name/URL (ignoring "
            "_LAS_YYYY) > USGS batch/delivery suffix; unresolved records excluded"
        ),
        "inputs": {
            "lidar_inventory": describe_input(
                input_paths["lidar_inventory"], USGS_LIDAR_METADATA_URL
            ),
            "usgs_3dep_index": (
                describe_input(input_paths["usgs_3dep_index"], USGS_WORKUNIT_QUERY_URL)
                if "usgs_3dep_index" in input_paths
                else None
            ),
            "vintage_overrides": (
                {
                    "path": str(options.vintage_overrides),
                    "sha256": sha256_file(options.vintage_overrides),
                }
                if options.vintage_overrides
                else None
            ),
            "census_cousub": {},
        },
        "lidar_inventory_stats": inventory_stats(classified, options.min_year),
    }

    # Reuse per-state outputs only when they came from an identical analysis setup.
    reuse = False
    if options.skip_existing:
        previous = _previous_manifest(output_dir)
        reuse = previous is not None and analysis_fingerprint(previous) == analysis_fingerprint(
            manifest
        )
        if not reuse:
            print("--skip-existing ignored: existing outputs were produced with other settings.")
    write_json(manifest, output_dir / MANIFEST_NAME)

    unresolved = classified.loc[classified["year"].isna(), UNRESOLVED_COLUMNS]
    write_csv(unresolved.sort_values("lidar_name"), output_dir / UNRESOLVED_NAME)

    census_inputs: dict[str, dict[str, object]] = manifest["inputs"]["census_cousub"]
    summaries: list[dict[str, str | int | float]] = []
    total = len(options.states)
    for position, state_abbr in enumerate(options.states, start=1):
        census_path = download_census_cousub(
            state_abbr, options.cache_dir, refresh=options.refresh_cache
        )
        census_inputs[state_abbr] = describe_input(census_path, census_cousub_url(state_abbr))
        paths = state_output_paths(output_dir, state_abbr)

        existing = _read_existing_state(paths) if reuse else None
        if existing is not None:
            all_results, gap_results = existing
            status = "reused existing outputs"
        else:
            towns = prepare_cousub(read_vector(census_path), state_abbr)
            all_results, gap_results = compute_coverage(
                towns,
                lidar,
                coverage_threshold=options.coverage_threshold,
                min_year=options.min_year,
            )
            _write_state_outputs(
                state_abbr,
                all_results,
                gap_results,
                paths=paths,
                threshold=options.coverage_threshold,
            )
            status = "analyzed"
        summaries.append(summarize_state(state_abbr, all_results, gap_results))
        write_json(manifest, output_dir / MANIFEST_NAME)
        print(
            f"[{position}/{total}] {state_abbr}: {status} {len(all_results)} county "
            f"subdivisions; {len(gap_results)} below {options.coverage_threshold:.1f}%.",
            flush=True,
        )

    batch_summary = pd.DataFrame(summaries, columns=BATCH_COLUMNS)
    write_csv(batch_summary, output_dir / "batch_summary.csv")
    write_markdown(
        build_batch_markdown_summary(
            batch_summary,
            threshold=options.coverage_threshold,
            min_year=options.min_year,
        ),
        output_dir / "batch_summary.md",
    )

    manifest["status"] = "complete"
    manifest["finished_at_utc"] = datetime.now(UTC).isoformat(timespec="seconds")
    write_json(manifest, output_dir / MANIFEST_NAME)
    return batch_summary


def run_preflight(options: RunOptions) -> list[str]:
    """Metadata-only readiness checks; performs no spatial analysis."""
    problems: list[str] = []
    ensure_directory(options.cache_dir)
    try:
        _, classified = _load_classified_lidar(options)
    except Exception as error:  # noqa: BLE001 - report every failure mode to the operator
        problems.append(f"LiDAR inventory unavailable: {error}")
    else:
        stats = inventory_stats(classified, options.min_year)
        print("LiDAR inventory:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

    session = build_session()
    print(f"Census TIGER/Line {CENSUS_TIGER_YEAR} COUSUB sources ({len(options.states)} states):")
    for state_abbr in options.states:
        url = census_cousub_url(state_abbr)
        cached = (options.cache_dir / "census" / Path(url).name).exists()
        try:
            response = session.head(url, timeout=(15, 60), allow_redirects=True)
            ok = response.status_code == 200
            size = int(response.headers.get("Content-Length", 0))
        except Exception as error:  # noqa: BLE001
            ok, size = False, 0
            problems.append(f"{state_abbr}: {url} unreachable ({error})")
        else:
            if not ok:
                problems.append(f"{state_abbr}: {url} returned HTTP {response.status_code}")
        print(
            f"  {state_abbr}: {'ok' if ok else 'FAIL'} "
            f"{size / 1_000_000:.1f} MB{' (cached)' if cached else ''}"
        )
    return problems
