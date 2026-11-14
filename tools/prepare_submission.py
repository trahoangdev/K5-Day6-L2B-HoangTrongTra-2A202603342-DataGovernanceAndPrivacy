"""Generate Team 6 evidence with the unchanged instructor runner/evaluator.

    python -m tools.prepare_submission

Uses existing dev-only internal labels. NEVER substitutes these for official GT.
Human decisions must be supplied separately; this tool never approves a review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pandas as pd

from src.common.report import compare_runs

ROOT = Path(__file__).resolve().parents[1]
CONFIG = "configs/submission.yaml"
EVIDENCE = Path("reports/submission")
RUNS = Path("out/submission")
SCOPE = "internal_dev_in_sample_not_official"


def digest(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_freeze() -> dict:
    freeze = json.loads(Path("configs/protocol_freeze.json").read_text(encoding="utf-8"))
    changed = [p for p, expected in freeze["sha256"].items() if digest(p) != expected]
    if changed:
        raise ValueError(f"Frozen inputs changed; create a new protocol version first: {changed}")
    return freeze


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], check=True, cwd=ROOT,
                   env={**os.environ, "PYTHONIOENCODING": "utf-8"})


def write_json(path: Path, data: dict) -> None:
    def clean(value):
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items()}
        if isinstance(value, list):
            return [clean(v) for v in value]
        return None if isinstance(value, float) and not math.isfinite(value) else value

    # The shared evaluator emits NaN for undefined slice cells; publish JSON null.
    path.write_text(json.dumps(clean(data), ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8", newline="\n")


def internal_gt() -> pd.DataFrame:
    images = pd.read_csv("fixtures/t02_raw_qc/images.csv")
    labels = pd.read_csv("reports/internal_labels_t02_final.csv")
    dev = images.loc[images.split.eq("dev")]
    if labels.image_id.duplicated().any() or set(labels.image_id) != set(dev.image_id):
        raise ValueError("Internal labels must cover each dev ID exactly once and no eval IDs")
    if not labels.is_defect.isin([0, 1]).all():
        raise ValueError("Unresolved internal labels")
    expected = labels.defect_type.isin(["blur", "glare", "dark", "compression"]).astype(int)
    if not expected.eq(labels.is_defect).all() or not labels.defect_type.isin(
            ["none", "blur", "glare", "dark", "compression"]).all():
        raise ValueError("Internal label class mapping is inconsistent")
    return dev.merge(labels, on="image_id", validate="one_to_one")


def wilson(hits: int, n: int) -> list[float | None]:
    """Descriptive only: related frames and dev tuning preclude generalization CI."""
    if n == 0:
        return [None, None]
    z = 1.959963984540054
    rate = hits / n
    denom = 1 + z * z / n
    center = (rate + z * z / (2 * n)) / denom
    half = z * math.sqrt(rate * (1 - rate) / n + z * z / (4 * n * n)) / denom
    return [max(0.0, center - half), min(1.0, center + half)]


def slices(gt: pd.DataFrame, predictions: pd.DataFrame, name: str) -> list[dict]:
    pred = predictions.loc[predictions.image_id.isin(gt.image_id)].sort_values(
        ["score", "image_id"], ascending=[False, True], kind="stable")
    top = set(pred.head(20).image_id)
    rows = []
    for column in ("light", "camera_id", "defect_type"):
        for value, group in gt.groupby(column):
            positive = group.is_defect.eq(1)
            selected = group.image_id.isin(top)
            tp = int((positive & selected).sum())
            fp = int((~positive & selected).sum())
            npos, nneg = int(positive.sum()), int((~positive).sum())
            rows.append({"run": name, "scope": SCOPE, "slice": f"{column}={value}",
                         "n": len(group), "positives": npos, "negatives": nneg,
                         "hits_in_global_dev_top20": tp, "false_alarms": fp,
                         "recall": tp / npos if npos else None,
                         "false_alarm_rate": fp / nneg if nneg else None})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-confirmed-review", action="store_true",
                        help="Replay the recorded human decisions only after exact raw-score/queue matching")
    args = parser.parse_args()
    os.chdir(ROOT)
    freeze = verify_freeze()
    confirmed_raw = (pd.read_csv(EVIDENCE / "poc/raw_predictions.csv")
                     if args.replay_confirmed_review else None)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    gt = internal_gt()
    gt_path = EVIDENCE / "internal_dev_labels_joined.csv"
    gt.to_csv(gt_path, index=False, lineterminator="\n")
    run("-m", "tools.verify_manifests")
    all_slices, intervals = [], {}
    for name, pipeline in (("baseline", "src.team06.baseline"), ("poc", "src.pipeline")):
        output = RUNS / name
        run("-m", "src.main", "--config", CONFIG, "--pipeline", pipeline,
            "--output", str(output), "--offline", "--seed", "42", "--run-name", name)
        if name == "poc" and args.replay_confirmed_review:
            current = pd.read_csv(output / "raw_predictions.csv")
            pd.testing.assert_frame_equal(current, confirmed_raw, check_exact=True)
            confirmation = json.loads((EVIDENCE / "review_confirmation.json").read_text(encoding="utf-8"))
            human = pd.read_csv("reports/review_queue.csv", keep_default_na=False)
            if list(human.item_id) != confirmation["item_ids"] or not human.reviewer.eq(
                    confirmation["confirmed_by"]).all():
                raise ValueError("Human review differs from its recorded confirmation")
            reviewed_path = output / "review_queue_reviewed.csv"
            if reviewed_path.exists():
                pd.testing.assert_frame_equal(pd.read_csv(reviewed_path, keep_default_na=False), human)
            else:
                human.to_csv(reviewed_path, index=False, lineterminator="\n")
                # First run established current binding; policy validates immutable queue fields.
                run("-m", "src.main", "--config", CONFIG, "--pipeline", pipeline,
                    "--output", str(output), "--offline", "--seed", "42", "--run-name", name)
        metric_path = Path(f"reports/metrics_{name}.json")
        run("-m", "src.evaluate", "--track", "t02", "--config", CONFIG,
            "--gt", str(gt_path), "--pred", str(output / "ranked_review.csv"),
            "--split", "dev", "--budget", "20", "--run-name", f"{name}_internal_dev",
            "--out", str(metric_path))
        data = json.loads(metric_path.read_text(encoding="utf-8"))
        data["extra"].update({"scope": SCOPE, "official": False,
                              "label_sha256": digest("reports/internal_labels_t02_final.csv"),
                              "freeze_sha256": digest("configs/protocol_freeze.json"),
                              "warning": "Same dev set used during design; not heldout accuracy. "
                                         "Inherited evaluator note 'eval N' refers to --split dev here."})
        write_json(metric_path, data)
        intervals[name] = {m["name"]: {"numerator": m["numerator"], "denominator": m["denominator"],
                                      "wilson95": wilson(int(m["numerator"]), int(m["denominator"]))}
                           for m in data["metrics"] if m["name"] in {"Defect Recall@B", "Precision@B"}}
        predictions = pd.read_csv(output / "raw_predictions.csv")
        all_slices.extend(slices(gt, predictions, name))
        destination = EVIDENCE / name
        destination.mkdir(exist_ok=True)
        # Synthetic fixture evidence only. No image-bearing HTML or real-data output is copied.
        for filename in ("raw_predictions.csv", "review_queue.csv", "image_decisions.csv",
                         "decision.json", "run_info.json", "review_context.json", "policy_snapshot.json",
                         "audit_log.jsonl", "decision_log.csv"):
            shutil.copyfile(output / filename, destination / filename)
    pd.DataFrame(all_slices).to_csv(EVIDENCE / "slices.csv", index=False, lineterminator="\n")
    write_json(EVIDENCE / "uncertainty.json", {
        "scope": SCOPE, "method": freeze["uncertainty"], "intervals": intervals})
    table = compare_runs("reports/metrics_baseline.json", "reports/metrics_poc.json")
    Path("reports/table1_baseline_vs_poc.md").write_text(
        "# Internal dev comparison — NOT official heldout evaluation\n\n"
        "56 dev images, internal AI-assisted labels; design observed this dev set. B=20, seed=42.\n"
        "Review queue uses all 96 images; metrics first filter to 56 dev images.\n\n" + table + "\n",
        encoding="utf-8", newline="\n")
    print("Evidence generated. Existing human decisions may be applied; no new review was auto-approved.")


if __name__ == "__main__":
    main()
