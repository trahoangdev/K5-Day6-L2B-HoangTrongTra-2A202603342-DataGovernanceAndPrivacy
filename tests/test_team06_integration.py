"""Lead-owned integration tests. Synthetic test scores are NOT a lab baseline/PoC."""
import json
import socket
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from PIL import Image

from src.common.context import RunContext
from src.common.manifest import build_manifest, write_manifest
from src.main import main
from src.pipeline import run_pipeline
from src.team06 import scoring
from src.team06.integration import validate_scored
from src.team06.policy import POLICY_VERSION


@pytest.fixture
def ctx(tmp_path):
    source = tmp_path / "input"
    (source / "images").mkdir(parents=True)
    rows = []
    for index in range(4):
        path = f"images/i{index}.jpg"
        Image.new("RGB", (16, 9), (40 + index * 30, 60, 80)).save(source / path)
        rows.append({"image_id": f"i{index}", "path": path, "camera_id": "cam_A",
                     "light": "day" if index < 2 else "night", "split": "dev" if index < 2 else "eval"})
    pd.DataFrame(rows).to_csv(source / "images.csv", index=False)
    files = ["images.csv"] + [row["path"] for row in rows]
    write_manifest(build_manifest(source, files, "synthetic:test", "CC0"), source / "manifest.csv")
    config = {"track": "t02", "group_id": "G06", "owner": "Hoàng Trọng Trà - 2A202603342",
              "seed": 42, "offline": True, "strict_provenance": True,
              "params": {"budget": 2, "review_split": "all", "policy_version": POLICY_VERSION}}
    return RunContext(track="t02", input_dir=source, output_dir=tmp_path / "out", config=config,
                      seed=42, rng=np.random.default_rng(42))


def fixture_scorer(ctx, data):
    """Deterministic injected contract data, independent of images and hidden labels."""
    return data["images"][["image_id"]].assign(score=[9.0, 8.0, 1.0, 0.0],
                                             pred_action="KEEP", reason="Integration test fixture")


def decision(ctx):
    return json.loads(ctx.out("decision.json").read_text(encoding="utf-8"))


def review_all(ctx, action="approve", value=""):
    queue = pd.read_csv(ctx.out("review_queue.csv"), dtype=str).fillna("")
    queue["reviewer"] = "Synthetic test reviewer"
    queue["reviewer_decision"] = action
    queue["override_value"] = value
    queue["review_note"] = "Synthetic fixture inspected for integration testing"
    queue.to_csv(ctx.out("review_queue_reviewed.csv"), index=False)
    return queue


def test_unreviewed_queue_holds_and_writes_complete_evidence(ctx):
    run_pipeline(ctx, scorer=fixture_scorer)
    assert decision(ctx)["status"] == "HOLD"
    assert decision(ctx)["reason_code"] == "REVIEW_PENDING"
    assert decision(ctx)["metrics"]["n_pending"] == 2
    for name in ("raw_predictions.csv", "ranked_review.csv", "image_decisions.csv", "review_queue.csv",
                 "contact_sheet.html", "review_context.json", "policy_snapshot.json", "audit_log.jsonl"):
        assert ctx.out(name).exists(), name
    final = pd.read_csv(ctx.out("ranked_review.csv"))
    assert final.pred_action.tolist() == ["REVIEW", "REVIEW", "KEEP", "KEEP"]
    assert "data:image/jpeg;base64," in ctx.out("contact_sheet.html").read_text(encoding="utf-8")
    assert all(Path(path).exists() for path in decision(ctx)["evidence"])


def test_complete_review_go_preserves_scores_raw_and_append_only_audit(ctx):
    run_pipeline(ctx, scorer=fixture_scorer)
    raw_bytes = ctx.out("raw_predictions.csv").read_bytes()
    old_audit = ctx.out("audit_log.jsonl").read_bytes()
    review_all(ctx)
    run_pipeline(ctx, scorer=fixture_scorer)
    assert decision(ctx)["status"] == "GO"
    assert decision(ctx)["reason_code"] == "TRIAGE_COMPLETE"
    final = pd.read_csv(ctx.out("ranked_review.csv"))
    assert final.pred_action.eq("KEEP").all()
    assert final.score.tolist() == [9.0, 8.0, 1.0, 0.0]
    assert final.review_status.tolist() == ["approved", "approved", "not_required", "not_required"]
    assert ctx.out("raw_predictions.csv").read_bytes() == raw_bytes
    assert ctx.out("audit_log.jsonl").read_bytes().startswith(old_audit)
    events = [json.loads(line) for line in ctx.out("audit_log.jsonl").read_text(encoding="utf-8").splitlines()]
    edits = [event for event in events if event["action"] == "review:approve"]
    assert len(edits) == 2 and all(event["actor"] == "Synthetic test reviewer" for event in edits)
    assert edits[0]["before"]["pred_action"] == "REVIEW"
    assert edits[0]["after"]["pred_action"] == "KEEP"
    final_bytes = ctx.out("ranked_review.csv").read_bytes()
    run_pipeline(ctx, scorer=fixture_scorer)
    assert ctx.out("ranked_review.csv").read_bytes() == final_bytes


