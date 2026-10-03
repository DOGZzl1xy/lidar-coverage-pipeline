# Agent Task List

Read `SPEC.md` for the stable contract and `Progress.md` for validation status,
recorded decisions, and open work before you change anything or ask the user a
question. Ask only when neither document answers it and the repository cannot
settle it safely.

## Working Rules

- Manage the environment with `uv` (`uv sync`, `uv run ...`); do not install
  into a global/conda environment.
- Keep `lidar-coverage --state RI` working; national scope is `CONUS` (48
  states + DC).
- The analysis pipeline uses footprint and metadata inputs only. Small
  point-cloud samples (`scripts/sample_ept_acquisition_dates.py`) are allowed
  for vintage verification with the user's approval.
- Do not commit caches (`data/cache/`) or generated outputs (`outputs*/`).
- Record validation results, audits, decisions, and open work only in
  `Progress.md`; keep this file and `SPEC.md` concise.

## Completed

- Standardized package, YAML configuration, single/multi-state CLI, per-state
  and batch outputs, unit tests (v0.1, 2026-05).
- v0.2 (2026-10-03): atomic cached downloads, `collection_key` alias merging
  for batch counts, vintage override framework with `year_source` and
  `unresolved_collections.csv`, `run_manifest.json` provenance, strict
  validator with regression tests, `CONUS` group + `configs/conus.yaml`,
  `--preflight`, `--skip-existing`, `--refresh-cache`, uv migration, removal
  of stale output directories.
- P1 vintage review completed (53 reviewed collections, latest-year policy);
  `00000` placeholders excluded; inventory auto-refresh; MN/KY data-source
  notes; CONUS + DC run completed and validated (2,304 of 35,309 below 5%).

## Open Tasks

- [ ] PI decision: present the hobuinc-only result (2,304 gaps) or the
      3DEP-supplemented result (396 gaps) as primary.
- [ ] Review the remaining text/official year differences before using a
      `min_year` other than 2015.

## Required Final Checks

```bash
uv sync
uv run ruff check src scripts tests && uv run ruff format --check src scripts tests
uv run python -m unittest discover -s tests
uv run lidar-coverage --config configs/default.yaml
uv run python scripts/validate_outputs.py --output-dir outputs_six_state
```

Report changed files, new commands, run results, output locations, and any
matters that need human review.
