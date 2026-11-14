"""Data & Provenance — Nguyễn Quốc Hưng, 2A202603324.

Loader + provenance guards for T02.

`load_inputs` verifies the manifest and the images.csv schema, then returns both
splits. `summarise_strata` reports the (camera, light) x split coverage the rest
of the team needs before choosing a normalisation grouping — see
reports/group_report.md.

Never read instructor ground truth or rewrite fixture manifests to hide errors.
"""
from __future__ import annotations

import pandas as pd

from ..common.context import RunContext
from ..common.manifest import verify_manifest

IMAGE_COLUMNS = ["image_id", "path", "camera_id", "light", "split"]


def load_inputs(ctx: RunContext) -> dict:
    """Return {manifest: DataFrame | None, images: DataFrame} for T02.

    Image paths remain relative to ctx.input_dir; both dev and eval are retained.
    Threshold fitting must use dev only, not the complete returned table.
    """
    if ctx.track != "t02":
        raise ValueError("Team 6 load_inputs supports T02 only")
    manifest = ctx.input_dir / "manifest.csv"
    problems = verify_manifest(manifest) if manifest.exists() else [{"problem": "no_manifest"}]
    if problems:
        if ctx.audit is not None:
            ctx.audit.log(actor="pipeline", action="provenance_problems", item_id=str(manifest), after=problems[:20])
        if ctx.config.get("strict_provenance", True):
            raise ValueError(f"provenance check failed ({len(problems)} problems), first: {problems[:3]}")

    images = pd.read_csv(ctx.input_dir / "images.csv", dtype={"image_id": str})
    missing = [c for c in IMAGE_COLUMNS if c not in images.columns]
    if missing:
        raise ValueError(f"images.csv missing required columns: {missing}")
    if images[IMAGE_COLUMNS].isna().any().any():
        raise ValueError("images.csv contains missing required metadata")
    if images.image_id.duplicated().any():
        raise ValueError("images.csv contains duplicate image_id values")
    if not images.split.isin(["dev", "eval"]).all():
        raise ValueError("T02 split must be dev or eval")
    return {"manifest": pd.read_csv(manifest) if manifest.exists() else None, "images": images}


SCENE_SEP = "_"


def scene_of(image_id: pd.Series) -> pd.Series:
    """`img_07_2` -> `img_07`. The 4 variants of one scene share an original."""
    return image_id.str.rsplit(SCENE_SEP, n=1).str[0]


def summarise_strata(images: pd.DataFrame) -> pd.DataFrame:
    """Images per (camera_id, light) x split.

    Why this matters: thresholds may only be fitted on `dev`, so any stratum that
    exists at eval but not at dev cannot get its own calibrated threshold. On the
    shipped fixture that is `cam_A/night` — 0 dev, 8 eval, i.e. 20% of the eval
    split. Normalising per (camera_id, light) therefore leaves a blind spot;
    per `camera_id` alone is covered on both sides.
    """
    cross = pd.crosstab([images.camera_id, images.light], images.split)
    for split in ("dev", "eval"):
        if split not in cross.columns:
            cross[split] = 0
    return cross


def uncalibratable_strata(images: pd.DataFrame) -> list[str]:
    """Strata present at eval with no dev example. Empty list = safe to stratify."""
    cross = summarise_strata(images)
    gap = cross[(cross["eval"] > 0) & (cross["dev"] == 0)]
    return sorted(f"{camera}/{light}" for camera, light in gap.index)


def leaking_scenes(images: pd.DataFrame) -> list[str]:
    """Original scenes appearing in both splits — near-duplicate leakage. Expected: []."""
    per_scene = images.assign(scene=scene_of(images.image_id)).groupby("scene")["split"].nunique()
    return sorted(per_scene[per_scene > 1].index)