@pytest.mark.parametrize("action,value", [("reject", ""), ("edit", "RECAPTURE")])
def test_recapture_requires_rework(ctx, action, value):
    run_pipeline(ctx, scorer=fixture_scorer)
    review_all(ctx, action, value)
    run_pipeline(ctx, scorer=fixture_scorer)
    assert decision(ctx)["status"] == "REWORK"
    assert decision(ctx)["reason_code"] == "RECAPTURE_REQUIRED"
    assert decision(ctx)["metrics"]["n_recapture"] == 2


def test_reviewer_can_keep_a_false_positive_without_changing_its_score(ctx):
    def false_positive(ctx, data):
        table = fixture_scorer(ctx, data)
        table.loc[0, "pred_action"] = "RECAPTURE"
        return table
    run_pipeline(ctx, scorer=false_positive)
    review_all(ctx, "edit", "KEEP")
    run_pipeline(ctx, scorer=false_positive)
    assert decision(ctx)["status"] == "GO"
    row = pd.read_csv(ctx.out("ranked_review.csv")).iloc[0]
    assert row.auto_action == "RECAPTURE" and row.pred_action == "KEEP" and row.score == 9


def test_explicit_auto_recapture_outside_queue_still_requires_rework(ctx):
    def auto_recapture(ctx, data):
        table = fixture_scorer(ctx, data)
        table.loc[3, "pred_action"] = "RECAPTURE"
        return table
    run_pipeline(ctx, scorer=auto_recapture)
    review_all(ctx)
    run_pipeline(ctx, scorer=auto_recapture)
    assert decision(ctx)["status"] == "REWORK"
    row = pd.read_csv(ctx.out("image_decisions.csv")).iloc[3]
    assert row.reason_code == "AUTO_RECAPTURE" and row.review_status == "not_required"


@pytest.mark.parametrize("action", ["skip", "escalate"])
def test_unresolved_human_decisions_hold(ctx, action):
    run_pipeline(ctx, scorer=fixture_scorer)
    review_all(ctx, action)
    run_pipeline(ctx, scorer=fixture_scorer)
    assert decision(ctx)["status"] == "HOLD"
    assert decision(ctx)["metrics"]["n_pending"] == 2


def test_hold_precedes_rework_when_review_is_partial(ctx):
    run_pipeline(ctx, scorer=fixture_scorer)
    queue = review_all(ctx, "reject")
    queue.loc[1, "reviewer_decision"] = ""
    queue.to_csv(ctx.out("review_queue_reviewed.csv"), index=False)
    run_pipeline(ctx, scorer=fixture_scorer)
    assert decision(ctx)["status"] == "HOLD"
    assert decision(ctx)["metrics"]["n_recapture"] == 1


def test_minimum_scorer_contract_is_safe_and_unknown_actions_do_not_become_keep(ctx):
    def minimal(ctx, data):
        return fixture_scorer(ctx, data)[["image_id", "score"]]
    run_pipeline(ctx, scorer=minimal)
    assert decision(ctx)["status"] == "HOLD"
    assert decision(ctx)["metrics"]["n_pending"] == 4
    review_all(ctx, "edit", "KEEP")
    run_pipeline(ctx, scorer=minimal)
    assert decision(ctx)["metrics"]["n_pending"] == 2  # uncertainty outside top-B still blocks GO


def test_approve_uncertainty_requires_explicit_edit(ctx):
    def uncertain(ctx, data):
        return fixture_scorer(ctx, data).assign(pred_action="REVIEW")
    run_pipeline(ctx, scorer=uncertain)
    review_all(ctx)
    with pytest.raises(ValueError, match="Cannot approve unresolved"):
        run_pipeline(ctx, scorer=uncertain)
    assert decision(ctx)["reason_code"] == "RUN_FAILED"


