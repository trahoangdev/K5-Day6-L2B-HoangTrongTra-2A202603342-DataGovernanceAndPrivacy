
"""Laplacian baseline — Phạm Văn Dương, 2A202603332.

Single global whole-image Laplacian threshold baseline.
Threshold is selected from the dev-set distribution and frozen.
Higher score means higher suspicion and higher review priority.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..common.context import RunContext
from ..common.image_ops import load_rgb, laplacian_variance


def score_baseline(ctx: RunContext, data: dict) -> pd.DataFrame:
    """Calculate Laplacian variance and rank suspicious images."""

    images = data["images"]

    # Read frozen threshold from T02 configuration
    threshold = float(ctx.param("laplacian_threshold", 186.8550))

    if not np.isfinite(threshold) or threshold <= 0:
        raise ValueError("laplacian_threshold must be a positive finite number")

    results = []

    for _, row in images.iterrows():
        image_path = ctx.input_dir / row["path"]

        # Load image and calculate whole-image Laplacian variance
        img = load_rgb(image_path)
        variance = laplacian_variance(img)

        if not np.isfinite(variance):
            raise ValueError(
                f"Invalid Laplacian variance for image {row['image_id']}"
            )

        # Lower variance means higher suspicion
        score = -variance

        suspected_blur = variance < threshold

        results.append({
            "image_id": row["image_id"],
            "path": row["path"],
            "camera_id": row["camera_id"],
            "light": row["light"],
            "split": row["split"],
            "laplacian_variance": variance,
            "score": score,
            "reason": (
                "low_laplacian_variance"
                if suspected_blur
                else "normal_laplacian_variance"
            ),
            "pred_defect_type": (
                "blur" if suspected_blur else "none"
            ),
            "pred_action": (
                "REVIEW" if suspected_blur else "KEEP"
            ),
        })

    scored = pd.DataFrame(results)

    # Preserve all input images and IDs
    if len(scored) != len(images):
        raise ValueError("Baseline must return one row per input image")

    if scored["image_id"].duplicated().any():
        raise ValueError("Duplicate image_id detected")

    if not np.isfinite(scored["score"]).all():
        raise ValueError("Baseline produced non-finite scores")

    # Record baseline information
    ctx.stats["baseline_threshold"] = threshold
    ctx.stats["baseline_method"] = "global_laplacian_variance"
    ctx.stats["baseline_n_suspected_blur"] = int(
        (scored["laplacian_variance"] < threshold).sum()
    )

    return scored


def run(ctx: RunContext) -> None:
    """Entry point for src.main --pipeline src.team06.baseline."""
    if ctx.track != "t02":
        raise ValueError("Team 6 baseline supports T02 only")

    from ..pipeline import run_pipeline

    run_pipeline(ctx, scorer=score_baseline)
