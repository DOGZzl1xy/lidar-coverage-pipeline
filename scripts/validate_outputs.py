"""Validate artifacts written by a state or multi-state pipeline run."""

from __future__ import annotations

import argparse
from pathlib import Path

from lidar_coverage.validation import validate_outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--states",
        nargs="+",
        help="States to check (default: every state recorded in run_manifest.json).",
    )
    parser.add_argument(
        "--coverage-threshold",
        type=float,
        help="Expected run threshold (default: the value recorded in run_manifest.json).",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    errors = validate_outputs(
        args.output_dir, states=args.states, coverage_threshold=args.coverage_threshold
    )
    if errors:
        raise SystemExit("Output validation failed:\n- " + "\n- ".join(errors))
    print(f"Validated outputs in {args.output_dir}.")


if __name__ == "__main__":
    main()
