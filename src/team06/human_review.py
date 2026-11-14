"""Human Review & Demo — Nguyễn Tuấn Minh, 2A202603349.

Bridge to the Lead's policy. Minh can extend UI/demo without changing decision
semantics, raw scores or audit requirements in team06.policy.
"""
from __future__ import annotations

import pandas as pd

from ..common.context import RunContext
from ..common.review import REVIEW_COLUMNS, load_review_decisions
from .policy import apply_review_decisions


def apply_human_review(ctx: RunContext, scored: pd.DataFrame, queue: pd.DataFrame) -> pd.DataFrame:
    """Read the CSV exported by the existing offline contact sheet or filled by hand."""
    reviewed_path = ctx.output_dir / "review_queue_reviewed.csv"
    reviewed = (load_review_decisions(reviewed_path) if reviewed_path.exists()
                else pd.DataFrame(columns=REVIEW_COLUMNS))
    return apply_review_decisions(ctx, scored, queue, reviewed)
