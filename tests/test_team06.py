"""Team 6 T02 data, baseline, and end-to-end contract tests."""

import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest
import yaml
from PIL import Image, ImageFilter

from src.common.context import RunContext
from src.common.manifest import build_manifest, write_manifest
from src.team06 import baseline
from src.team06.data import IMAGE_COLUMNS, leaking_scenes, load_inputs, summarise_strata
from src.team06.integration import run_t02
from src.team06.policy import POLICY_VERSION


@pytest.fixture
def ctx(tmp_path):
    """Small, valid T02 fixture that does not depend on mutable lab fixtures."""
    input_dir = tmp_path / "input"
    (input_dir / "images").mkdir(parents=True)
    rows = []
    for index in range(4):
        path = f"images/i{index}.jpg"
        Image.new("RGB", (32, 18), (40 + index * 30, 60, 80)).save(input_dir / path)
        rows.append(
            {
                "image_id": f"scene{index}_0",
                "path": path,
                "camera_id": "cam_A",
                "light": "day" if index < 2 else "night",
                "split": "dev" if index < 2 else "eval",
            }
        )
    pd.DataFrame(rows).to_csv(input_dir / "images.csv", index=False)
    write_manifest(
        build_manifest(input_dir, ["images.csv", *(row["path"] for row in rows)], "synthetic:test", "CC0"),
        input_dir / "manifest.csv",
    )
    config = {
        "track": "t02",
        "group_id": "G06",
        "owner": "Synthetic test owner",
        "seed": 42,
        "offline": True,
        "strict_provenance": True,
        "params": {
            "budget": 2,
            "dev_split": "dev",
            "review_split": "all",
            "policy_version": POLICY_VERSION,
            "laplacian_threshold": 186.8550,
        },
    }
    return RunContext(
        track="t02",
        input_dir=input_dir,
        output_dir=tmp_path / "out",
        config=config,
        seed=42,
        rng=np.random.default_rng(42),
    )