@pytest.mark.parametrize("mutation,match", [
    (lambda table: table.assign(score=[float("nan"), 8, 1, 0]), "non-finite"),
    (lambda table: table.assign(score=[float("inf"), 8, 1, 0]), "non-finite"),
    (lambda table: table.assign(score=["bad", "8", "1", "0"]), "non-finite"),
    (lambda table: table.assign(score=True), "boolean"),
    (lambda table: pd.concat([table.head(1), table.head(1), table.tail(2)]), "duplicate image_id"),
    (lambda table: table.head(3), "input image_id pool"),
    (lambda table: table.assign(split="eval"), "immutable metadata"),
    (lambda table: table.assign(pred_action="GO"), "pred_action"),
])
def test_invalid_scorer_output_fails_before_success_files(ctx, mutation, match):
    def invalid(ctx, data):
        return mutation(fixture_scorer(ctx, data))
    with pytest.raises(ValueError, match=match):
        run_pipeline(ctx, scorer=invalid)
    assert not ctx.out("ranked_review.csv").exists()
    assert decision(ctx)["status"] == "HOLD"
    assert decision(ctx)["reason_code"] == "RUN_FAILED"


@pytest.mark.parametrize("column,value,match", [
    ("item_id", "unknown", "outside the current queue"),
    ("reviewer", "", "no `reviewer`"),
    ("review_note", "", "review_note"),
    ("score", "999", "score does not match"),
    ("suggested_action", "RECAPTURE", "suggested_action does not match"),
    ("override_value", "KEEP", "Use edit"),
])
def test_invalid_review_is_rejected_without_applying_partial_overrides(ctx, column, value, match):
    run_pipeline(ctx, scorer=fixture_scorer)
    queue = review_all(ctx)
    queue.loc[1, column] = value  # first row is valid, second row invalid
    queue.to_csv(ctx.out("review_queue_reviewed.csv"), index=False)
    with pytest.raises(ValueError, match=match):
        run_pipeline(ctx, scorer=fixture_scorer)
    assert not ctx.out("ranked_review.csv").exists()
    assert not any(event["action"].startswith("review:") for event in ctx.audit.read())


def test_duplicate_review_ids_are_rejected(ctx):
    run_pipeline(ctx, scorer=fixture_scorer)
    queue = review_all(ctx)
    pd.concat([queue, queue.head(1)]).to_csv(ctx.out("review_queue_reviewed.csv"), index=False)
    with pytest.raises(ValueError, match="Duplicate item_id"):
        run_pipeline(ctx, scorer=fixture_scorer)


@pytest.mark.parametrize("change", ["score", "budget", "binding"])
def test_stale_review_cannot_reuse_prior_go(ctx, change):
    run_pipeline(ctx, scorer=fixture_scorer)
    review_all(ctx)
    run_pipeline(ctx, scorer=fixture_scorer)
    assert decision(ctx)["status"] == "GO"
    scorer = fixture_scorer
    if change == "score":
        def scorer(ctx, data):
            return fixture_scorer(ctx, data).assign(score=[9.1, 8, 1, 0])
    elif change == "budget":
        ctx.config["params"]["budget"] = 1
    else:
        ctx.out("review_context.json").unlink()
    with pytest.raises(ValueError, match="Stale or unbound"):
        run_pipeline(ctx, scorer=scorer)
    assert decision(ctx)["status"] == "HOLD"
    assert not ctx.out("ranked_review.csv").exists()
    assert ctx.out("review_queue_reviewed.csv").exists()


def test_tie_breaking_and_review_pool_are_explicit(ctx):
    images = pd.read_csv(ctx.input_dir / "images.csv")
    tied = fixture_scorer(ctx, {"images": images}).assign(score=1).iloc[::-1]
    normalized = validate_scored(tied, images)
    assert normalized.image_id.tolist() == ["i0", "i1", "i2", "i3"]
    ctx.config["params"]["review_split"] = "eval"
    run_pipeline(ctx, scorer=fixture_scorer)
    assert pd.read_csv(ctx.out("review_queue.csv")).item_id.tolist() == ["i2", "i3"]
    assert len(pd.read_csv(ctx.out("ranked_review.csv"))) == 4


@pytest.mark.parametrize("key,value", [("budget", 0), ("budget", True),
                                      ("review_split", "invalid"), ("policy_version", "unknown")])
def test_invalid_settings_cannot_disable_the_review_gate(ctx, key, value):
    ctx.config["params"][key] = value
    with pytest.raises(ValueError):
        run_pipeline(ctx, scorer=fixture_scorer)
    assert decision(ctx)["status"] == "HOLD"
    assert not ctx.out("ranked_review.csv").exists()


