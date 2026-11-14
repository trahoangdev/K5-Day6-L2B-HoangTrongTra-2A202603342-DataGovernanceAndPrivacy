"""PoC scoring — Nguyễn Nhật Hạ, 2A202603325.

Turn per-image features into an explainable QC suspicion score. Higher score =
review first. Every image gets ``pred_defect_type`` in
{none, blur, glare, dark, compression} and ``pred_action`` in
{KEEP, REVIEW, RECAPTURE}.

Scoring strategy
----------------
1. Session-relative evidence (no labels):
   * sharpness is compared with the sharpest frame of the same session
     (blur is only meaningful relative to the camera/optics),
   * dark frames are compared with the median highlight level (p95) of the
     session, so a *usable* night frame (dark scene, bright lamps) is not
     mistaken for an underexposed frame,
   * compression is compared with the median 8x8 blockiness of the session.
2. Absolute evidence for glare, where physics is independent of the session:
   clipped/saturated blobs survive morphological erosion (lamps do not).
3. Camera-specific sharpness ceilings and global median fallbacks are frozen
   on the ``dev`` split only (``params.dev_split``), so a session without a
   sharp reference still gets a conservative estimate.
4. The final score is a weighted sum of the four defect severities plus a
   small bonus when independent cues agree.

All thresholds below were frozen on dev and are intentionally conservative:
a false alarm wastes one of the B=20 review slots, a missed mild defect only
loses a secondary metric point.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from ..common.context import RunContext
from .features import FEATURE_COLUMNS, extract_features

DEFECT_TYPES = ("blur", "glare", "dark", "compression")

DEFAULTS: dict = {
    "min_group_size": 2,
    "camera_ceiling_quantile": 0.90,
    # blur: log1p tile-sharpness drop
    "blur_drop_floor": 0.95,
    "blur_drop_scale": 1.4,
    "camera_drop_floor": 0.90,
    "camera_drop_scale": 1.2,
    # dark: log1p p95 highlight drop + absolute floors
    "dark_drop_floor": 0.45,
    "dark_drop_scale": 0.55,
    "dark_p95_floor": 50.0,
    "dark_p95_scale": 30.0,
    "dark_frac_floor": 0.72,
    "dark_frac_scale": 0.20,
    # glare: absolute saturated/bright blob fractions
    "glare_sat_floor": 0.0018,
    "glare_sat_scale": 0.0045,
    "glare_soft_floor": 0.0015,
    "glare_soft_scale": 0.012,
    "glare_core_floor": 0.004,
    "glare_core_scale": 0.05,
    # compression: block-boundary gradient excess
    "comp_block_floor": 0.30,
    "comp_block_scale": 0.9,
    "comp_abs_floor": 1.85,
    "comp_abs_scale": 1.1,
    "weights": {"blur": 1.0, "dark": 1.0, "glare": 1.05, "compression": 0.8},
    "multi_signal_floor": 0.20,
    "multi_signal_bonus": 0.15,
    # type assignment (specific cues win over generic sharpness loss)
    "type_floor": 0.30,
    "dark_type_floor": 0.50,
    "glare_type_floor": 0.35,
    "comp_type_floor": 0.45,
    # human actions
    "keep_max": 0.20,
    "review_max": 0.60,
}

OUTPUT_COLUMNS = [
    "image_id",
    "path",
    "camera_id",
    "light",
    "split",
    "score",
    "reason",
    "pred_defect_type",
    "pred_action",
]


def _clip01(values: np.ndarray | pd.Series) -> np.ndarray:
    return np.clip(np.asarray(values, dtype=float), 0.0, 1.0)


def _ramp(values, floor: float, scale: float) -> np.ndarray:
    """0 below `floor`, 1 at `floor + scale`, linear in between."""
    return _clip01((np.asarray(values, dtype=float) - floor) / float(scale))


def _resolve_params(ctx: RunContext) -> tuple[dict, str]:
    params = {**DEFAULTS, "weights": dict(DEFAULTS["weights"])}
    dev_split = str(ctx.param("dev_split", "dev"))
    if dev_split != "dev":
        raise ValueError("T02 calibration must use dev_split=dev; eval cannot be used for fitting")
    overrides = ctx.param("scoring", None)
    if overrides is None:
        overrides = {}
    if not isinstance(overrides, dict):
        raise ValueError("params.scoring must be a mapping")
    unknown = set(overrides) - set(DEFAULTS)
    if unknown:
        raise ValueError(f"Unknown scoring parameters: {sorted(unknown)}")
    for key, value in overrides.items():
        if key == "weights":
            if not isinstance(value, dict) or set(value) - set(DEFECT_TYPES):
                raise ValueError("scoring.weights must map known defect types to finite non-negative numbers")
            params["weights"] = {**params["weights"], **value}
        else:
            params[key] = value

    group_size = params["min_group_size"]
    if isinstance(group_size, bool) or not isinstance(group_size, int) or group_size < 1:
        raise ValueError("scoring.min_group_size must be a positive integer")
    for key, value in params.items():
        if key in {"weights", "min_group_size"}:
            continue
        params[key] = _finite_nonnegative(value, f"scoring.{key}")
        if key.endswith("_scale") and params[key] == 0:
            raise ValueError(f"scoring.{key} must be positive")
    params["weights"] = {name: _finite_nonnegative(value, f"scoring.weights.{name}")
                         for name, value in params["weights"].items()}
    if not 0 <= params["camera_ceiling_quantile"] <= 1:
        raise ValueError("scoring.camera_ceiling_quantile must be in [0, 1]")
    if params["keep_max"] >= params["review_max"]:
        raise ValueError("scoring.keep_max must be less than scoring.review_max")
    return params, dev_split


def _finite_nonnegative(value, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite non-negative number") from exc
    if isinstance(value, (bool, np.bool_)) or not np.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return number


def _session_references(features: pd.DataFrame, dev: pd.DataFrame, params: dict,
                        global_ceiling: float) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Per-session reference levels; dev-frozen fallbacks for tiny sessions."""
    sizes = features.groupby("scene_id")["image_id"].transform("size")
    enough = sizes >= int(params["min_group_size"])
    sharp_ref = features.groupby("scene_id")["log_tile_max"].transform("max")
    bright_ref = features.groupby("scene_id")["log_p95"].transform("median")
    block_ref = features.groupby("scene_id")["jpeg_blockiness"].transform("median")

    bright_fallback = float(dev["log_p95"].median())
    block_fallback = float(dev["jpeg_blockiness"].median())
    sharp_ref = sharp_ref.where(enough, global_ceiling)
    bright_ref = bright_ref.where(enough, bright_fallback)
    block_ref = block_ref.where(enough, block_fallback)
    return sharp_ref.astype(float), bright_ref.astype(float), block_ref.astype(float)