@pytest.fixture
def textured_ctx(ctx):
    """Sharp/blurred image pairs with real edges, not constant-color zero-variance images."""
    yy, xx = np.indices((72, 128))
    pixels = (25 + 200 * ((xx // 4 + yy // 4) % 2)).astype(np.uint8)
    sharp = Image.fromarray(pixels).convert("RGB")
    blurred = sharp.filter(ImageFilter.GaussianBlur(radius=3))
    images = pd.read_csv(ctx.input_dir / "images.csv")
    for index, row in enumerate(images.itertuples(index=False)):
        image = sharp if index % 2 == 0 else blurred
        image.save(ctx.input_dir / row.path, quality=95)
    write_manifest(
        build_manifest(ctx.input_dir, ["images.csv", *images.path], "synthetic:test", "CC0"),
        ctx.input_dir / "manifest.csv",
    )
    return ctx


def test_load_inputs_preserves_schema_splits_and_provenance(ctx):
    data = load_inputs(ctx)
    images = data["images"]

    assert list(images.columns[: len(IMAGE_COLUMNS)]) == IMAGE_COLUMNS
    assert len(images) == 4
    assert images.split.value_counts().to_dict() == {"dev": 2, "eval": 2}
    assert images.image_id.is_unique
    assert ctx.input_dir.joinpath("manifest.csv").is_file()


def test_load_inputs_rejects_tampered_metadata(ctx):
    images_path = ctx.input_dir / "images.csv"
    images = pd.read_csv(images_path)
    images.loc[0, "camera_id"] = "tampered-camera"
    images.to_csv(images_path, index=False)

    with pytest.raises(ValueError, match="provenance check failed"):
        load_inputs(ctx)


def test_load_inputs_rejects_missing_required_metadata(ctx):
    images_path = ctx.input_dir / "images.csv"
    images = pd.read_csv(images_path).drop(columns=["camera_id"])
    images.to_csv(images_path, index=False)
    ctx.config["strict_provenance"] = False

    with pytest.raises(ValueError, match="missing required columns"):
        load_inputs(ctx)


def test_data_audit_detects_strata_and_scene_leakage(ctx):
    images = load_inputs(ctx)["images"]
    strata = summarise_strata(images)

    assert strata.loc[("cam_A", "day"), "dev"] == 2
    assert strata.loc[("cam_A", "night"), "eval"] == 2
    assert leaking_scenes(images) == []


def test_baseline_pipeline_writes_current_t02_outputs(ctx):
    run_t02(ctx, scorer=baseline.score_baseline)

    raw = pd.read_csv(ctx.output_dir / "raw_predictions.csv")
    ranked = pd.read_csv(ctx.output_dir / "ranked_review.csv")
    queue = pd.read_csv(ctx.output_dir / "review_queue.csv")
    info = json.loads((ctx.output_dir / "decision.json").read_text(encoding="utf-8"))

    assert len(raw) == len(ranked) == 4
    assert len(queue) == 2
    assert set(raw["image_id"]) == set(ranked["image_id"])
    assert ranked["score"].map(np.isfinite).all()
    assert set(ranked["pred_action"]) <= {"KEEP", "REVIEW", "RECAPTURE"}
    assert {"review_status", "reason_code", "action_owner"} <= set(ranked.columns)
    assert info["status"] == "HOLD"
    assert info["reason_code"] == "REVIEW_PENDING"


def test_baseline_is_deterministic_and_preserves_all_images(ctx):
    run_t02(ctx, scorer=baseline.score_baseline)
    first = (ctx.output_dir / "raw_predictions.csv").read_bytes()

    run_t02(ctx, scorer=baseline.score_baseline)
    second = (ctx.output_dir / "raw_predictions.csv").read_bytes()

    assert first == second
    assert json.loads((ctx.output_dir / "review_context.json").read_text())["queue_ids"]


def test_baseline_rejects_invalid_frozen_threshold(ctx):
    ctx.config["params"]["laplacian_threshold"] = 0

    with pytest.raises(ValueError, match="positive finite"):
        run_t02(ctx, scorer=baseline.score_baseline)

    assert not (ctx.output_dir / "ranked_review.csv").exists()
    decision = json.loads((ctx.output_dir / "decision.json").read_text(encoding="utf-8"))
    assert decision["status"] == "HOLD"
    assert decision["reason_code"] == "RUN_FAILED"


def test_baseline_cli_runs_real_entrypoint_and_records_run_info(textured_ctx, tmp_path):
    ctx = textured_ctx
    config = tmp_path / "cli_config.yaml"
    config.write_text(yaml.safe_dump(ctx.config, allow_unicode=True), encoding="utf-8")
    command = [
        sys.executable, "-m", "src.main", "--track", "t02", "--pipeline", "src.team06.baseline",
        "--config", str(config), "--input", str(ctx.input_dir), "--output", str(ctx.output_dir),
        "--run-name", "baseline", "--offline", "--seed", "42",
    ]
    result = subprocess.run(
        command, cwd=Path(__file__).resolve().parents[1], capture_output=True,
        text=True, encoding="utf-8", timeout=30, env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for filename in (
        "raw_predictions.csv", "ranked_review.csv", "review_queue.csv", "contact_sheet.html",
        "image_decisions.csv", "decision.json", "decision_log.csv", "audit_log.jsonl", "run_info.json",
    ):
        assert (ctx.output_dir / filename).is_file(), filename
    info = json.loads((ctx.output_dir / "run_info.json").read_text(encoding="utf-8"))
    assert info["status"] == 0
    assert info["pipeline"] == "src.team06.baseline"
    assert info["run_name"] == "baseline" and info["seed"] == 42 and info["offline"] is True
    assert info["stats"]["n_items"] == 4 and info["stats"]["n_queued"] == 2
    assert info["output_check"]["exists"] and info["output_check"]["missing_columns"] == []
    assert info["stats"]["decision_status"] == "HOLD"  # successful CLI, pending human review
    ranked = pd.read_csv(ctx.output_dir / "ranked_review.csv")
    assert set(ranked.image_id) == set(load_inputs(ctx)["images"].image_id)
    assert ranked.image_id.is_unique and np.isfinite(ranked.score).all()


def test_baseline_prioritizes_blurred_images_over_sharp_images(textured_ctx):
    ctx = textured_ctx
    run_t02(ctx, scorer=baseline.score_baseline)
    raw = pd.read_csv(ctx.output_dir / "raw_predictions.csv").set_index("image_id")
    for sharp_id, blurred_id in (("scene0_0", "scene1_0"), ("scene2_0", "scene3_0")):
        assert raw.loc[blurred_id, "score"] > raw.loc[sharp_id, "score"]
        assert raw.loc[blurred_id, "pred_defect_type"] == "blur"
        assert raw.loc[sharp_id, "pred_defect_type"] == "none"
        assert raw.loc[blurred_id, "pred_action"] == "REVIEW"
        assert raw.loc[sharp_id, "pred_action"] == "KEEP"
    queue = pd.read_csv(ctx.output_dir / "review_queue.csv")
    assert set(queue.item_id) == {"scene1_0", "scene3_0"}
