"""Build the shared Team 6 offline HTML deck from committed evidence.

    python -m tools.build_demo_html

Embeds synthetic images and the OFL Manrope font. Never embeds real BDD images.
Requires no network. Reuses the font already embedded in demo/index.html when rebuilding.
"""
from __future__ import annotations

import base64
import html
import json
import os
from pathlib import Path
import re

import pandas as pd

from tools.prepare_submission import read_test_counts

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    os.chdir(ROOT)
    target = Path("demo/index.html")
    font_file = Path("out/submission/Manrope.ttf")
    if font_file.exists():
        font = base64.b64encode(font_file.read_bytes()).decode("ascii")
    elif target.exists():
        match = re.search(r"data:font/ttf;base64,([A-Za-z0-9+/=]+)", target.read_text(encoding="utf-8"))
        if not match:
            raise ValueError("The existing deck has no embedded font")
        font = match[1]
    else:
        raise ValueError("Need existing demo/index.html embedded font or out/submission/Manrope.ttf")
    b, p = [read(f"reports/metrics_{n}.json") for n in ("baseline", "poc")]
    decision = read("reports/submission/poc/decision.json")
    ood = read("reports/submission/ood_summary.json")
    clean = read("reports/submission/clean_checkout.json")
    if not clean["raw_scores_replay_matched"] or decision["status"] != "HOLD":
        raise ValueError("Review the deck narrative against changed evidence")
    tests = read_test_counts()
    if not tests["passed"] or tests["failed"] or tests["errors"]:
        raise ValueError("Expected a passing test summary")
    roster = [
        ("Hoàng Trọng Trà", "2A202603342", "Lead / Integrator"),
        ("Nguyễn Quốc Hưng", "2A202603324", "Data & Provenance"),
        ("Phạm Văn Dương", "2A202603332", "Baseline & Research"),
        ("Nguyễn Nhật Hạ", "2A202603325", "Core Algorithm / PoC"),
        ("Lê Trần Phi Hùng", "2A202603353", "QA & Evaluation"),
        ("Nguyễn Tuấn Minh", "2A202603349", "Human Review & Demo"),
    ]
    members = "".join(f'<div class="member"><strong>{name}</strong><span class="identity">{sid}</span><span class="role">{html.escape(role)}</span></div>' for name, sid, role in roster)
    rows = []
    for key, label in (("Defect Recall@B", "Defect Recall@20"), ("Precision@B", "Precision@20"),
                       ("Defect-type accuracy (GT defects)", "Defect type accuracy")):
        values = [next(m for m in d["metrics"] if m["name"] == key) for d in (b, p)]
        cells = []
        for m in values:
            ratio = (f'{m["numerator"]}/{m["denominator"]}' if m["denominator"] is not None else f'N = {m["n"]}')
            cells.append(f'<td>{m["value"]*100:.2f}%<span class="ratio">{ratio}</span></td>')
        rows.append(f'<tr><td>{label}</td>{"".join(cells)}</tr>')
    slices = pd.read_csv("reports/submission/slices.csv")
    blocks = []
    for key, label in (("defect_type=blur", "Blur"), ("defect_type=glare", "Glare"), ("defect_type=dark", "Dark")):
        group = slices.loc[slices.slice.eq(key)]
        bars = []
        for run, title in (("baseline", "Baseline"), ("poc", "PoC")):
            row = group.loc[group.run.eq(run)].iloc[0]
            bars.append(f'<div class="bar-row"><span>{title}</span><div class="bar-track"><div class="bar {run}" style="--value:{row.recall*100:.6f}%"></div></div><span>{int(row.hits_in_global_dev_top20)}/{int(row.positives)}</span></div>')
        blocks.append(f'<div class="slice-block"><div class="slice-title">{label}</div>{"".join(bars)}</div>')
    notes = [
        {"timing": "Slide 1 · 25 giây", "html": "<p>Giới thiệu bài toán và sáu thành viên theo phân công ban đầu. Đây là sản phẩm chung của Team6. Trà là Lead, không phải tên chủ sở hữu riêng của bài trình bày.</p><p>Phân công không đồng nghĩa mọi người đã có Git evidence. Phần còn lại do Lead tiếp quản; chưa ghi nhận commit thực chất của Minh, xem team_contributions.csv.</p>"},
        {"timing": "Slide 2 · 40 giây", "html": "<p>Đi đủ năm bước BTC yêu cầu. Baseline một ngưỡng Laplacian toàn ảnh. PoC đa feature, calibration dev, session references phụ thuộc batch. Giữ GT guard và evaluator gốc.</p><p>Freeze ghi nhận 2026 11 14 trước lần sinh hồ sơ, sau quá trình quan sát dev. Không tuyên bố đã freeze phút30. Candidate pool, split theo scene, seed42 và B20 giữ nguyên. Nguồn phương pháp: OpenCV Laplace Operator và SciPy binary_erosion trong group_report.md.</p>"},
        {"timing": "Slide 3 · 40 giây", "html": "<p>Primary Defect Recall@B là số lỗi trong top B chia tổng lỗi thật; Precision@B là số lỗi tìm được chia số ảnh chọn. Lọc split trước ranking. Cả hai đạt20/34, trần khả thi trên dev này, nên không tuyên bố PoC hơn ở primary.</p><p>Type accuracy là secondary trên34 ảnh lỗi. CamA hit Baseline8/19, PoC12/19; camB12/15 và8/15. Night1/3 cho cả hai, Nnight=4. CI Wilson chỉ mô tả dev, không là confidence tổng quát hóa. Runtime một lần ở metrics JSON, không phải benchmark ổn định.</p>"},
        {"timing": "Slide 4 · 45 giây", "html": "<p>Trà đã xem và xác nhận RECAPTURE cả20 trong chat. Không coi AI proposal là human approval. CSV và confirmation giữ đúng actor, audit ghi before/after; approve không sửa score.</p><p>Trước review:40 KEEP,31 RECAPTURE,25 pending. Sau review:40 KEEP,51 RECAPTURE,5 pending. HOLD/REVIEW_PENDING. Pending: img_15_0, img_09_0, img_16_3, img_08_2, img_19_2. Không tăng budget để làm đẹp quyết định.</p><p>Ảnh đêm hữu ích, glare cục bộ và ranking blur minh họa failure analysis. Camera mềm: chưa chứng minh camB mềm có hệ thống bằng dữ liệu sạch; không dựng kết luận theo trung vị trộn corruption.</p>"},
        {"timing": "Slide 5 · 30 giây · Tổng khoảng 3 phút", "html": "<p>Mở terminal chạy một lệnh tái lập, rồi xem decision.json và contact sheet. Clean checkout đã xác minh không cần download dữ liệu thật để tái lập fixture/demo.39 tests skip do cần GT instructor. Khi có official GT, giảng viên chạy evaluator split eval; không tune sau kết quả.</p><p>10 OOD thật đều foggy do rare first sampler seed42, không đại diện phân phối thật. Toàn bộ bị đề xuất RECAPTURE có thể là false alarm/domain shift. Không có QC GT để báo accuracy. Ảnh thật giữ local.</p><p>Checklist còn thiếu: official eval, Git evidence thành viên thứ6, bằng chứng tag demo180m/final24h đúng mốc. Không tự gán điểm rubric hoặc tuyên bố đạt tất cả guideline. Không giả tag lịch sử.</p>"},
    ]
    tokens = {"FONT": font, "FONT_LICENSE": Path("demo/Manrope-OFL.txt").read_text(encoding="utf-8"), "ROSTER": members, "METRIC_ROWS": "".join(rows),
              "SLICES": "".join(blocks), "PASSED": str(tests["passed"]), "SKIPPED": str(tests["skipped"]),
              "REVIEWED": str(decision["metrics"]["n_reviewed"]), "KEEP": str(decision["metrics"]["n_keep"]),
              "RECAPTURE": str(decision["metrics"]["n_recapture"]), "PENDING": str(decision["metrics"]["n_pending"]),
              "OOD_N": str(ood["n_scored"]), "DOTS": "".join(f'<button type="button" aria-label="Slide {n}" aria-current="{str(n==1).lower()}">{n}</button>' for n in range(1, 6)),
              "DATA": json.dumps({"team": "Team 6", "notes": notes, "btc_commit": "b0ce8bfd972315448aace86185c1a3e075754b93", "metric_scope": "internal_dev_in_sample_not_official"}, ensure_ascii=False).replace("</", "<\\/")}
    for token, name in (("NIGHT", "img_18_1"), ("GLARE", "img_20_3"), ("BLUR", "img_18_3")):
        pixels = Path(f"fixtures/t02_raw_qc/images/{name}.jpg").read_bytes()
        tokens[token] = "data:image/jpeg;base64," + base64.b64encode(pixels).decode("ascii")
    text = Path("demo/slides.template.html").read_text(encoding="utf-8")
    for token, value in tokens.items():
        text = text.replace(f"@@{token}@@", value)
    if "@@" in text:
        raise ValueError("Unresolved template token")
    target.write_text(text, encoding="utf-8", newline="\n")
    print(f"Built {target}: 5 shared team slides, offline font/images, {len(text.encode('utf-8'))} bytes")


if __name__ == "__main__":
    main()
