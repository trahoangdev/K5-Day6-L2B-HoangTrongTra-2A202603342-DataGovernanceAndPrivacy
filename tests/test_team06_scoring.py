"""PoC calibration/config regressions. Synthetic features are not accuracy labels."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.common.context import RunContext
from src.team06 import scoring
from src.team06.features import FEATURE_COLUMNS


@pytest.fixture
def sample(tmp_path, monkeypatch):
    images = pd.DataFrame({
        "image_id": ["s0_0", "s0_1", "s1_0", "s1_1"],
        "path": [f"images/{i}.jpg" for i in range(4)], "camera_id": "cam_A", "light": "day",
        "split": ["dev", "dev", "eval", "eval"],
    })
    features = images.copy().assign(scene_id=["s0", "s0", "s1", "s1"])
    for column in FEATURE_COLUMNS:
        features[column] = 0.0
    features[["lap_var", "lap_tile_max", "lap_tile_p25", "lap_tile_median"]] = 1000.0
    features[["bright_mean", "bright_p05", "bright_p95", "bright_p99"]] = 180.0
    features["jpeg_blockiness"] = 1.0
    ctx = RunContext(track="t02", input_dir=Path(tmp_path), output_dir=tmp_path / "out",
                     config={"params": {"dev_split": "dev"}}, seed=42, rng=np.random.default_rng(42))
    monkeypatch.setattr(scoring, "extract_features", lambda ctx, images: features.copy())
    return ctx, images, features


def test_valid_scorer_contract_and_calibration_remain_dev_only(sample, monkeypatch):
    ctx, images, features = sample
    references = []
    original = scoring._session_references
    def capture(table, dev, params, ceiling):
        references.append((dev.image_id.tolist(), ceiling))
        return original(table, dev, params, ceiling)
    monkeypatch.setattr(scoring, "_session_references", capture)
    first = scoring.score_images(ctx, {"images": images})
    features.loc[features.split.eq("eval"), "lap_tile_max"] = 1e12
    second = scoring.score_images(ctx, {"images": images})
    assert references[0] == references[1]
    assert references[0][0] == ["s0_0", "s0_1"]
    assert set(first.image_id) == set(images.image_id)
    assert np.isfinite(first.score).all() and np.isfinite(second.score).all()
    assert first.pred_action.eq("KEEP").all()


def test_eval_only_input_fails_before_extracting_features(sample, monkeypatch):
    ctx, images, _ = sample
    def forbidden(*args):
        pytest.fail("Eval-only input reached feature extraction/calibration")
    monkeypatch.setattr(scoring, "extract_features", forbidden)
    with pytest.raises(ValueError, match="refusing to fit on eval-only"):
        scoring.score_images(ctx, {"images": images[images.split.eq("eval")]})


def test_eval_cannot_be_configured_as_the_calibration_split(sample):
    ctx, images, _ = sample
    ctx.config["params"]["dev_split"] = "eval"
    with pytest.raises(ValueError, match="dev_split=dev"):
        scoring.score_images(ctx, {"images": images})


@pytest.mark.parametrize("overrides", [
    {"weights": {"blur": float("nan")}},
    {"weights": {"blur": float("inf")}},
    {"weights": {"blur": -1}},
    {"weights": {"blur": True}},
    {"weights": {"wrong_name": 1}},
    {"weights": "invalid"},
    {"blur_drop_scale": 0},
    {"blur_drop_scale": -1},
    {"blur_drop_scale": float("inf")},
    {"glare_sat_floor": float("nan")},
    {"camera_ceiling_quantile": 1.2},
    {"keep_max": 0.7, "review_max": 0.6},
    {"min_group_size": True},
    {"min_group_size": 1.5},
    {"typo_parameter": 1},
    "invalid",
])
def test_invalid_scoring_config_is_not_converted_to_keep(sample, overrides):
    ctx, images, _ = sample
    ctx.config["params"]["scoring"] = overrides
    with pytest.raises(ValueError):
        scoring.score_images(ctx, {"images": images})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1.0])
def test_invalid_feature_is_not_converted_to_zero_score(sample, value):
    ctx, images, features = sample
    features.loc[0, "lap_tile_max"] = value
    with pytest.raises(ValueError, match="finite non-negative image features"):
        scoring.score_images(ctx, {"images": images})


def test_score_overflow_is_rejected_even_with_finite_weights(sample):
    ctx, images, features = sample
    ctx.config["params"]["scoring"] = {"weights": {name: 1e308 for name in scoring.DEFECT_TYPES}}
    features["bright_p95"] = 0.0
    features["dark_frac"] = 1.0
    features["sat_frac"] = 1.0
    features["jpeg_blockiness"] = 10.0
    with pytest.raises(ValueError, match="non-finite scores"):
        scoring.score_images(ctx, {"images": images})
