"""T02 orchestration — Hoàng Trọng Trà, 2A202603342.

Scorers remain owned by Dương/Hạ. Validate their output, render shared review UI,
bind reviews to a reproducible run and gate release without reading ground truth.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from ..common.contact_sheet import render_contact_sheet
from ..common.context import RunContext
from ..common.decision import Decision, write_decision
from ..common.io import config_hash, read_json, sha256_file, sha256_text, write_json
from ..common.review import AuditLog, load_review_decisions, make_review_queue, write_review_queue
from .data import IMAGE_COLUMNS, load_inputs
from .human_review import apply_human_review
from .policy import ACTIONS, POLICY_VERSION, decide, validate_settings

# Human input, the previous review binding and append-only logs are retained.
GENERATED = ("raw_predictions.csv", "ranked_review.csv", "image_decisions.csv", "decision.json",
             "review_queue.csv", "contact_sheet.html", "policy_snapshot.json")
POLICY_COLUMNS = {"auto_action", "review_required", "review_status", "reviewer", "review_note",
                  "action_owner", "reason_code", "action_reason"}


def validate_scored(scored: pd.DataFrame, images: pd.DataFrame) -> pd.DataFrame:
    """Require complete, unique IDs and finite scores; metadata comes from the loader."""
    if not isinstance(scored, pd.DataFrame):
        raise ValueError("T02 scorer must return a DataFrame")
    if not scored.columns.is_unique:
        raise ValueError("T02 scorer returned duplicate column names")
    if not {"image_id", "score"} <= set(scored.columns):
        raise ValueError("T02 scorer must return image_id and score")
    if images.empty or scored.empty:
        raise ValueError("T02 input and scored tables must not be empty")
    if POLICY_COLUMNS & set(scored.columns):
        raise ValueError("Scorer must not supply reserved review/policy columns")
    out = scored.copy()
    if out.image_id.isna().any():
        raise ValueError("T02 scorer returned a missing image_id")
    out["image_id"] = out.image_id.astype(str)
    if out.image_id.duplicated().any():
        raise ValueError("T02 scorer returned duplicate image_id values")
    if set(out.image_id) != set(images.image_id):
        raise ValueError("T02 scorer must preserve exactly the input image_id pool")
    if out.score.map(lambda value: isinstance(value, (bool, np.bool_))).any():
        raise ValueError("T02 score must be numeric, not boolean")
    numeric = pd.to_numeric(out.score, errors="coerce")
    if not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise ValueError("T02 scorer returned a non-numeric or non-finite score")
    out["score"] = numeric.astype(float)
    expected = images.set_index("image_id")
    for column in IMAGE_COLUMNS[1:]:
        values = out.image_id.map(expected[column])
        if column in out and not out[column].astype(str).eq(values.astype(str)).all():
            raise ValueError(f"T02 scorer changed immutable metadata: {column}")
        out[column] = values
    for column, default in (("reason", ""), ("pred_defect_type", "unknown"), ("pred_action", "REVIEW")):
        out[column] = out[column].fillna(default).astype(str) if column in out else default
    out["pred_action"] = out.pred_action.str.strip().str.upper()
    if not out.pred_action.isin(ACTIONS).all():
        raise ValueError("T02 pred_action must be KEEP, RECAPTURE or REVIEW")
    columns = IMAGE_COLUMNS + ["score", "reason", "pred_defect_type", "pred_action"]
    columns += sorted(set(out.columns) - set(columns))
    return out[columns].sort_values(["score", "image_id"], ascending=[False, True], kind="mergesort").reset_index(drop=True)


def make_queue(ctx: RunContext, scored: pd.DataFrame) -> pd.DataFrame:
    split = ctx.param("review_split", "all")
    pool = scored if split == "all" else scored[scored.split.eq(split)]
    if pool.empty:
        raise ValueError(f"T02 review pool is empty for review_split={split}")
    return make_review_queue(pool, "image_id", "score", ctx.param("budget", 20),
                             reason_col="reason", action_col="pred_action", slice_col="light", evidence_col="path")


def bind_reviews(ctx: RunContext, scored: pd.DataFrame, queue: pd.DataFrame) -> None:
    """Reject decisions from a previous input/config/scoring context in the same output folder."""
    manifest = ctx.input_dir / "manifest.csv"
    binding = {
        "policy_version": POLICY_VERSION, "config_hash": config_hash(ctx.config), "seed": ctx.seed,
        "input_manifest_sha256": sha256_file(manifest) if manifest.exists() else None,
        "scored_sha256": sha256_text(scored.to_csv(index=False, lineterminator="\n")),
        "queue_ids": queue.item_id.tolist(),
    }
    fingerprint = config_hash(binding)
    binding["fingerprint"] = fingerprint
    path = ctx.out("review_context.json")
    reviewed = ctx.out("review_queue_reviewed.csv")
    if reviewed.exists() and not load_review_decisions(reviewed).empty:
        if not path.exists() or read_json(path).get("fingerprint") != fingerprint:
            raise ValueError("Stale or unbound reviewed queue: archive it and review the current run again")
    ctx.stats["review_fingerprint"] = fingerprint
    write_json(path, binding)


def run_t02(ctx: RunContext, scorer: Callable[[RunContext, dict], pd.DataFrame]) -> None:
    if ctx.input_dir.resolve() == ctx.output_dir.resolve() or ctx.input_dir.resolve() in ctx.output_dir.resolve().parents:
        raise ValueError("T02 output must be outside the input directory")
    ctx.output_dir.mkdir(parents=True, exist_ok=True)
    for name in GENERATED:
        ctx.out(name).unlink(missing_ok=True)
    if ctx.audit is None:
        ctx.audit = AuditLog(ctx.out("audit_log.jsonl"))
    ctx.stats.pop("review_fingerprint", None)
    ctx.stats.update(n_items=0, n_queued=0, n_reviewed=0, provenance_verified=False, decision_status="HOLD")
    try:
        validate_settings(ctx)
        ctx.audit.log(actor="pipeline", action="run_started", item_id=ctx.run_name, policy_version=POLICY_VERSION)
        data = load_inputs(ctx)
        ctx.stats["provenance_verified"] = bool(ctx.config.get("strict_provenance", True))
        raw = validate_scored(scorer(ctx, data), data["images"])
        ctx.stats["n_items"] = len(raw)
        queue = make_queue(ctx, raw)
        ctx.stats.update(review_split=ctx.param("review_split", "all"), n_queued=len(queue))
        bind_reviews(ctx, raw, queue)
        raw.to_csv(ctx.out("raw_predictions.csv"), index=False)
        write_review_queue(queue, ctx.out("review_queue.csv"))
        write_json(ctx.out("policy_snapshot.json"), {
            "version": POLICY_VERSION, "budget": ctx.param("budget", 20),
            "review_split": ctx.param("review_split", "all"), "precedence": ["HOLD", "REWORK", "GO"],
            "score_threshold": None, "note": "Scoring thresholds belong to the scorer; review does not change scores",
        })
        render_contact_sheet(queue, ctx.out("contact_sheet.html"), image_root=ctx.input_dir,
                             title="Team 6 · T02 review")
        final = apply_human_review(ctx, raw, queue)
        immutable = [column for column in raw.columns if column != "pred_action"]
        if not set(immutable) <= set(final.columns) or not final[immutable].equals(raw[immutable]):
            raise ValueError("Human review must preserve image IDs, metadata, row order and original scores")
        final.to_csv(ctx.out("ranked_review.csv"), index=False)
        columns = ["image_id", "auto_action", "pred_action", "review_required", "review_status",
                   "reason_code", "action_reason", "action_owner", "reviewer", "review_note"]
        final[columns].to_csv(ctx.out("image_decisions.csv"), index=False)
        for row in final.itertuples(index=False):
            ctx.audit.log(actor=row.action_owner, action="image_decision", item_id=row.image_id,
                          before=row.auto_action, after=row.pred_action, reason=row.reason_code,
                          run_fingerprint=ctx.stats["review_fingerprint"])
        decision = decide(ctx, final)
        ctx.stats["decision_status"] = decision.status
        write_decision(decision, ctx.out("decision.json"), ctx.out("decision_log.csv"))
        ctx.audit.log(actor=decision.owner, action="run_decision", item_id=ctx.run_name,
                      after=decision.status, reason=decision.reason_code, run_fingerprint=ctx.stats["review_fingerprint"])
    except Exception as exc:
        # Never leave a previous successful ranking/GO visible after a failed rerun.
        for name in ("ranked_review.csv", "image_decisions.csv", "decision.json"):
            ctx.out(name).unlink(missing_ok=True)
        ctx.audit.log(actor="pipeline", action="run_failed", item_id=ctx.run_name,
                      reason=f"{type(exc).__name__}: {exc}")
        owner = ctx.config.get("owner")
        if isinstance(owner, str) and owner.strip():
            write_decision(Decision(status="HOLD", reason_code="RUN_FAILED", reason=str(exc), owner=owner,
                                    scope=ctx.track, evidence=[str(ctx.out("audit_log.jsonl"))]),
                           ctx.out("decision.json"), ctx.out("decision_log.csv"))
        ctx.stats["decision_status"] = "HOLD"
        raise
