# Agent Notes

Read `SPEC.md` (contract) and `Progress.md` (results, decisions, open items)
before changing anything or asking the user a question.

## Rules

- Use uv (`uv sync`, `uv run ...`); never install into a global or conda
  environment.
- The analysis uses footprints and metadata only. Point-cloud sampling for
  vintage checks needs the user's approval.
- Never commit `data/cache/` or `outputs*/`.
- Record results, audits and decisions only in `Progress.md`.
- Add new reviewed vintages to
  `src/lidar_coverage/data/vintage_overrides_reviewed.csv` with a `review_id`
  and evidence.

## Checks before handing back

```bash
uv run ruff check src scripts tests && uv run ruff format --check src scripts tests
uv run python -m unittest discover -s tests
uv run lidar-coverage --states RI MA PA CA TX FL --output-dir outputs_six_state
uv run lidar-coverage-validate outputs_six_state
```