def _defect_type(signals: dict[str, np.ndarray], index: int, params: dict) -> str:
    # Specific, physically meaningful cues take precedence over generic
    # sharpness loss (strong JPEG/glare also destroy tile detail).
    if signals["dark"][index] >= params["dark_type_floor"]:
        return "dark"
    if signals["glare"][index] >= params["glare_type_floor"]:
        return "glare"
    if signals["compression"][index] >= params["comp_type_floor"]:
        return "compression"
    best = max(DEFECT_TYPES, key=lambda name: signals[name][index])
    return best if signals[best][index] >= params["type_floor"] else "none"


def _reason(signals: dict[str, np.ndarray], evidence: dict[str, np.ndarray],
            index: int, params: dict) -> str:
    entries = []
    if signals["blur"][index] > 0.10:
        entries.append((signals["blur"][index], f"blur(tile_drop={evidence['sharp_drop'][index]:.2f})"))
    if signals["dark"][index] > 0.10:
        entries.append((signals["dark"][index], f"dark(p95_drop={evidence['bright_drop'][index]:.2f})"))
    if signals["glare"][index] > 0.10:
        entries.append((signals["glare"][index],
                        f"glare(sat={evidence['sat_frac'][index]:.4f},blob={evidence['soft_blob'][index]:.4f})"))
    if signals["compression"][index] > 0.10:
        entries.append((signals["compression"][index], f"compression(block_rise={evidence['block_rise'][index]:.2f})"))
    entries.sort(key=lambda item: item[0], reverse=True)
    return "; ".join(text for _, text in entries[:3]) if entries else "no defect signal vs session reference"


def _action(score: float, params: dict) -> str:
    if score < params["keep_max"]:
        return "KEEP"
    if score < params["review_max"]:
        return "REVIEW"
    return "RECAPTURE"


