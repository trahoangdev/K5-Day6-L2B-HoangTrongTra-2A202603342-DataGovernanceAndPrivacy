"""T02 decision rules — Hoàng Trọng Trà, 2A202603342.

Consumes scorer actions, not score thresholds or GT. Mandatory top-B review;
unresolved uncertainty stays REVIEW. HOLD > REWORK > GO. See reports/group_report.md.
"""
from __future__ import annotations

import math

import pandas as pd

from ..common.context import RunContext
from ..common.decision import Decision


POLICY_VERSION = "t02-lead-v1"
ACTIONS = {"KEEP", "RECAPTURE", "REVIEW"}
RESOLVED_ACTIONS = {"KEEP", "RECAPTURE"}


def validate_settings(ctx: RunContext) -> None:
    if not isinstance(ctx.config.get("owner"), str) or not ctx.config["owner"].strip():
        raise ValueError("T02 policy requires a non-empty owner")
    if ctx.param("policy_version", POLICY_VERSION) != POLICY_VERSION:
        raise ValueError(f"Unsupported T02 policy_version; expected {POLICY_VERSION}")
    budget = ctx.param("budget", 20)
    if isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0:
        raise ValueError("T02 budget must be a positive integer")
    if ctx.param("review_split", "all") not in {"all", "dev", "eval"}:
        raise ValueError("T02 review_split must be all, dev or eval")


def prepare_actions(ctx: RunContext, scored: pd.DataFrame, queue: pd.DataFrame) -> pd.DataFrame:
    """Preserve automatic suggestions and mark mandatory human decisions pending."""
    final = scored.copy()
    final["auto_action"] = final["pred_action"]
    final["review_required"] = final.image_id.isin(queue.item_id) | final.auto_action.eq("REVIEW")
    final["review_status"] = "not_required"
    final["reviewer"] = ""
    final["review_note"] = ""
    final["action_owner"] = ctx.config["owner"]
    final["reason_code"] = "AUTO_" + final.auto_action
    final["action_reason"] = final.reason.where(final.reason.str.strip().ne(""), "Automatic scorer suggestion")
    required = final.review_required
    final.loc[required, "pred_action"] = "REVIEW"
    final.loc[required, "review_status"] = "pending"
    final.loc[required, "reason_code"] = "REVIEW_REQUIRED"
    final.loc[required, "action_reason"] = "Top-B audit or uncertain scorer action requires human review"
    return final


def apply_review_decisions(ctx: RunContext, scored: pd.DataFrame, queue: pd.DataFrame,
                           reviewed: pd.DataFrame) -> pd.DataFrame:
    """Validate all rows before applying changes. Scores and metadata stay untouched.

    approve accepts a concrete suggestion; reject rejects the image (RECAPTURE);
    edit requires KEEP/RECAPTURE; escalate and skip remain unresolved REVIEW.
    """
    final = prepare_actions(ctx, scored, queue)
    if reviewed.item_id.duplicated().any():
        raise ValueError("Duplicate item_id in reviewed queue")
    queue_by_id = queue.set_index("item_id")
    unknown = set(reviewed.item_id) - set(queue_by_id.index)
    if unknown:
        raise ValueError(f"Reviewed IDs are outside the current queue: {sorted(unknown)}")
    changes = []
    for row in reviewed.itertuples(index=False):
        original = queue_by_id.loc[row.item_id]
        try:
            score = float(row.score)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid review score for {row.item_id}") from exc
        if not math.isfinite(score) or not math.isclose(score, float(original.score), rel_tol=0, abs_tol=1e-9):
            raise ValueError(f"Review score does not match current queue for {row.item_id}")
        for col in ("rank", "reason", "suggested_action", "slice", "evidence_path"):
            if str(getattr(row, col)) != str(original[col]):
                raise ValueError(f"Reviewed {col} does not match current queue for {row.item_id}")
        actor, note = row.reviewer.strip(), row.review_note.strip()
        if not actor or not note:
            raise ValueError(f"Reviewer and review_note are mandatory for {row.item_id}")
        override = row.override_value.strip().upper()
        suggestion, decision = original.suggested_action, row.reviewer_decision
        if decision == "edit":
            if override not in RESOLVED_ACTIONS:
                raise ValueError(f"edit requires override_value KEEP or RECAPTURE for {row.item_id}")
            action, status = override, "edited"
        else:
            if override:
                raise ValueError(f"Use edit to supply override_value for {row.item_id}")
            if decision == "approve":
                if suggestion not in RESOLVED_ACTIONS:
                    raise ValueError(f"Cannot approve unresolved REVIEW for {row.item_id}; use edit")
                action, status = suggestion, "approved"
            elif decision == "reject":
                action, status = "RECAPTURE", "rejected"
            elif decision in {"escalate", "skip"}:
                action, status = "REVIEW", {"escalate": "escalated", "skip": "skipped"}[decision]
            else:
                raise ValueError(f"Unknown reviewer_decision {decision!r}")
        changes.append((row.item_id, actor, note, decision, action, status))

    for item_id, actor, note, decision, action, status in changes:
        mask = final.image_id.eq(item_id)
        before = final.loc[mask, "pred_action"].item()
        final.loc[mask, ["pred_action", "review_status", "reviewer", "review_note", "action_owner",
                         "reason_code", "action_reason"]] = [
            action, status, actor, note, actor, f"HUMAN_{status.upper()}", note,
        ]
        if ctx.audit is not None:
            ctx.audit.log(actor=actor, action=f"review:{decision}", item_id=item_id,
                          before={"pred_action": before, "auto_action": final.loc[mask, "auto_action"].item()},
                          after={"pred_action": action, "review_status": status}, reason=note,
                          run_fingerprint=ctx.stats.get("review_fingerprint"))
    ctx.stats["n_reviewed"] = len(changes)
    return final


