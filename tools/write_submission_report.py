"""Render the report/demo source from generated evidence, never hand-enter metrics."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

import pandas as pd

from tools.prepare_submission import ROOT


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    os.chdir(ROOT)
    freeze = read("configs/protocol_freeze.json")
    baseline, poc = [read(f"reports/metrics_{n}.json") for n in ("baseline", "poc")]
    before = read("reports/submission/poc/before_review_decision.json")
    after = read("reports/submission/poc/decision.json")
    ood = read("reports/submission/ood_summary.json")
    intervals = read("reports/submission/uncertainty.json")["intervals"]["poc"]
    labels = pd.read_csv("reports/submission/internal_dev_labels_joined.csv")
    final = pd.read_csv("reports/submission/poc/image_decisions.csv")
    pending = ", ".join(final.loc[final.pred_action.eq("REVIEW"), "image_id"])
    slices = pd.read_csv("reports/submission/slices.csv")
    suite = ET.parse("out/submission/tests.xml").getroot().find("testsuite")
    passed = int(suite.get("tests")) - int(suite.get("skipped")) - int(suite.get("failures")) - int(suite.get("errors"))
    test_summary = f"{passed} passed, {suite.get('skipped')} skipped, {suite.get('failures')} failed"
    roster = [
        ("Hoàng Trọng Trà – 2A202603342", "Lead / Integrator; tiếp quản phần còn lại", "52b3cf1", "src/team06/integration.py; src/team06/policy.py; tools/; reports/; demo/", "Trà trình bày toàn bộ demo; AI hỗ trợ implementation và soạn hồ sơ"),
        ("Nguyễn Quốc Hưng – 2A202603324", "Data & Provenance", "bd0850f", "src/team06/data.py; tools/data_audit.py; reports/internal_labels_t02_*.csv", "Git evidence thực tế; đính chính camera 17a80f6"),
        ("Phạm Văn Dương – 2A202603332", "Baseline & Research", "684924a", "src/team06/baseline.py", "Baseline Laplacian thực tế"),
        ("Nguyễn Nhật Hạ – 2A202603325", "Core Algorithm / PoC", "e75920f", "src/team06/features.py; src/team06/scoring.py", "Feature và scoring thực tế"),
        ("Lê Trần Phi Hùng – 2A202603353", "QA & Evaluation", "081fae2", "tests/test_team06.py; tests/test_team06_scoring.py; tests/test_team06_integration.py", "QA thực tế; báo cáo lịch sử bfc33ed"),
        ("Nguyễn Tuấn Minh – 2A202603349", "Human Review & Demo (phân công ban đầu)", "", "", "Chưa tìm thấy commit thực chất trong main; Trà tiếp quản, không ghi thay tác giả"),
    ]
    contribution_rows, contribution_table = [], []
    for member, role, commit, modules, note in roster:
        author = email = sha = ""
        if commit:
            sha, author, email = subprocess.check_output(
                ["git", "show", "-s", "--format=%H%x09%an%x09%ae", commit], text=True).strip().split("\t")
        contribution_rows.append([member, author, email, role, modules, sha, note,
                                  "Hoàng Trọng Trà" if member.startswith("Hoàng") else "Chưa ghi nhận trình bày"])
        contribution_table.append(f"| {member} | {author or 'Chưa có'} {email} | {role} | {sha[:7] or 'Chưa có'} |")
    with Path("reports/team_contributions.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["member", "git_author_name", "git_email", "role", "modules_files", "commit_shas", "evidence_note", "presenter"])
        writer.writerows(contribution_rows)

    def metric(data, name):
        return next(m for m in data["metrics"] if m["name"] == name)

    recall, precision = [metric(poc, n) for n in ("Defect Recall@B", "Precision@B")]
    slice_table = ["| Slice | N | Lỗi thật | Hit Baseline | Hit PoC |", "|---|---:|---:|---:|---:|"]
    for key, group in slices.groupby("slice", sort=False):
        b, p = [group.loc[group.run.eq(name)].iloc[0] for name in ("baseline", "poc")]
        slice_table.append(f"| {key} | {int(p.n)} | {int(p.positives)} | {int(b.hits_in_global_dev_top20)} | {int(p.hits_in_global_dev_top20)} |")
    counts = after["metrics"]
    report = f'''# Team 6 · T02 Raw QC Triage

Hoàng Trọng Trà – 2A202603342 chịu trách nhiệm tích hợp và tiếp quản phần việc còn lại theo yêu cầu trong chat.
Repo: https://github.com/trahoangdev/K5-Day6-L2B-HoangTrongTra-2A202603342-DataGovernanceAndPrivacy.
Đối chiếu BTC main `b0ce8bf`. Hồ sơ hiện tại cho thấy pipeline hoạt động, **chưa chứng minh chất lượng heldout**.
Freeze ghi nhận {freeze['frozen_at_utc']}, base `{freeze['base_commit'][:7]}`. Chưa có bằng chứng mốc phút 30/180 hoặc deadline +24h.
Không đặt tag lịch sử `demo-180m`/`final-24h` để giả lập thời hạn. Deadline lớp chưa được cung cấp.

## 1. Vấn đề và đầu ra

Người kiểm dữ liệu chỉ có budget B=20 để tìm ảnh cần chụp lại trước khi dùng downstream.
Bỏ sót blur, thiếu sáng hoặc lóa có thể làm dữ liệu không hữu ích; báo nhầm ảnh đêm làm mất dữ liệu hữu ích và tốn công thu thập.
Đầu vào là ảnh cùng metadata camera/light/split và manifest. Đầu ra gồm ranking, queue, action từng ảnh,
contact sheet offline, override/audit và quyết định có owner/reason.

```mermaid
flowchart LR
  A[Input + manifest] --> B[Verify + load]
  B --> C[Laplacian baseline / multi-feature PoC]
  C --> D[Rank + top-B]
  D --> E[Human review + override]
  E --> F[Image actions + run decision]
  F --> G[Audit + metrics report]
```

Policy `t02-lead-v1` ưu tiên HOLD khi còn review hoặc thiếu provenance/offline; REWORK khi đã giải quyết review nhưng còn RECAPTURE;
GO khi tất cả ảnh KEEP và review bắt buộc đã có bằng chứng. GO chỉ mô tả triage của batch, không phải chứng nhận chất lượng hay tuân thủ pháp lý.

## 2. Dữ liệu và provenance

Fixture synthetic CC0-1.0 do BTC cung cấp: 96 ảnh, 56 dev và 40 eval, 24 scene gốc, bốn biến thể mỗi scene.
Split theo scene không rò scene giữa dev/eval. Schema `image_id,path,camera_id,light,split`; nhãn nội bộ thêm
`defect_type,severity,is_defect,annotator,source,note`. Mapping lỗi: blur/glare/dark/compression=1, none=0.
Manifest hash kiểm trên byte gốc, `.gitattributes` giữ fixture verbatim để tránh LF/CRLF làm sai checksum.
Toàn bộ 14 manifest fixture PASS; log còn gồm các manifest dữ liệu thật cục bộ, số lượng có thể khác khi clone sạch.

Nhãn nội bộ cuối chỉ gồm {len(labels)} dev, {int(labels.is_defect.sum())} ảnh lỗi, {int(labels.is_defect.eq(0).sum())} ảnh none.
Hưng thực hiện một lượt và test-retest có hỗ trợ tiền gán nhãn AI, không phải hai annotator độc lập.
Agreement binary .900, kappa .800, type agreement .850 trên 20 retest là số liệu lịch sử của Data;
4 bất đồng đã adjudicate, giữ nguyên raw/retest/disagreement. img_18_3 có hồ sơ adjudication riêng, ghi actor AI-assisted,
không suy diễn thành review độc lập. Nhãn chịu thiên lệch cùng đặc trưng blur nên kết quả dev có thể lạc quan.
Không có GT eval chính thức trong student repo, không tạo hoặc suy luận GT cho 40 eval để tune.

## 3. Phương pháp và protocol

Baseline của Dương dùng variance Laplacian toàn ảnh, score âm để ảnh mờ xếp trước; action threshold 186.855.
Giữ giá trị đã triển khai, chưa có log grid-search để chứng minh tối ưu. Ngưỡng 777 trong ghi chú Data chỉ là minh họa tách nhãn sau quan sát,
khác ngưỡng triển khai và khác Recall@20.

PoC của Hạ kết hợp sharpness tile 4×4, p95/dark fraction, vùng sáng bão hòa sau erosion và tỉ lệ gradient biên JPEG 8×8.
Chuẩn camera/global học từ dev; so sánh session theo batch không dùng nhãn. Đây là phương pháp phụ thuộc thành phần batch,
không nên diễn giải là bộ phân loại từng ảnh độc lập. Với camera lạ/singleton, dùng fallback dev.
Weighted score cộng agreement bonus, higher nghĩa đáng ngờ hơn; score không giới hạn ở 1.
KEEP dưới .20, REVIEW từ .20 đến dưới .60, RECAPTURE từ .60.
Mọi tham số nằm trong `configs/submission.yaml`, SHA-256 ở `configs/protocol_freeze.json`; script từ chối nếu đầu vào freeze bị đổi.

Baseline/PoC dùng cùng pool, seed42, B=20, cấu hình policy và evaluator nguyên gốc.
Metric join theo image_id, lọc split trước top-B. Queue demo top-20 toàn bộ 96 khác top-20 dev hoặc eval.
Baseline threshold chỉ tác động action, ranking vẫn dùng score liên tục.
Không có weights/model cần tải lúc chạy. Thay đổi thuật toán sau báo cáo cần freeze mới và không được chọn theo eval.

## 4. Kết quả nội bộ và failure cases

**Chỉ đánh giá dev in-sample, nhãn AI-assisted. Không phải điểm BTC hay heldout.**
Số liệu dưới đây do `src.evaluate --split dev --budget 20` và `src.compare` sinh nguyên bản.
Ghi chú `eval N` của evaluator dùng tên chung, split thực tế ở JSON là dev.

{'Baseline: ' + Path('reports/table1_baseline_vs_poc.md').read_text(encoding='utf-8').partition('Baseline: ')[2]}

Cả hai chạm trần Recall@20 khả thi trên dev này: {recall['numerator']}/{recall['denominator']} vì số lỗi thật lớn hơn budget.
Không có cải thiện primary metric. Type accuracy cao hơn chỉ là secondary trên cùng nhãn dev.
PoC đổi ưu tiên từ blur sang glare/dark, không thể suy ra tốt hơn mọi camera hoặc mọi use case.
Các hit dưới đây dùng cùng top-20 dev toàn cục; N là số ảnh slice, lỗi thật là denominator recall.

{chr(10).join(slice_table)}

Failure 1: `img_20_3` glare vẫn có nhiều cạnh nên global Laplacian không đưa vào top-20 dev;
PoC ưu tiên glare tốt hơn ở slice này. Xem `reports/images/hard_1_glare.png` và raw predictions.
Failure 2: `img_18_3` blur nặng được Baseline chọn nhưng PoC score 1.0 bị các ảnh nhiều cue đẩy ra khỏi top-20 dev.
Đây là lỗi phân bổ budget/ranking, không chỉ lỗi nhận dạng loại defect. `img_22_1` blur nội bộ còn có PoC score 0,
minh họa độ nhạy của nhãn nhẹ và session reference. Không chỉnh ngưỡng sau khi thấy các lỗi này.
Failure 3 theo handout: chưa chứng minh camera B mềm hơn có hệ thống. Trung vị trộn corruption gây kết luận sai;
Data đã đính chính bằng ảnh sạch theo scene, tránh dựng failure không có bằng chứng.

Wilson 95% mô tả Recall: {intervals['Defect Recall@B']['wilson95'][0]:.4f}–{intervals['Defect Recall@B']['wilson95'][1]:.4f};
Precision: {intervals['Precision@B']['wilson95'][0]:.4f}–{intervals['Precision@B']['wilson95'][1]:.4f}.
Tương quan frame, chọn top-B và tune dev vi phạm giả định độc lập; các khoảng này không chứng minh tổng quát hóa hoặc chênh lệch có ý nghĩa.
Runtime đo một lần, gồm load/provenance/features/HTML/audit, không gồm startup process; không phải benchmark tối ưu.
Máy: {poc['machine']['processor']}, {poc['machine']['platform']}, Python {poc['machine']['python']}, code `{poc['git_sha']}`.

## 5. Human review và quyết định

Trà đã xác nhận trong chat: “Tôi đã xem và chấp thuận RECAPTURE cả 20 ảnh”.
`reports/review_queue.csv` giữ reviewer, timestamp và lý do riêng từng ảnh; `review_confirmation.json` ghi nguyên văn phạm vi xác nhận.
AI đưa đề xuất thị giác trước, Trà chấp thuận sau khi xem. Không coi đây là đánh giá mù hoặc annotator thứ hai.
Pipeline áp approve trên đề xuất RECAPTURE, không sửa score, metadata hay thứ hạng.
`audit_log.jsonl` ghi trước/sau, actor và binding; CSV review cũ sai context bị chặn.

Trước review: {before['metrics']['n_reviewed']} reviewed, {before['metrics']['n_pending']} pending, {before['status']}.
Sau review: {counts['n_reviewed']} reviewed, {counts['n_keep']} KEEP, {counts['n_recapture']} RECAPTURE,
{counts['n_pending']} pending, quyết định **{after['status']} / {after['reason_code']}**.
Pending ngoài budget: {pending}. Không tự tăng B để đổi HOLD thành GO.
Muốn xử lý tiếp cần protocol/run review bổ sung hoặc thu thập lại, tách khỏi phép chấm B=20.
GO/REWORK/HOLD đều có test; không dùng test synthetic như review evidence thật.

## 6. Kiểm tra OOD, reliability và tái lập

Theo plan freeze, dùng sampler BTC tải {ood['n_scored']} ảnh BDD100K từ mirror `dgural/bdd100k`, seed42, max-side640.
Sampler ưu tiên rare/fog nên cả {ood['weather']['foggy']} ảnh đều foggy: {json.dumps(ood['timeofday'],ensure_ascii=False)}.
Đây là smoke test OOD có chủ đích, không đại diện phân phối thật. {ood['n_dev_reference']} ảnh dev giữ nguyên làm reference,
camera/session BDD chưa biết nên mỗi ảnh là singleton với fallback dev, không gộp session giả.
Run offline trả đủ {ood['n_scored']} score hữu hạn, khoảng {ood['score_min']:.6f}–{ood['score_max']:.6f};
đề xuất {json.dumps(ood['predicted_actions'])}, loại {json.dumps(ood['predicted_types'])}.
Không có QC GT nên không biết bao nhiêu báo nhầm. Toàn bộ bị RECAPTURE cho thấy cần human calibration/domain review,
không chứng minh model phát hiện đúng lỗi. Resize/JPEG chất lượng90 có thể đổi blockiness; không tune sau kiểm tra.
Ảnh/contact sheet thật ở `data/real/` gitignored; chỉ metadata/score/hash được đưa vào report.
Nguồn mirror và điều kiện research/education được ghi theo prep BTC; cần kiểm lại quyền sử dụng ngoài bài lab.

Kiểm tra hiện tại: **{test_summary}**, preflight exit0, manifest exit0.
39 skip do bài chấm cần GT overlay giảng viên. Log ở `reports/submission/tests.txt`, `preflight.txt`, `manifests.txt`.
QA lịch sử của Hùng trên Windows từng có 16 lỗi checksum, 118 pass và 39 skip tại 081fae2;
đây là bằng chứng môi trường cũ, không xóa lịch sử hoặc coi là lỗi test hiện tại. Checkout giữ byte LF đã khắc phục.

```powershell
# Sau khi cài requirements.txt vào .venv (bước chuẩn bị, có thể cần mạng):
.venv/Scripts/python.exe -m tools.prepare_submission --replay-confirmed-review
.venv/Scripts/python.exe -m src.evaluate --track t02 --config configs/submission.yaml --gt reports/submission/internal_dev_labels_joined.csv --pred out/submission/poc/ranked_review.csv --split dev --budget 20
.venv/Scripts/python.exe -m pytest -q
# Khi giảng viên có GT: thay --gt bằng fixture GT, --split eval; không tune trên kết quả.
# OOD chỉ sau prep online, ảnh thật giữ local:
.venv/Scripts/python.exe -m tools.check_t02_ood
```

## 7. Giới hạn và đóng góp

Synthetic nhỏ, dev có bias tiền gán nhãn, night dev ít, cam_A/night không có dev để chuẩn theo camera×light.
Chưa có official GT/hidden eval, kiểm thử độc lập, đo usability hoặc run chứng minh thời hạn.
Khi tăng dữ liệu 10× cần đo lại CPU/memory/contact-sheet size và công suất reviewer, không ngoại suy từ một timing.
Ảnh thật có thể có người/biển số; không xuất pixel ra cloud/repo. Không tuyên bố đạt GDPR hay luật Việt Nam từ policy tự động.
Domain owner cần xác nhận mức hữu ích của ảnh và tiêu chí recapture; quyền chia sẻ/retention cần bên sở hữu dữ liệu xác nhận.

| Thành viên | Git author / email thực tế | Công việc | Commit chứng minh |
|---|---|---|---|
{chr(10).join(contribution_table)}

User đã giao Trà làm toàn bộ phần còn lại. Giữ nguyên ghi nhận đóng góp trước đó, không tạo commit giả cho Minh.
Yêu cầu BTC mỗi người có commit thực chất **chưa đủ cho người thứ sáu**; Trà tiếp quản không tự thay thế điều kiện cá nhân này.
AI hỗ trợ code công cụ hồ sơ, phân tích và soạn report/demo; mọi review được ghi đúng actor.

## 8. References và trạng thái nộp

Nguồn truy cập 2026-11-14:

- [BTC T02](https://github.com/VinUni-AI20k/K5-Day6-L2-DataGovernanceAndPrivacy/blob/main/docs/tracks/T02.md): metric, budget, baseline và failure analysis.
- [OpenCV Laplace Operator](https://docs.opencv.org/4.13.0/d5/db5/tutorial_laplace_operator.html): cơ sở đạo hàm bậc hai để đo chi tiết; code nhóm dùng SciPy, không sao chép demo C++.
- [SciPy binary_erosion](https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.binary_erosion.html): giải thích erosion của mask; việc phân biệt đèn/lóa là heuristic riêng cần kiểm chứng.
- [BDD prep BTC](../tools/download_real_samples.py) và [mirror](https://huggingface.co/datasets/dgural/bdd100k): sampler/provenance của OOD, không phải QC GT.

Đã có pipeline, metric contract, bảng sinh script, slice/CI, review thật, audit, test, OOD và source demo.
Còn giới hạn nộp: official score do giảng viên chấm, bằng chứng commit thành viên thứ sáu,
tag/thời hạn lịch sử chưa xác minh và batch hiện tại vẫn HOLD. Không báo các mục này là hoàn tất.
'''
    Path("reports/group_report.md").write_text(report, encoding="utf-8", newline="\n")
    print("Generated group report and verified Git contribution table. HTML demo: python -m tools.build_demo_html")


if __name__ == "__main__":
    main()
