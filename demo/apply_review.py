"""Replay Minh's saved review only on its bound run; preserve v1 submission evidence.

Usage, from the repo root, after the offline PoC run:

    python -m src.main --config configs/lab.yaml --output out/minh-review --run-name minh_review --offline --seed 42
    python -m demo.apply_review
    python -m src.main --config configs/lab.yaml --output out/minh-review --run-name minh_review --offline --seed 42
"""
from __future__ import annotations

import argparse
import io
import os
from pathlib import Path
import tempfile

from src.team06.review_bundle import read_bound_review

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay recorded decisions after exact context validation")
    parser.add_argument("--run-dir", type=Path, default=Path("out/minh-review"))
    parser.add_argument("--bundle", type=Path, default=Path("demo/review_bundle.json"))
    parser.add_argument("--protocol", type=Path, default=Path("configs/review_protocol_v2.json"))
    args = parser.parse_args(argv)
    run_dir = ROOT / args.run_dir
    try:
        reviewed = read_bound_review(run_dir, ROOT / args.bundle, ROOT / args.protocol, ROOT)
        stream = io.StringIO(newline="")
        reviewed.to_csv(stream, index=False, lineterminator="\n")
        payload = stream.getvalue().encode("utf-8")
        destination = run_dir / "review_queue_reviewed.csv"
        if destination.exists():
            if destination.read_bytes() != payload:
                raise ValueError("Existing reviewed CSV differs; use a separate run directory, never overwrite human input")
        else:
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=run_dir, suffix=".tmp", delete=False) as handle:
                    temporary = Path(handle.name)
                    handle.write(payload)
                os.replace(temporary, destination)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Review replay rejected: {exc}")
        return 2
    filled = int(reviewed.reviewer_decision.ne("").sum())
    print(f"Replayed {filled}/{len(reviewed)} recorded decisions -> {destination}")
    print("This is replay, not a new human review. Re-run the same src.main command to apply and audit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
