"""Local-only unlabelled BDD100K smoke test, using frozen dev references.

Prep (online): python -m tools.download_real_samples --packs bdd --bdd-n 10 --seed 42 --workers 4
Run (offline scoring): python -m tools.check_t02_ood
Never publishes real pixels, HTML contact sheets, or invented QC accuracy.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from src.common.manifest import build_manifest, verify_manifest, write_manifest
from tools.prepare_submission import ROOT, digest, run, verify_freeze, write_json


def main() -> None:
    os.chdir(ROOT)
    freeze = verify_freeze()
    source = Path("data/real/bdd")
    if verify_manifest(source / "manifest.csv"):
        raise ValueError("BDD source manifest did not verify")
    meta = pd.read_csv(source / "metadata.csv")
    if len(meta) != freeze["ood_plan"]["n"] or meta.file_id.duplicated().any():
        raise ValueError("Expected exactly 10 unique BDD samples from the preregistered sampler")
    work = Path("data/real/team06_ood_input")
    output = Path("data/real/team06_ood_output")
    (work / "images").mkdir(parents=True, exist_ok=True)
    fixture = Path("fixtures/t02_raw_qc")
    images = pd.read_csv(fixture / "images.csv")
    dev = images.loc[images.split.eq("dev")].copy()
    for row in dev.itertuples():
        shutil.copyfile(fixture / row.path, work / row.path)
    rows = []
    for row in meta.itertuples():
        # No known capture sessions/cameras: do not invent common peers for BDD.
        # Singleton unknown cameras force the existing global-dev fallbacks.
        item = f"bdd-{row.file_id}"
        path = f"images/{item}.jpg"
        shutil.copyfile(source / row.path, work / path)
        rows.append({"image_id": item, "path": path, "camera_id": f"unknown-{row.file_id}",
                     "light": {"daytime": "day", "dawn/dusk": "dusk", "night": "night"}.get(
                         row.timeofday, "unknown"), "split": "eval"})
    combined = pd.concat([dev, pd.DataFrame(rows)], ignore_index=True)
    combined.to_csv(work / "images.csv", index=False, lineterminator="\n")
    manifest = build_manifest(work, ["images.csv", *combined.path],
                              "BTC synthetic dev + hf:dgural/bdd100k (local OOD smoke test)",
                              "See source manifests; BDD100K research/education restrictions")
    write_manifest(manifest, work / "manifest.csv")
    run("-m", "src.main", "--config", "configs/submission.yaml", "--input", str(work),
        "--output", str(output), "--offline", "--seed", "42", "--run-name", "ood_smoke")
    predictions = pd.read_csv(output / "raw_predictions.csv")
    ood = predictions.loc[predictions.image_id.str.startswith("bdd-")].copy()
    if len(ood) != 10 or not np.isfinite(ood.score).all():
        raise ValueError("OOD scoring did not return 10 finite predictions")
    ood["source_file_id"] = ood.image_id.str.removeprefix("bdd-")
    ood = ood.merge(meta[["file_id", "weather", "timeofday", "scene"]],
                    left_on="source_file_id", right_on="file_id", validate="one_to_one")
    ood["resized_image_sha256"] = [digest(work / p) for p in ood.path]
    fields = ["image_id", "source_file_id", "weather", "timeofday", "scene", "score",
              "pred_defect_type", "pred_action", "reason", "resized_image_sha256"]
    ood[fields].to_csv("reports/submission/ood_scores.csv", index=False, lineterminator="\n")
    info = json.loads((output / "run_info.json").read_text(encoding="utf-8"))
    write_json(Path("reports/submission/ood_summary.json"), {
        "scope": "unlabelled_real_OOD_smoke_test_not_accuracy",
        "plan": freeze["ood_plan"], "source_manifest_sha256": digest(source / "manifest.csv"),
        "n_scored": len(ood), "n_dev_reference": len(dev), "seed": 42, "offline": True,
        "weather": meta.weather.value_counts().to_dict(),
        "timeofday": meta.timeofday.value_counts().to_dict(),
        "predicted_actions": ood.pred_action.value_counts().to_dict(),
        "predicted_types": ood.pred_defect_type.value_counts().to_dict(),
        "score_min": float(ood.score.min()), "score_max": float(ood.score.max()),
        "runtime_seconds_including_dev_reference": info["runtime_seconds"],
        "git_sha": info.get("git_sha"), "machine": info.get("machine"),
        "limitations": ["10 foggy images selected by unchanged rare-first sampler; not representative",
                        "No QC labels: recall, precision and false alarms are unknown",
                        "Unknown cameras/session IDs use singleton groups and frozen global-dev fallback",
                        "JPEG resized to max-side640/quality90 by existing prep, changing blockiness",
                        "Run now does not prove completion at historical +24h deadline"],
        "privacy": "Real images/contact sheets stay in gitignored data/real; only metadata/scores/hashes published",
    })
    print("Scored 10 real OOD images offline; metadata-only report written. No accuracy claim.")


if __name__ == "__main__":
    main()
