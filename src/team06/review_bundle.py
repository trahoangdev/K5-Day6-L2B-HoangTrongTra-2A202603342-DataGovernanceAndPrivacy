"""Bound review replay, based on Nguyễn Tuấn Minh's commit 2bedc49.

Protocol v2 is separate from the frozen v1 pipeline. Replay uses recorded human
decisions and their original timestamp; it never creates a human confirmation.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json

import pandas as pd

from ..common.io import config_hash, sha256_file, sha256_text
from ..common.review import DEFAULT_ALLOWED_DECISIONS, REVIEW_COLUMNS
from .policy import RESOLVED_ACTIONS

VERSION = "team06-review-bundle-v2"
IMMUTABLE_COLUMNS = REVIEW_COLUMNS[:7]


def queue_digest(queue: pd.DataFrame) -> str:
    missing = set(REVIEW_COLUMNS) - set(queue.columns)
    if missing:
        raise ValueError(f"queue missing columns: {sorted(missing)}")
    if queue.item_id.isna().any() or queue.item_id.astype(str).str.strip().eq("").any():
        raise ValueError("Queue item_id must be non-empty")
    if queue.item_id.astype(str).duplicated().any():
        raise ValueError("Duplicate item_id in live queue")
    return sha256_text(queue[IMMUTABLE_COLUMNS].astype(str).to_csv(index=False, lineterminator="\n"))


def validate_context(actual: dict, expected: dict) -> None:
    keys = {"policy_version", "config_hash", "seed", "input_manifest_sha256",
            "scored_sha256", "queue_ids", "fingerprint"}
    if set(actual) != keys or actual != expected:
        raise ValueError("Review bundle does not match current run context; review the new run separately")
    binding = {key: value for key, value in actual.items() if key != "fingerprint"}
    if config_hash(binding) != actual["fingerprint"]:
        raise ValueError("Invalid review context fingerprint")


def merge_review_decisions(queue: pd.DataFrame, decisions: pd.DataFrame, reviewer: str,
                           reviewed_at: str, *, review_context: dict,
                           expected_context: dict, expected_queue_sha256: str) -> pd.DataFrame:
    """Fill reviewer fields only after validating the exact reviewed run and queue.

    Partial decisions stay partial. Scores, order and suggestions are immutable.
    The timestamp must come from the saved record, never from the replay clock.
    """
    validate_context(review_context, expected_context)
    if queue_digest(queue) != expected_queue_sha256:
        raise ValueError("Saved review does not match live queue contents")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("reviewer name is mandatory")
    try:
        recorded = datetime.fromisoformat(reviewed_at)
        if recorded.tzinfo is None:
            raise ValueError("Timezone is required")
    except (TypeError, ValueError) as exc:
        raise ValueError("Recorded review timestamp with timezone is mandatory") from exc
    required = {"item_id", "reviewer_decision", "review_note"}
    if not required <= set(decisions.columns):
        raise ValueError(f"decisions missing columns: {sorted(required - set(decisions.columns))}")
    sheet = queue[REVIEW_COLUMNS].copy()
    for column in REVIEW_COLUMNS[7:]:
        sheet[column] = ""
    sheet["item_id"] = sheet.item_id.astype(str)
    work = decisions.copy().fillna("")
    work["item_id"] = work.item_id.astype(str).str.strip()
    work["reviewer_decision"] = work.reviewer_decision.astype(str).str.strip().str.lower()
    work["review_note"] = work.review_note.astype(str).str.strip()
    if "override_value" not in work:
        work["override_value"] = ""
    work["override_value"] = work.override_value.astype(str).str.strip().str.upper()
    work = work.loc[work.reviewer_decision.ne("")]
    if work.item_id.duplicated().any():
        raise ValueError("Duplicate item_id in review decisions")
    unknown = sorted(set(work.item_id) - set(sheet.item_id))
    if unknown:
        raise ValueError(f"Decision IDs are outside the current queue: {unknown}")
    bad = sorted(set(work.reviewer_decision) - set(DEFAULT_ALLOWED_DECISIONS))
    if bad:
        raise ValueError(f"Unknown reviewer_decision values: {bad}")
    indexed = sheet.set_index("item_id")
    for row in work.itertuples(index=False):
        if not row.review_note:
            raise ValueError(f"review_note is mandatory for {row.item_id}")
        if row.reviewer_decision == "edit":
            if row.override_value not in RESOLVED_ACTIONS:
                raise ValueError(f"edit requires override_value KEEP or RECAPTURE for {row.item_id}")
        elif row.override_value:
            raise ValueError(f"Use edit to supply override_value for {row.item_id}")
        if row.reviewer_decision == "approve" and indexed.loc[row.item_id, "suggested_action"] not in RESOLVED_ACTIONS:
            raise ValueError(f"Cannot approve unresolved REVIEW for {row.item_id}; use edit")
        indexed.loc[row.item_id, REVIEW_COLUMNS[7:]] = [
            reviewer.strip(), row.reviewer_decision, row.override_value, row.review_note, reviewed_at,
        ]
    return indexed.reset_index()[REVIEW_COLUMNS]


def read_bound_review(run_dir: Path, bundle_path: Path, protocol_path: Path, root: Path) -> pd.DataFrame:
    """Verify frozen v2 sources plus actual run artifacts, then replay saved input."""
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("version") != VERSION:
        raise ValueError("Unsupported review protocol")
    try:
        relative_bundle = bundle_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("Bundle must be in the protocol repository") from exc
    required = {relative_bundle, "src/team06/review_bundle.py", "demo/apply_review.py",
                "configs/protocol_freeze.json"}
    hashes = protocol.get("sha256", {})
    if not required <= set(hashes):
        raise ValueError("Review protocol must bind bundle, implementation and legacy freeze")
    for path, expected in hashes.items():
        if sha256_file(root / path) != expected:
            raise ValueError(f"Frozen review protocol changed: {path}")
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    if bundle.get("version") != VERSION:
        raise ValueError("Unsupported review bundle")
    context = json.loads((run_dir / "review_context.json").read_text(encoding="utf-8"))
    validate_context(context, bundle["context"])
    info = json.loads((run_dir / "run_info.json").read_text(encoding="utf-8"))
    if (info.get("status") != 0 or info.get("offline") is not True or info.get("track") != "t02"
            or info.get("config_hash") != context["config_hash"] or info.get("seed") != context["seed"]
            or (root / info["output"]).resolve() != run_dir.resolve()):
        raise ValueError("Run metadata does not match the bound offline run")
    manifest = root / info["input"] / "manifest.csv"
    raw = (run_dir / "raw_predictions.csv").read_text(encoding="utf-8")
    if (sha256_file(manifest) != context["input_manifest_sha256"]
            or sha256_text(raw) != context["scored_sha256"]):
        raise ValueError("Current input or raw scores differ from the saved review")
    queue = pd.read_csv(run_dir / "review_queue.csv", dtype=str).fillna("")
    if queue_digest(queue) != bundle["queue_sha256"]:
        raise ValueError("Saved review does not match live queue contents")
    if queue.item_id.tolist() != context["queue_ids"]:
        raise ValueError("Current queue IDs differ from the saved review")
    decisions = pd.DataFrame(bundle["decisions"], columns=[
        "item_id", "reviewer_decision", "override_value", "review_note"])
    return merge_review_decisions(
        queue, decisions, bundle["reviewer"], bundle["recorded_at"],
        review_context=context, expected_context=bundle["context"],
        expected_queue_sha256=bundle["queue_sha256"],
    )