@pytest.mark.parametrize("column,value", [("score", 0.0), ("split", "eval")])
def test_integration_rejects_a_review_adapter_that_changes_rank_or_metadata(ctx, monkeypatch, column, value):
    from src.team06 import integration

    original = integration.apply_human_review
    def broken_adapter(ctx, raw, queue):
        result = original(ctx, raw, queue)
        result.loc[0, column] = value
        return result
    monkeypatch.setattr(integration, "apply_human_review", broken_adapter)
    with pytest.raises(ValueError, match="Human review must preserve"):
        run_pipeline(ctx, scorer=fixture_scorer)
    assert decision(ctx)["status"] == "HOLD"
    assert not ctx.out("ranked_review.csv").exists()


@pytest.mark.parametrize("setting", ["provenance", "offline"])
def test_unverified_or_online_run_cannot_go(ctx, setting):
    if setting == "provenance":
        ctx.config["strict_provenance"] = False
    else:
        ctx.offline = False
    run_pipeline(ctx, scorer=fixture_scorer)
    review_all(ctx)
    run_pipeline(ctx, scorer=fixture_scorer)
    assert decision(ctx)["status"] == "HOLD"
    assert decision(ctx)["reason_code"] == {"provenance": "PROVENANCE_UNVERIFIED", "offline": "OFFLINE_REQUIRED"}[setting]


def test_cli_uses_lead_integration_and_reports_go_after_review(ctx, monkeypatch, tmp_path):
    monkeypatch.setattr(scoring, "score_images", fixture_scorer)
    config = tmp_path / "lab.yaml"
    config.write_text(yaml.safe_dump(ctx.config, allow_unicode=True), encoding="utf-8")
    args = ["--config", str(config), "--track", "t02", "--input", str(ctx.input_dir),
            "--output", str(ctx.output_dir), "--offline", "--seed", "42"]
    assert main(args) == 0  # successful execution can legitimately produce HOLD
    assert decision(ctx)["status"] == "HOLD"
    review_all(ctx)
    assert main(args) == 0
    assert decision(ctx)["status"] == "GO"
    info = json.loads(ctx.out("run_info.json").read_text(encoding="utf-8"))
    assert info["status"] == 0 and info["stats"]["decision_status"] == "GO"


@pytest.mark.parametrize("attempt,code", [("gt", 5), ("network", 4)])
def test_cli_guards_remain_active_inside_scorer(ctx, monkeypatch, tmp_path, attempt, code):
    def blocked(ctx, data):
        if attempt == "gt":
            pd.read_csv("fixtures/t02_raw_qc/gt/labels.csv")
        else:
            socket.create_connection(("example.com", 443), timeout=1)
        raise AssertionError("Guard failed")
    monkeypatch.setattr(scoring, "score_images", blocked)
    config = tmp_path / "lab.yaml"
    config.write_text(yaml.safe_dump(ctx.config, allow_unicode=True), encoding="utf-8")
    assert main(["--config", str(config), "--track", "t02", "--input", str(ctx.input_dir),
                 "--output", str(ctx.output_dir), "--offline"]) == code
    assert decision(ctx)["status"] == "HOLD"
    assert not ctx.out("ranked_review.csv").exists()


@pytest.mark.parametrize("invalid", ["nan_weights", "eval_only"])
def test_real_poc_calibration_errors_fail_closed_through_cli(ctx, tmp_path, invalid):
    if invalid == "nan_weights":
        ctx.config["params"]["scoring"] = {"weights": {"blur": float("nan")}}
    else:
        images = pd.read_csv(ctx.input_dir / "images.csv")
        images[images.split.eq("eval")].to_csv(ctx.input_dir / "images.csv", index=False)
        files = ["images.csv"] + images.path.tolist()
        write_manifest(build_manifest(ctx.input_dir, files, "synthetic:test", "CC0"), ctx.input_dir / "manifest.csv")
    config = tmp_path / "lab.yaml"
    config.write_text(yaml.safe_dump(ctx.config, allow_unicode=True), encoding="utf-8")
    assert main(["--config", str(config), "--track", "t02", "--input", str(ctx.input_dir),
                 "--output", str(ctx.output_dir), "--offline"]) == 2
    assert decision(ctx)["status"] == "HOLD"
    assert decision(ctx)["reason_code"] == "RUN_FAILED"
    assert not ctx.out("ranked_review.csv").exists()
