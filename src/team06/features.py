"""Image features — Nguyễn Nhật Hạ, 2A202603325.

Per-image QC features for T02 (blur, dark, glare, compression). Features are
computed on local files only; ground truth is never read.

Design notes
------------
* Sharpness uses the *maximum* 4x4-tile Laplacian variance instead of the
  whole-image variance: a sharp image always has at least one detailed region,
  whereas global variance is diluted by flat sky/road and rewards JPEG ringing.
* Glare is a spatial signal. A bright blob is only suspicious when it survives
  morphological erosion (thin night lamps disappear), so we measure the largest
  connected component of eroded saturated/bright masks rather than raw pixel
  counts.
* Compression uses the classic 8x8 JPEG grid: gradient energy on block
  boundaries divided by gradient energy inside blocks.
* ``scene_id`` groups frames of the same capture session; scoring compares an
  image against its session peers (no labels involved). It is derived from the
  trailing ``_<frame>`` of ``image_id`` and falls back to camera+light.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import binary_erosion, convolve, label

from ..common import image_ops
from ..common.context import RunContext

_LAPLACE = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
_TILE_GRID = 4
_SAT_LEVEL = 245          # gray value treated as clipped/blown out
_SOFT_BRIGHT = 235        # wide glare halo (before clipping)
_BLOCK = 8                # JPEG block size
_EIGHT_CONNECTED = np.ones((3, 3), dtype=bool)

FEATURE_COLUMNS = [
    "lap_var",
    "lap_tile_max",
    "lap_tile_p25",
    "lap_tile_median",
    "bright_mean",
    "bright_p05",
    "bright_p95",
    "bright_p99",
    "dark_frac",
    "clip_dark_frac",
    "sat_frac",
    "sat_any_frac",
    "glare_blob_frac",
    "glare_soft_blob_frac",
    "jpeg_blockiness",
]


def _scene_key(image_id: str, camera_id: str, light: str) -> str:
    match = re.match(r"^(.*)_\d+$", str(image_id))
    return match.group(1) if match else f"{camera_id}|{light}"


def _largest_component_fraction(mask: np.ndarray, min_iters: int) -> float:
    """Largest connected blob fraction after eroding thin structures."""
    core = binary_erosion(mask, iterations=min_iters, border_value=0) if min_iters else mask
    if not core.any():
        return 0.0
    labels, n = label(core, structure=_EIGHT_CONNECTED)
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    return float(sizes.max() / mask.size) if n else 0.0


def _tile_sharpness(gray: np.ndarray) -> tuple[float, float, float]:
    height, width = gray.shape
    if height < _TILE_GRID * 4 or width < _TILE_GRID * 4:
        value = float(convolve(gray, _LAPLACE, mode="reflect").var())
        return value, value, value
    tile_h, tile_w = height // _TILE_GRID, width // _TILE_GRID
    values = [
        float(convolve(gray[i * tile_h:(i + 1) * tile_h, j * tile_w:(j + 1) * tile_w], _LAPLACE, mode="reflect").var())
        for i in range(_TILE_GRID)
        for j in range(_TILE_GRID)
    ]
    arr = np.asarray(values)
    return float(arr.max()), float(np.percentile(arr, 25)), float(np.median(arr))


def _jpeg_blockiness(gray: np.ndarray) -> float:
    """Mean ratio of 8x8 boundary gradients to interior gradients."""
    if gray.shape[0] < 2 * _BLOCK or gray.shape[1] < 2 * _BLOCK:
        return 1.0
    gx = np.abs(np.diff(gray, axis=1))
    gy = np.abs(np.diff(gray, axis=0))
    col_boundary = (np.arange(gx.shape[1]) % _BLOCK) == (_BLOCK - 1)
    row_boundary = (np.arange(gy.shape[0]) % _BLOCK) == (_BLOCK - 1)
    horiz = gx[:, col_boundary].mean() / max(gx[:, ~col_boundary].mean(), 1e-6)
    vert = gy[row_boundary, :].mean() / max(gy[~row_boundary, :].mean(), 1e-6)
    return float(0.5 * (horiz + vert))


def extract_features(ctx: RunContext, images: pd.DataFrame) -> pd.DataFrame:
    """Return one feature row per image_id; resolve image paths via ctx.input_dir."""
    rows: list[dict] = []
    for record in images.itertuples(index=False):
        path = Path(ctx.input_dir) / str(record.path)
        if not path.exists():
            raise FileNotFoundError(f"T02 image not found: {path}")
        rgb = image_ops.load_rgb(path)
        gray = image_ops.to_gray(rgb)

        tile_max, tile_p25, tile_median = _tile_sharpness(gray)
        sat_mask = gray >= _SAT_LEVEL
        soft_mask = gray >= _SOFT_BRIGHT
        rows.append(
            {
                "image_id": str(record.image_id),
                "path": str(record.path),
                "camera_id": str(record.camera_id),
                "light": str(record.light),
                "split": str(record.split),
                "scene_id": _scene_key(record.image_id, record.camera_id, record.light),
                "lap_var": image_ops.laplacian_variance(rgb),
                "lap_tile_max": tile_max,
                "lap_tile_p25": tile_p25,
                "lap_tile_median": tile_median,
                "bright_mean": float(gray.mean()),
                "bright_p05": float(np.percentile(gray, 5)),
                "bright_p95": float(np.percentile(gray, 95)),
                "bright_p99": float(np.percentile(gray, 99)),
                "dark_frac": float((gray < 25).mean()),
                "clip_dark_frac": float((gray < 10).mean()),
                "sat_frac": float(sat_mask.mean()),
                "sat_any_frac": float((rgb.max(axis=2) >= 250).mean()),
                "glare_blob_frac": _largest_component_fraction(sat_mask, min_iters=3),
                "glare_soft_blob_frac": _largest_component_fraction(soft_mask, min_iters=2),
                "jpeg_blockiness": _jpeg_blockiness(gray),
            }
        )

    features = pd.DataFrame(rows)
    ctx.stats["n_feature_rows"] = len(features)
    return features[["image_id", "path", "camera_id", "light", "split", "scene_id", *FEATURE_COLUMNS]]