def decide(ctx: RunContext, final: pd.DataFrame) -> Decision:
    """Run-level triage gate; GO does not claim heldout accuracy or legal compliance."""
    validate_settings(ctx)
    counts = final.pred_action.value_counts() if "pred_action" in final else pd.Series(dtype=int)
    metrics = {
        "policy_version": POLICY_VERSION, "n_items": len(final),
        "n_keep": int(counts.get("KEEP", 0)), "n_recapture": int(counts.get("RECAPTURE", 0)),
        "n_pending": int(counts.get("REVIEW", 0)),
        "review_split": ctx.param("review_split", "all"), "budget": ctx.param("budget", 20),
        "n_queued": ctx.stats.get("n_queued", 0), "n_reviewed": ctx.stats.get("n_reviewed", 0),
        "n_escalated": int(final.review_status.eq("escalated").sum()) if "review_status" in final else 0,
        "n_skipped": int(final.review_status.eq("skipped").sum()) if "review_status" in final else 0,
    }
    if not len(final):
        status, code, reason = "HOLD", "EMPTY_INPUT", "No images are available for a release decision"
    elif not ctx.stats.get("provenance_verified", False):
        status, code, reason = "HOLD", "PROVENANCE_UNVERIFIED", "Verified input provenance is required"
    elif not ctx.offline:
        status, code, reason = "HOLD", "OFFLINE_REQUIRED", "The lab release gate requires an offline run"
    elif not {"pred_action", "review_required", "review_status"} <= set(final.columns):
        status, code, reason = "HOLD", "INCOMPLETE_POLICY_EVIDENCE", "Missing per-image review evidence"
    elif not final.pred_action.isin(ACTIONS).all():
        status, code, reason = "HOLD", "INVALID_IMAGE_ACTION", "Image decisions contain unsupported actions"
    elif metrics["n_pending"] or final.review_status.isin(["pending", "skipped", "escalated"]).any():
        status, code, reason = "HOLD", "REVIEW_PENDING", "Required reviews, skips or escalations remain unresolved"
    elif (final.review_required & ~final.review_status.isin(["approved", "rejected", "edited"])).any():
        status, code, reason = "HOLD", "INCOMPLETE_POLICY_EVIDENCE", "Required review is not evidenced as resolved"
    elif metrics["n_recapture"]:
        status, code, reason = "REWORK", "RECAPTURE_REQUIRED", "Recapture is required before releasing this input set"
    else:
        status, code, reason = "GO", "TRIAGE_COMPLETE", "Required reviews are resolved and all image actions are KEEP"
    return Decision(
        status=status, reason_code=code, reason=reason, owner=ctx.config["owner"], scope=ctx.track,
        evidence=[str(ctx.out(name)) for name in (
            "raw_predictions.csv", "ranked_review.csv", "image_decisions.csv", "review_queue.csv",
            "review_context.json", "policy_snapshot.json", "audit_log.jsonl",
        )], metrics=metrics,
    )
