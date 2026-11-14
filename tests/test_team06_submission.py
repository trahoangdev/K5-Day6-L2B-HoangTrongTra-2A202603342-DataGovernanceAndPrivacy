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


def test_exporter_whitelist_keeps_review_and_baseline_outputs_local(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "out/poc"
    output.mkdir(parents=True)
    for filename in submission.POC_EVIDENCE_FILES:
        (output / filename).write_text("new run\n", encoding="utf-8")
    for filename in ("run_info.json", "review_queue.csv", "policy_snapshot.json"):
        (output / filename).write_text("local only", encoding="utf-8")
    (output / "decision_log.csv").write_text("ts,status\nnow,HOLD\n", encoding="utf-8")
    archived = Path("reports/submission/poc")
    archived.mkdir(parents=True)
    (archived / "audit_log.jsonl").write_bytes(b"original human audit\n")

    submission.export_run_evidence("baseline", output)
    assert not Path("reports/submission/baseline").exists()
    submission.export_run_evidence("poc", output)

    assert {p.name for p in archived.iterdir()} == set(submission.POC_EVIDENCE_FILES)
    assert (archived / "audit_log.jsonl").read_bytes() == b"original human audit\n"
    assert Path("reports/decision_log.csv").read_text() == "ts,status\nnow,HOLD\n"


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


def test_report_reads_saved_results_without_local_junit_xml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    saved = Path("reports/submission/tests.txt")
    saved.parent.mkdir(parents=True)
    saved.write_text("....... [100%]\n140 passed, 39 skipped in 10.49s\n", encoding="utf-8")
    assert not Path("out/submission/tests.xml").exists()
    counts = submission.read_test_counts()
    assert (counts["passed"], counts["skipped"], counts["failed"], counts["errors"]) == (140, 39, 0, 0)


def test_saved_test_failures_and_errors_are_not_hidden(tmp_path):
    saved = tmp_path / "tests.txt"
    saved.write_text("1 failed, 2 passed, 3 skipped, 1 error in 1.0s\n", encoding="utf-8")
    counts = submission.read_test_counts(saved)
    assert (counts["passed"], counts["skipped"], counts["failed"], counts["errors"]) == (2, 3, 1, 1)


def test_missing_test_summary_is_rejected(tmp_path):
    saved = tmp_path / "tests.txt"
    saved.write_text("pytest crashed before collecting tests\n", encoding="utf-8")
    with pytest.raises(ValueError, match="No pytest summary"):
        submission.read_test_counts(saved)
