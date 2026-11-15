"""Human Review & Demo — Nguyễn Tuấn Minh, 2A202603349.

Bridge to the Lead's policy. The demo sheet may fill reviewer fields only.
Decision semantics, raw scores and audit requirements stay in team06.policy.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from ..common.context import RunContext
from ..common.review import DEFAULT_ALLOWED_DECISIONS, REVIEW_COLUMNS, load_review_decisions
from .policy import RESOLVED_ACTIONS, apply_review_decisions

REVIEWER = "Nguyễn Tuấn Minh - 2A202603349"
DECISION_COLUMNS = ["item_id", "reviewer_decision", "override_value", "review_note"]


def apply_human_review(ctx: RunContext, scored: pd.DataFrame, queue: pd.DataFrame) -> pd.DataFrame:
    """Read the CSV exported by the offline contact sheet or written by the demo."""
    reviewed_path = ctx.output_dir / "review_queue_reviewed.csv"
    reviewed = (load_review_decisions(reviewed_path) if reviewed_path.exists()
                else pd.DataFrame(columns=REVIEW_COLUMNS))
    return apply_review_decisions(ctx, scored, queue, reviewed)


def merge_review_decisions(queue: pd.DataFrame, decisions: pd.DataFrame, reviewer: str,
                           reviewed_at: str = "") -> pd.DataFrame:
    """Copy the live queue and fill reviewer fields. Rank, score and evidence stay untouched.

    IDs that are not in the current queue are rejected before any row is written.
    A partial sheet is valid: unresolved queue rows stay blank and the run remains HOLD.
    """
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("reviewer name is mandatory")
    missing = [column for column in REVIEW_COLUMNS if column not in queue.columns]
    if missing:
        raise ValueError(f"queue missing columns: {missing}")
    required = ["item_id", "reviewer_decision", "review_note"]
    missing_decisions = [column for column in required if column not in decisions.columns]
    if missing_decisions:
        raise ValueError(f"decisions missing columns: {missing_decisions}")

    sheet = queue.loc[:, REVIEW_COLUMNS].copy()
    for column in ("reviewer", "reviewer_decision", "override_value", "review_note", "reviewed_at"):
        sheet[column] = ""
    sheet["item_id"] = sheet["item_id"].astype(str)
    if decisions.empty:
        return sheet.reset_index(drop=True)

    work = decisions.copy()
    work["item_id"] = work["item_id"].astype(str).str.strip()
    work["reviewer_decision"] = work["reviewer_decision"].fillna("").astype(str).str.strip().str.lower()
    work["review_note"] = work["review_note"].fillna("").astype(str).str.strip()
    if "override_value" not in work.columns:
        work["override_value"] = ""
    work["override_value"] = work["override_value"].fillna("").astype(str).str.strip()
    work = work[work["reviewer_decision"] != ""].copy()
    if work.empty:
        return sheet.reset_index(drop=True)
    if work["item_id"].duplicated().any():
        raise ValueError("Duplicate item_id in review decisions")
    unknown = sorted(set(work["item_id"]) - set(sheet["item_id"]))
    if unknown:
        raise ValueError(f"Decision IDs are outside the current queue: {unknown}")
    bad = sorted(set(work["reviewer_decision"]) - set(DEFAULT_ALLOWED_DECISIONS))
    if bad:
        raise ValueError(f"unknown reviewer_decision values {bad}; allowed={sorted(DEFAULT_ALLOWED_DECISIONS)}")
    blank_notes = work[work["review_note"] == ""]
    if len(blank_notes):
        raise ValueError(f"review_note is mandatory for {blank_notes.item_id.tolist()}")

    stamped = reviewed_at.strip() or datetime.now(timezone.utc).isoformat(timespec="seconds")
    indexed = sheet.set_index("item_id")
    for row in work.itertuples(index=False):
        override = row.override_value.upper()
        if row.reviewer_decision == "edit":
            if override not in RESOLVED_ACTIONS:
                raise ValueError(f"edit requires override_value KEEP or RECAPTURE for {row.item_id}")
        elif override:
            raise ValueError(f"Use edit to supply override_value for {row.item_id}")
        else:
            override = ""
        indexed.loc[row.item_id, ["reviewer", "reviewer_decision", "override_value", "review_note", "reviewed_at"]] = [
            reviewer.strip(), row.reviewer_decision, override, row.review_note, stamped,
        ]
    return indexed.reset_index()[REVIEW_COLUMNS]
