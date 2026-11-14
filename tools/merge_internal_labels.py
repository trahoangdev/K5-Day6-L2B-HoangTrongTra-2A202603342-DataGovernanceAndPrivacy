"""Measure labelling agreement and build the adjudication list.

Two modes, chosen automatically from the `annotator` column:

  * **inter-annotator** — two different people labelled the same images.
    Cohen's kappa here means what it usually means: do we agree on what a
    defect is? This is the mode the protocol prefers.
  * **test-retest** — the same person labelled a subset twice, with a gap.
    Reported as self-consistency, NOT as inter-annotator agreement. It is the
    fallback when only one person is available; it detects unstable criteria
    but cannot detect a bias the single annotator holds consistently.

Implements step 3 of `reports/group_report.md`:
  * Cohen's kappa on `is_defect` (the binary the primary metric depends on);
  * raw agreement on `defect_type`;
  * the list of images the two annotators disagree on, for joint adjudication;
  * a merged file where agreed rows are filled in and disagreements left blank.

Usage:
    python tools/merge_internal_labels.py --a out/labels_A.csv \
                                          --b out/labels_B.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

KAPPA_MIN = 0.70
AGREE_MIN = 0.70


def cohen_kappa(a: pd.Series, b: pd.Series) -> float | None:
    """Unweighted Cohen's kappa for two aligned categorical series."""
    n = len(a)
    if n == 0:
        return None
    po = float((a.values == b.values).mean())
    cats = sorted(set(a) | set(b))
    pe = sum((a == c).mean() * (b == c).mean() for c in cats)
    if pe >= 1.0:
        return 1.0 if po >= 1.0 else None
    return (po - pe) / (1 - pe)


def load(path: Path, who: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str).fillna("")
    need = {"image_id", "defect_type", "is_defect"}
    missing = need - set(df.columns)
    if missing:
        raise SystemExit(f"{path}: thiếu cột {sorted(missing)}")
    blank = df[df.defect_type == ""]
    if len(blank):
        raise SystemExit(f"{path}: còn {len(blank)} ảnh chưa gán nhãn "
                         f"(ví dụ {list(blank.image_id.head(3))}) — gán hết rồi hãy chạy lại")
    if df.image_id.duplicated().any():
        raise SystemExit(f"{path}: có image_id trùng")
    return df.set_index("image_id").add_suffix(f"_{who}")


def reconcile_labels(m: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Only complete agreement on every compared field is an agreed label.

    Severity is optional for legacy files, but must exist on both sides when
    either provides it. Blank fields never count as resolved agreement.
    """
    fields = ["defect_type", "is_defect"]
    if {"severity_A", "severity_B"} & set(m.columns):
        if not {"severity_A", "severity_B"} <= set(m.columns):
            raise ValueError("severity must be supplied in both labelling files")
        fields.insert(1, "severity")
    merged = pd.DataFrame(index=m.index)
    agreed = pd.Series(True, index=m.index, dtype=bool)
    for field in fields:
        left = m[f"{field}_A"].fillna("").astype(str).str.strip()
        right = m[f"{field}_B"].fillna("").astype(str).str.strip()
        same = left.eq(right) & left.ne("") & right.ne("")
        merged[field] = left.where(same, "")
        agreed &= same
    merged["status"] = agreed.map({True: "agreed", False: "NEEDS_ADJUDICATION"})
    merged["note"] = ""
    columns = [f"{field}_{side}" for field in fields for side in ("A", "B")]
    return merged, m.loc[~agreed, columns]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="out/labels_A.csv")
    ap.add_argument("--b", default="out/labels_B.csv")
    ap.add_argument("--out", default="out/labels_merged.csv")
    ap.add_argument("--disagree", default="out/label_disagreements.csv")
    ap.add_argument("--retest", action="store_true",
                    help="ép chế độ test-retest (mặc định tự nhận từ cột annotator)")
    args = ap.parse_args(argv)
    root = Path(__file__).resolve().parents[1]

    A, B = load(root / args.a, "A"), load(root / args.b, "B")
    who_a = A["annotator_A"].iloc[0] if "annotator_A" in A.columns else "?"
    who_b = B["annotator_B"].iloc[0] if "annotator_B" in B.columns else "?"
    retest = args.retest or (who_a == who_b and who_a != "?")
    mode = "TEST-RETEST (cùng một người gán hai lượt)" if retest else "INTER-ANNOTATOR (hai người gán độc lập)"
    label = "nhất quán với chính mình" if retest else "đồng thuận giữa hai người"
    print(f"Chế độ: {mode}")
    only_a, only_b = A.index.difference(B.index), B.index.difference(A.index)
    if len(only_a) or len(only_b):
        print(f"CẢNH BÁO: chỉ A có {len(only_a)} ảnh, chỉ B có {len(only_b)} ảnh — so trên phần chung")
    m = A.join(B, how="inner")
    n = len(m)
    if not n:
        raise SystemExit("Không có image_id chung để đối soát nhãn")

    k = cohen_kappa(m.is_defect_A, m.is_defect_B)
    agree_type = float((m.defect_type_A == m.defect_type_B).mean())
    agree_bin = float((m.is_defect_A == m.is_defect_B).mean())

    print(f"N chung = {n}")
    print(f"  {label} trên is_defect  : {agree_bin:.3f}")
    print(f"  Cohen's kappa is_defect : {k:.3f}" if k is not None else "  Cohen's kappa: không tính được")
    print(f"  {label} trên defect_type: {agree_type:.3f}")
    fails = []
    if k is not None and k < KAPPA_MIN:
        fails.append(f"kappa {k:.3f} < {KAPPA_MIN}")
    if agree_type < AGREE_MIN:
        fails.append(f"đồng thuận defect_type {agree_type:.3f} < {AGREE_MIN}")
    print("  -> ĐẠT ngưỡng nhất quán; vẫn cần đối soát mọi trường bên dưới"
          if not fails else "  -> CHƯA ĐẠT: " + "; ".join(fails))
    if retest:
        print("  LƯU Ý: đây là độ nhất quán của một người, KHÔNG phải kappa giữa hai người.")
        print("         Báo cáo phải ghi rõ 'một người gán, test-retest trên N=%d'." % n)

    print("\nMa trận chéo defect_type (hàng = A, cột = B):")
    print(pd.crosstab(m.defect_type_A, m.defect_type_B).to_string())

    merged, dis = reconcile_labels(m)
    dis.to_csv(root / args.disagree, lineterminator="\n")
    print(f"\n{len(dis)} ảnh lệch nhau -> {args.disagree} (cần xem lại và chốt nhãn)")

    merged.to_csv(root / args.out, lineterminator="\n")
    print(f"{int(merged.status.eq('agreed').sum())}/{n} ảnh thống nhất mọi trường -> {args.out}")
    print("Điền nốt các dòng NEEDS_ADJUDICATION rồi lưu thành reports/internal_labels_t02_final.csv")
    return 1 if fails or len(dis) else 0


if __name__ == "__main__":
    raise SystemExit(main())
