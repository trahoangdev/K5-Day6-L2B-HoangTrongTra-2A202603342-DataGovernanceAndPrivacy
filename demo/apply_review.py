"""Merge demo/decisions.csv onto the live review queue without copying scores.

Usage, from the repo root, after the offline PoC run:

    .\\.venv\\Scripts\\python.exe -m demo.apply_review
    .\\.venv\\Scripts\\python.exe -m src.main --track t02 --output out/poc --run-name poc --offline --seed 42
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.team06.human_review import REVIEWER, merge_review_decisions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fill review_queue_reviewed.csv from demo decisions")
    parser.add_argument("--queue", type=Path, default=Path("out/poc/review_queue.csv"))
    parser.add_argument("--decisions", type=Path, default=Path("demo/decisions.csv"))
    parser.add_argument("--out", type=Path, default=Path("out/poc/review_queue_reviewed.csv"))
    parser.add_argument("--reviewer", default=REVIEWER)
    args = parser.parse_args(argv)
    queue = pd.read_csv(args.queue, dtype=str).fillna("")
    decisions = pd.read_csv(args.decisions, dtype=str).fillna("")
    reviewed = merge_review_decisions(queue, decisions, args.reviewer)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    reviewed.to_csv(args.out, index=False)
    filled = int(reviewed.reviewer_decision.str.strip().ne("").sum())
    print(f"wrote {args.out} ({filled}/{len(reviewed)} decided, reviewer={args.reviewer})")
    print("re-run: python -m src.main --track t02 --output out/poc --run-name poc --offline --seed 42")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
