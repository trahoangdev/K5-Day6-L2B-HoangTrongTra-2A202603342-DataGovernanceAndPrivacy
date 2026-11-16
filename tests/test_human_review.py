"""Human-review sheet checks — Nguyễn Tuấn Minh, 2A202603349."""
import pandas as pd
import pytest
import copy
import json
from pathlib import Path

from demo import apply_review as cli
from src.common.io import config_hash, sha256_file, sha256_text
from src.common.review import REVIEW_COLUMNS
from src.team06.review_bundle import VERSION, merge_review_decisions, queue_digest, read_bound_review


RECORDED = "2026-11-16T01:02:33+07:00"


def _context(queue):
    binding = {"policy_version": "t02-lead-v1", "config_hash": "test-config", "seed": 42,
               "input_manifest_sha256": "manifest", "scored_sha256": "raw",
               "queue_ids": queue.item_id.tolist()}
    return {**binding, "fingerprint": config_hash(binding)}


def _merge(queue, decisions, reviewer="Nguyễn Tuấn Minh - 2A202603349", reviewed_at=RECORDED, **overrides):
    options = {"review_context": _context(queue), "expected_context": _context(queue),
               "expected_queue_sha256": queue_digest(queue)}
    options.update(overrides)
    return merge_review_decisions(queue, decisions, reviewer, reviewed_at, **options)


def _queue():
    return pd.DataFrame([{
        "rank": 1, "item_id": "img_18_2", "score": "1.728876", "reason": "glare",
        "suggested_action": "RECAPTURE", "slice": "night", "evidence_path": "images/img_18_2.jpg",
        "reviewer": "", "reviewer_decision": "", "override_value": "", "review_note": "", "reviewed_at": "",
    }, {
        "rank": 2, "item_id": "img_12_3", "score": "2.15", "reason": "dark",
        "suggested_action": "RECAPTURE", "slice": "dusk", "evidence_path": "images/img_12_3.jpg",
        "reviewer": "", "reviewer_decision": "", "override_value": "", "review_note": "", "reviewed_at": "",
    }])


def test_merge_keeps_queue_score_and_fills_only_reviewer_fields():
    decisions = pd.DataFrame([
        {"item_id": "img_18_2", "reviewer_decision": "edit", "override_value": "keep", "review_note": "night still usable"},
    ])
    sheet = _merge(_queue(), decisions)
    assert list(sheet.columns) == REVIEW_COLUMNS
    edited = sheet.set_index("item_id").loc["img_18_2"]
    assert edited.score == "1.728876"
    assert edited.suggested_action == "RECAPTURE"
    assert edited.reviewer_decision == "edit" and edited.override_value == "KEEP"
    assert edited.reviewer == "Nguyễn Tuấn Minh - 2A202603349"
    assert edited.reviewed_at == RECORDED
    pending = sheet.set_index("item_id").loc["img_12_3"]
    assert pending.reviewer_decision == "" and pending.reviewer == ""


def test_merge_rejects_ids_outside_the_live_queue():
    decisions = pd.DataFrame([
        {"item_id": "not-in-queue", "reviewer_decision": "approve", "override_value": "", "review_note": "no"},
    ])
    with pytest.raises(ValueError, match="outside the current queue"):
        _merge(_queue(), decisions)


def _decisions():
    return pd.DataFrame([{"item_id": "img_18_2", "reviewer_decision": "approve",
                          "override_value": "", "review_note": "Recorded approval"}])


@pytest.mark.parametrize("column,value", [("score", "0.01"), ("suggested_action", "KEEP"),
                                         ("reason", "different"), ("evidence_path", "other.jpg"),
                                         ("rank", 9), ("slice", "day")])
def test_old_decision_cannot_be_rebound_to_new_queue(column, value):
    original = _queue()
    changed = original.copy()
    changed.loc[0, column] = value
    with pytest.raises(ValueError, match="live queue contents"):
        _merge(changed, _decisions(), expected_queue_sha256=queue_digest(original))


@pytest.mark.parametrize("key,value", [("config_hash", "new-config"), ("seed", 7),
                                      ("scored_sha256", "changed"), ("input_manifest_sha256", "changed"),
                                      ("queue_ids", ["other"]), ("policy_version", "v9")])
def test_old_decision_rejects_a_different_run_context(key, value):
    expected = _context(_queue())
    actual = copy.deepcopy(expected)
    actual[key] = value
    with pytest.raises(ValueError, match="run context"):
        _merge(_queue(), _decisions(), review_context=actual, expected_context=expected)


def test_fingerprint_cannot_be_replaced_by_unverified_metadata():
    context = _context(_queue())
    context["fingerprint"] = "forged"
    with pytest.raises(ValueError, match="fingerprint"):
        _merge(_queue(), _decisions(), review_context=context, expected_context=context)


@pytest.mark.parametrize("reviewer,stamp", [("", RECORDED), ("Reviewer", ""),
                                          ("Reviewer", "2026-11-16T01:02:33")])
def test_replay_requires_saved_identity_and_timestamp(reviewer, stamp):
    with pytest.raises(ValueError):
        _merge(_queue(), _decisions(), reviewer=reviewer, reviewed_at=stamp)


@pytest.mark.parametrize("changes", [{"reviewer_decision": "unknown"}, {"review_note": ""},
                                    {"reviewer_decision": "edit", "override_value": "REVIEW"},
                                    {"override_value": "KEEP"}])