def score_images(ctx: RunContext, data: dict) -> pd.DataFrame:
    """Score data['images']; tune only on dev and preserve all original IDs/splits."""
    if ctx.track != "t02":
        raise ValueError("Team 6 PoC supports T02 only")
    images = data.get("images")
    if images is None or images.empty:
        raise ValueError("T02 scoring requires data['images'] with at least one row")

    params, dev_split = _resolve_params(ctx)
    if not images["split"].eq(dev_split).any():
        raise ValueError("T02 scoring requires dev images for calibration; refusing to fit on eval-only input")
    started = time.perf_counter()
    features = extract_features(ctx, images)
    numeric = features[FEATURE_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(numeric).all() or (numeric < 0).any():
        raise ValueError("T02 scoring requires finite non-negative image features")
    features["log_tile_max"] = np.log1p(features["lap_tile_max"])
    features["log_p95"] = np.log1p(features["bright_p95"])
    features["log_sat"] = np.log1p(features["sat_frac"])

    dev = features[features["split"] == dev_split]
    if dev.empty:
        raise ValueError("T02 feature table has no dev rows; calibration cannot fall back to eval")
    global_ceiling = float(dev["log_tile_max"].quantile(float(params["camera_ceiling_quantile"])))
    camera_ceiling = dev.groupby("camera_id")["log_tile_max"].quantile(float(params["camera_ceiling_quantile"]))
    camera_ref = features["camera_id"].map(camera_ceiling).astype(float).fillna(global_ceiling)

    sharp_ref, bright_ref, block_ref = _session_references(features, dev, params, global_ceiling)

    sharp_drop = np.clip(sharp_ref.to_numpy() - features["log_tile_max"].to_numpy(), 0.0, None)
    bright_drop = np.clip(bright_ref.to_numpy() - features["log_p95"].to_numpy(), 0.0, None)
    block_rise = np.clip(features["jpeg_blockiness"].to_numpy() - block_ref.to_numpy(), 0.0, None)

    # --- blur: relative to the sharpest session frame, plus camera ceiling
    blur_s = np.maximum(
        _ramp(sharp_drop, params["blur_drop_floor"], params["blur_drop_scale"]),
        _ramp(camera_ref.to_numpy() - features["log_tile_max"].to_numpy(),
              params["camera_drop_floor"], params["camera_drop_scale"]),
    )
    # --- dark: relative highlight drop, with absolute clip fallbacks
    dark_s = np.maximum.reduce([
        _ramp(bright_drop, params["dark_drop_floor"], params["dark_drop_scale"]),
        _ramp(params["dark_p95_floor"] - features["bright_p95"].to_numpy(),
              0.0, params["dark_p95_scale"]),
        _ramp(features["dark_frac"].to_numpy(), params["dark_frac_floor"], params["dark_frac_scale"]),
    ])
    # --- glare: absolute saturated/bright blobs (erosion removes thin lamps)
    glare_s = np.maximum.reduce([
        _ramp(features["sat_frac"].to_numpy(), params["glare_sat_floor"], params["glare_sat_scale"]),
        _ramp(features["glare_soft_blob_frac"].to_numpy(), params["glare_soft_floor"], params["glare_soft_scale"]),
        _ramp(features["glare_blob_frac"].to_numpy(), params["glare_core_floor"], params["glare_core_scale"]),
    ])
    # --- compression: 8x8 block-boundary excess, relative + absolute
    compression_s = np.maximum(
        _ramp(block_rise, params["comp_block_floor"], params["comp_block_scale"]),
        _ramp(features["jpeg_blockiness"].to_numpy(), params["comp_abs_floor"], params["comp_abs_scale"]),
    )

    signals = {"blur": blur_s, "dark": dark_s, "glare": glare_s, "compression": compression_s}
    weights = params["weights"]
    with np.errstate(over="ignore", invalid="ignore"):
        score = sum(float(weights[name]) * signals[name] for name in DEFECT_TYPES)
        strong = sum((signals[name] >= params["multi_signal_floor"]).astype(int) for name in DEFECT_TYPES)
        score = score + params["multi_signal_bonus"] * np.maximum(strong - 1, 0)
    if not np.isfinite(score).all():
        raise ValueError("T02 scoring produced non-finite scores; refusing to replace them with KEEP")
    score = np.clip(score, 0.0, None)

    evidence = {
        "sharp_drop": sharp_drop,
        "bright_drop": bright_drop,
        "block_rise": block_rise,
        "sat_frac": features["sat_frac"].to_numpy(),
        "soft_blob": features["glare_soft_blob_frac"].to_numpy(),
    }

    scored = features[["image_id", "path", "camera_id", "light", "split"]].copy()
    scored["score"] = np.round(score, 6)
    scored["pred_defect_type"] = [_defect_type(signals, i, params) for i in range(len(features))]
    scored["pred_action"] = [_action(float(score[i]), params) for i in range(len(features))]
    scored["reason"] = [_reason(signals, evidence, i, params) for i in range(len(features))]

    if scored[["image_id", "score"]].isna().any().any() or not np.isfinite(scored["score"]).all():
        raise ValueError("T02 scoring produced non-finite scores or missing image_id")
    if scored["image_id"].duplicated().any():
        raise ValueError("T02 scoring produced duplicate image_id rows")

    elapsed = time.perf_counter() - started
    ctx.stats["t02_ms_per_image"] = round(1000.0 * elapsed / max(len(scored), 1), 3)
    ctx.stats["t02_flagged"] = int((scored["score"] >= params["keep_max"]).sum())
    return scored[OUTPUT_COLUMNS]
