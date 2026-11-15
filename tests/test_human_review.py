"""Human-review sheet checks — Nguyễn Tuấn Minh, 2A202603349."""
import pandas as pd
import pytest

from src.common.review import REVIEW_COLUMNS
from src.team06.human_review import merge_review_decisions


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
    sheet = merge_review_decisions(_queue(), decisions, "Nguyễn Tuấn Minh - 2A202603349", reviewed_at="2026-11-16T00:00:00+00:00")
    assert list(sheet.columns) == REVIEW_COLUMNS
    edited = sheet.set_index("item_id").loc["img_18_2"]
    assert edited.score == "1.728876"
    assert edited.suggested_action == "RECAPTURE"
    assert edited.reviewer_decision == "edit" and edited.override_value == "KEEP"
    assert edited.reviewer == "Nguyễn Tuấn Minh - 2A202603349"
    pending = sheet.set_index("item_id").loc["img_12_3"]
    assert pending.reviewer_decision == "" and pending.reviewer == ""


def test_merge_rejects_ids_outside_the_live_queue():
    decisions = pd.DataFrame([
        {"item_id": "not-in-queue", "reviewer_decision": "approve", "override_value": "", "review_note": "no"},
    ])
    with pytest.raises(ValueError, match="outside the current queue"):
        merge_review_decisions(_queue(), decisions, "Nguyễn Tuấn Minh - 2A202603349")
