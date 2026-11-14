"""Team 6 T02 data, baseline, and end-to-end contract tests."""

import json

import numpy as np
import pandas as pd
import pytest
from PIL import Image

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
