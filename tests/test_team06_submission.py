"""Submission evidence must not silently relabel eval or bypass the freeze."""
import json
import csv
from pathlib import Path

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


def test_exporter_only_publishes_required_logs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output = Path("out/poc")
    output.mkdir(parents=True)
    for filename in ("raw_predictions.csv", "run_info.json", "review_queue.csv", "policy_snapshot.json"):
        (output / filename).write_text("local only", encoding="utf-8")
    (output / "audit_log.jsonl").write_text("new run audit\n", encoding="utf-8")
    (output / "decision_log.csv").write_text("ts,status\nnow,HOLD\n", encoding="utf-8")
    Path("reports").mkdir()
    original = Path("reports/audit_log.jsonl")
    original.write_bytes(b"original human audit\n")
    submission.export_run_evidence("baseline", output)
    submission.export_run_evidence("poc", output)
    assert {p.name for p in Path("reports").iterdir()} == {"audit_log.jsonl", "decision_log.csv"}
    assert original.read_bytes() == b"original human audit\n"
    assert not Path("reports/submission").exists()


def test_published_decision_log_is_append_only_and_replays_do_not_duplicate(tmp_path):
    source, published = tmp_path / "run.csv", tmp_path / "published.csv"
    original = b'ts,status,reason\nold,HOLD,"needs review, keep history"\n'
    published.write_bytes(original)
    source.write_bytes(original + b"new,HOLD,pending\n")
    submission.append_decision_log(source, published)
    assert published.read_bytes().startswith(original)
    with published.open(newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 2
    once = published.read_bytes()
    submission.append_decision_log(source, published)
    assert published.read_bytes() == once


def test_decision_log_schema_error_does_not_change_published_history(tmp_path):
    source, published = tmp_path / "run.csv", tmp_path / "published.csv"
    published.write_bytes(b"ts,status\nold,HOLD\n")
    source.write_bytes(b"ts,status,extra\nnew,HOLD,oops\n")
    with pytest.raises(ValueError, match="schema"):
        submission.append_decision_log(source, published)
    assert published.read_bytes() == b"ts,status\nold,HOLD\n"


def review_fixture(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output = Path("out/poc")
    output.mkdir(parents=True)
    (output / "raw_predictions.csv").write_text("image_id,score\na,1.0\n", encoding="utf-8", newline="\n")
    (output / "review_queue.csv").write_text("item_id\na\n", encoding="utf-8")
    human = Path("reports/review_queue.csv")
    human.parent.mkdir()
    human.write_text("item_id,reviewer\na,Reviewer A\n", encoding="utf-8")
    manifest = Path("fixtures/t02_raw_qc/manifest.csv")
    manifest.parent.mkdir(parents=True)
    manifest.write_text("input manifest\n", encoding="utf-8")
    proof = {"confirmed_review": {
        "context": {"scored_sha256": submission.digest(output / "raw_predictions.csv"),
                    "input_manifest_sha256": submission.digest(manifest), "queue_ids": ["a"]},
        "confirmation": {"item_ids": ["a"], "confirmed_by": "Reviewer A"},
        "review_csv_sha256": submission.digest(human)}}
    return proof, output


def test_review_replays_without_a_committed_prediction_snapshot(tmp_path, monkeypatch):
    proof, output = review_fixture(tmp_path, monkeypatch)
    assert list(submission.confirmed_review(proof, output).item_id) == ["a"]
    assert not Path("reports/submission").exists()


@pytest.mark.parametrize("file,text", [("out/poc/raw_predictions.csv", "image_id,score\na,99\n"),
                                       ("out/poc/review_queue.csv", "item_id\nother\n"),
                                       ("reports/review_queue.csv", "item_id,reviewer\na,Imposter\n")])
def test_review_binding_rejects_changed_score_queue_or_human(tmp_path, monkeypatch, file, text):
    proof, output = review_fixture(tmp_path, monkeypatch)
    Path(file).write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="Saved review does not match"):
        submission.confirmed_review(proof, output)