def test_invalid_decisions_fail_without_mutating_input(changes):
    queue = _queue()
    saved = queue.copy(deep=True)
    decisions = _decisions()
    for key, value in changes.items():
        decisions.loc[0, key] = value
    with pytest.raises(ValueError):
        _merge(queue, decisions)
    pd.testing.assert_frame_equal(queue, saved)


def test_duplicate_ids_and_unresolved_approval_fail():
    decisions = _decisions()
    with pytest.raises(ValueError, match="Duplicate"):
        _merge(_queue(), pd.concat([decisions, decisions]))
    with pytest.raises(ValueError, match="Duplicate"):
        _merge(pd.concat([_queue(), _queue()]), decisions)
    queue = _queue()
    queue.loc[0, "suggested_action"] = "REVIEW"
    with pytest.raises(ValueError, match="Cannot approve"):
        _merge(queue, decisions)


@pytest.fixture
def bound_run(tmp_path):
    run = tmp_path / "out/review"
    run.mkdir(parents=True)
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures/manifest.csv").write_text("input manifest", encoding="utf-8")
    raw = "image_id,score\nimg_18_2,1.728876\nimg_12_3,2.15\n"
    (run / "raw_predictions.csv").write_text(raw, encoding="utf-8", newline="\n")
    queue = _queue()
    queue.to_csv(run / "review_queue.csv", index=False, lineterminator="\n")
    context = _context(queue)
    context["input_manifest_sha256"] = sha256_file(tmp_path / "fixtures/manifest.csv")
    context["scored_sha256"] = sha256_text(raw)
    context["fingerprint"] = config_hash({k: v for k, v in context.items() if k != "fingerprint"})
    (run / "review_context.json").write_text(json.dumps(context), encoding="utf-8")
    info = {"status": 0, "offline": True, "track": "t02", "config_hash": context["config_hash"],
            "seed": 42, "output": "out/review", "input": "fixtures"}
    (run / "run_info.json").write_text(json.dumps(info), encoding="utf-8")
    bundle = {"version": VERSION, "context": context, "queue_sha256": queue_digest(queue),
              "reviewer": "Recorded test reviewer", "recorded_at": RECORDED,
              "decisions": _decisions().to_dict("records")}
    (tmp_path / "demo").mkdir()
    (tmp_path / "configs").mkdir()
    (tmp_path / "src/team06").mkdir(parents=True)
    (tmp_path / "demo/review_bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
    hashes = {}
    for name in ["demo/apply_review.py", "src/team06/review_bundle.py", "configs/protocol_freeze.json"]:
        (tmp_path / name).write_text("test-only frozen source", encoding="utf-8")
        hashes[name] = sha256_file(tmp_path / name)
    hashes["demo/review_bundle.json"] = sha256_file(tmp_path / "demo/review_bundle.json")
    protocol = {"version": VERSION, "sha256": hashes}
    (tmp_path / "configs/review_protocol_v2.json").write_text(json.dumps(protocol), encoding="utf-8")
    return tmp_path, run


def _read_bound(root, run):
    return read_bound_review(run, root / "demo/review_bundle.json", root / "configs/review_protocol_v2.json", root)


def test_bound_cli_is_idempotent_and_does_not_overwrite_other_human_input(bound_run, monkeypatch):
    root, run = bound_run
    monkeypatch.setattr(cli, "ROOT", root)
    args = ["--run-dir", "out/review"]
    assert cli.main(args) == 0
    output = run / "review_queue_reviewed.csv"
    first = output.read_bytes()
    assert cli.main(args) == 0 and output.read_bytes() == first
    sheet = pd.read_csv(output, keep_default_na=False)
    assert sheet.loc[0, "reviewed_at"] == RECORDED
    output.write_bytes(b"other human input\n")
    assert cli.main(args) == 2
    assert output.read_bytes() == b"other human input\n"


@pytest.mark.parametrize("path,text", [("raw_predictions.csv", "changed score"),
                                     ("review_context.json", "{}"), ("review_queue.csv", "item_id\nother\n"),
                                     ("review_queue.csv", "wrong_column\nother\n")])
def test_artifact_tampering_is_rejected_before_cli_writes(bound_run, monkeypatch, path, text):
    root, run = bound_run
    monkeypatch.setattr(cli, "ROOT", root)
    (run / path).write_text(text, encoding="utf-8")
    assert cli.main(["--run-dir", "out/review"]) == 2
    assert not (run / "review_queue_reviewed.csv").exists()


def test_modified_manifest_or_bundle_is_rejected(bound_run):
    root, run = bound_run
    _read_bound(root, run)
    manifest = root / "fixtures/manifest.csv"
    old = manifest.read_bytes()
    manifest.write_bytes(b"changed manifest")
    with pytest.raises(ValueError, match="input or raw scores"):
        _read_bound(root, run)
    manifest.write_bytes(old)
    bundle = root / "demo/review_bundle.json"
    value = json.loads(bundle.read_text())
    value["reviewer"] = "Imposter"
    bundle.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="Frozen review protocol changed"):
        _read_bound(root, run)


@pytest.mark.parametrize("key,value", [("offline", False), ("status", 2), ("config_hash", "wrong"),
                                      ("seed", 7), ("output", "out/other")])
def test_run_metadata_must_match_actual_bound_run(bound_run, key, value):
    root, run = bound_run
    info = json.loads((run / "run_info.json").read_text())
    info[key] = value
    (run / "run_info.json").write_text(json.dumps(info), encoding="utf-8")
    with pytest.raises(ValueError, match="Run metadata"):
        _read_bound(root, run)
