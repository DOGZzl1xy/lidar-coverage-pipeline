# Agent Task List

This document is the implementation checklist for standardizing the LiDAR
coverage pipeline. Before making a decision or asking the user a question,
read `SPEC.md` first for the stable project contract, then read `Progress.md`
for current validation status, recorded decisions, and outstanding readiness
work. Ask the user only when the needed information is not specified there and
cannot be determined safely from the repository.

## Working Rules

- Preserve the existing single-state CLI entry point:
  `lidar-coverage --state RI`.
- The planned national expansion scope is the contiguous 48 states plus DC
  (`CONUS + DC`).
- Do not run a complete CONUS analysis until the readiness gates recorded in
  `Progress.md` are complete; never download LiDAR point clouds.
- Do not commit generated caches or output artifacts.
- Use the Census TIGER/Line COUSUB boundaries and the
  `hobuinc/usgs-lidar` footprint metadata described in `SPEC.md`.
- Keep changes focused on repeatable state and batch coverage analysis.
- Record validation findings, external audits, and open expansion work only in
  `Progress.md`; keep this checklist and the project specification concise.

## Task Checklist

- [x] Inspect the original repository layout and single-state implementation.
- [x] Capture requirements, conventions, and output contracts in `SPEC.md`.
- [x] Standardize project configuration and Python source formatting.
- [x] Add YAML configuration support with a documented default configuration.
- [x] Preserve single-state operation and implement multi-state CLI operation.
- [x] Write per-state CSV, Markdown, and GeoJSON outputs.
- [x] Write batch summary CSV and Markdown outputs.
- [x] Add unit tests for vintage parsing, the 2015 filter, coverage bounds,
      empty LiDAR input, and multi-state summaries.
- [x] Add `scripts/validate_outputs.py` for multi-state artifact validation.
- [x] Update `README.md` and `.gitignore` for the standardized workflow.
- [x] Install the package and run the requested test and six-state validation
      commands for `RI MA PA CA TX FL`.
- [x] Parse supported USGS suffix-style years and ignore `_LAS_YYYY`
      processing tokens during current text-based vintage extraction.
- [x] Dissolve multi-part COUSUB fragments by `GEOID`.
- [x] Check unique GEOIDs and below-threshold row values in
      `scripts/validate_outputs.py`.
- [x] Fix hardcoded "2015+" in vintage note text: now uses `min_year` param.
- [x] Fix cross-field year priority: four-digit year from URL now takes
      precedence over USGS suffix in name, matching SPEC contract.
- [x] Fix 3 Ruff E501 line-length violations in analysis.py and
      test_pipeline.py.
- [x] Add `Progress.md` as the single record for validation status, external
      quality review, decisions, and CONUS readiness work.

## Required Final Checks

Run these commands from the repository root:

```bash
python -m pip install -e .
python -m unittest discover -s tests
lidar-coverage --states RI MA PA CA TX FL --coverage-threshold 5 --output-dir outputs
python scripts/validate_outputs.py --output-dir outputs --states RI MA PA CA TX FL
```

Report changed files, new commands, whether the six-state run completed,
where state outputs were written, and any matters requiring human review.
