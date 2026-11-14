"""Submission evidence must not silently relabel eval or bypass the freeze."""
import json

import pandas as pd
import pytest

from tools import prepare_submission as submission


def test_freeze_detects_modified_input(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "configs").mkdir()
    (tmp_path / "input.csv").write_text("original", encoding="utf-8")
    contract = {"sha256": {"input.csv": submission.digest("input.csv")}}
    (tmp_path / "configs/protocol_freeze.json").write_text(json.dumps(contract), encoding="utf-8")
    assert submission.verify_freeze() == contract
    (tmp_path / "input.csv").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="Frozen inputs changed"):
        submission.verify_freeze()


def test_internal_gt_rejects_eval_labels(monkeypatch):
    frames = [pd.DataFrame({"image_id": ["a", "b"], "split": ["dev", "eval"]}),
              pd.DataFrame({"image_id": ["b"], "is_defect": [1], "defect_type": ["blur"]})]
    monkeypatch.setattr(submission.pd, "read_csv", lambda *_: frames.pop(0))
    with pytest.raises(ValueError, match="no eval IDs"):
        submission.internal_gt()


def test_json_undefined_slice_cells_are_null(tmp_path):
    dest = tmp_path / "metrics.json"
    submission.write_json(dest, {"metrics": [{"value": 0.5}], "slices": [float("nan")]})
    assert json.loads(dest.read_text()) == {"metrics": [{"value": 0.5}], "slices": [None]}


def test_slices_use_global_budget_not_new_budget_per_camera():
    gt = pd.DataFrame({"image_id": [f"i{x:02}" for x in range(24)], "is_defect": [1] * 24,
                       "light": ["day"] * 24, "camera_id": ["A"] * 12 + ["B"] * 12,
                       "defect_type": ["blur"] * 24})
    pred = gt[["image_id"]].assign(score=list(range(24, 0, -1)))
    rows = submission.slices(gt, pred, "poc")
    b = next(row for row in rows if row["slice"] == "camera_id=B")
    assert b["hits_in_global_dev_top20"] == 8
    assert b["recall"] == 8 / 12
