# T02 · Pipeline và decision policy của Lead

Owner: **Hoàng Trọng Trà – 2A202603342**. Phiên bản: **t02-lead-v1** (2026-11-14).
Quy tắc vận hành dưới đây không dùng GT, metric eval hay một ngưỡng score mới do Lead tự đặt.
Baseline/feature/scoring vẫn do Dương/Hạ triển khai; ngưỡng của scorer phải chọn trên dev.

## 1. Giao diện tích hợp

Entry point giữ nguyên: `python -m src.main ...` → `src.pipeline.run(ctx)`.
T02 dùng `src.team06.integration.run_t02`; baseline gọi cùng luồng qua
`src.pipeline.run_pipeline(ctx, scorer=score_baseline)`.

Năm bước:

1. **Load:** gọi loader của Hưng, kiểm provenance và giữ metadata/split gốc.
2. **Process:** nhận DataFrame từ scorer; bắt buộc đủ đúng tập `image_id`, ID duy nhất,
   score thực hữu hạn; không đổi metadata. Không yêu cầu score nằm trong [0,1].
3. **Rank:** score giảm dần, hòa điểm theo `image_id` tăng dần; lấy top-B trong `review_split`.
4. **Review:** render contact sheet offline bằng hạ tầng chung, đọc reviewer CSV và áp policy.
5. **Decide:** xuất quyết định từng ảnh và toàn run, kèm owner/reason/evidence và audit.

Scorer có thể trả tối thiểu `image_id,score` theo đề. Adapter ghép metadata từ loader;
thiếu `pred_action` được coi là REVIEW, không tự suy đoán KEEP từ score.
Contract đầy đủ khuyến nghị: `image_id,path,camera_id,light,split,score,reason,pred_defect_type,pred_action`.
Scorer không được cung cấp các cột review/owner/reason_code do policy quản lý.

`raw_predictions.csv` giữ đề xuất tự động. `ranked_review.csv` giữ **đúng score gốc** và hành động
sau review; không loại ảnh RECAPTURE khỏi tập prediction để thay denominator hoặc thứ hạng metric.

## 2. Policy từng ảnh

| Tình huống | Hành động cuối ban đầu | Review bắt buộc? |
|---|---|---|
| Nằm trong top-B | REVIEW, giữ đề xuất trong `auto_action` | Có |
| Scorer trả REVIEW/không có action, kể cả ngoài top-B | REVIEW | Có; ngoài queue vẫn chặn GO |
| Ngoài queue, scorer trả KEEP | KEEP, reason `AUTO_KEEP` | Không, theo policy tự động |
| Ngoài queue, scorer trả RECAPTURE | RECAPTURE, reason `AUTO_RECAPTURE` | Không; vẫn yêu cầu REWORK toàn run |

Với hành động tự động, owner là Lead trong config; không gán tên reviewer cho ảnh chưa được người kiểm.

| `reviewer_decision` | Ý nghĩa trong T02 | `override_value` |
|---|---|---|
| approve | Chấp thuận đề xuất KEEP/RECAPTURE của scorer | Để trống; REVIEW phải dùng edit |
| reject | Reviewer loại **ảnh** vì không đạt chất lượng → RECAPTURE | Để trống |
| edit | Reviewer quyết định lại hành động | Bắt buộc KEEP hoặc RECAPTURE |
| escalate | Chờ xử lý thêm → REVIEW / escalated | Để trống |
| skip | Chưa kiểm xong → REVIEW / skipped | Để trống |

Mọi dòng có quyết định phải có **reviewer và review_note**. `reject` không có nghĩa tự đảo ngược prediction;
muốn giữ ảnh bị báo nhầm, dùng `edit` + `KEEP` và nêu bằng chứng (ví dụ ảnh đêm vẫn hữu ích).
`edit` không sửa score, loại lỗi hoặc feature trong phiên bản này.

Reviewer chỉ xử lý ID trong queue hiện tại. ID lạ, ID trùng, field queue bị sửa hoặc override không hợp lệ
làm run lỗi rõ ràng; toàn file được validate trước khi ghi bất kỳ audit override nào.

## 3. Gate toàn run

Thứ tự **HOLD → REWORK → GO**:

| Điều kiện | Kết quả / reason code |
|---|---|
| Không có dữ liệu hợp lệ | HOLD hoặc input error; không GO |
| Không enforce provenance thành công | HOLD / PROVENANCE_UNVERIFIED |
| Run không offline | HOLD / OFFLINE_REQUIRED |
| Còn REVIEW, pending, skip hoặc escalation; thiếu chứng cứ review bắt buộc | HOLD / REVIEW_PENDING hoặc INCOMPLETE_POLICY_EVIDENCE |
| Review bắt buộc đã xử lý, còn ít nhất một RECAPTURE | REWORK / RECAPTURE_REQUIRED |
| Mọi review bắt buộc đã xử lý, mọi ảnh KEEP | GO / TRIAGE_COMPLETE |
| Module chưa implement, lỗi scorer/reviewer/input/guard trong run | HOLD / RUN_FAILED; giữ nguyên exit code lỗi của runner |

GO chỉ mô tả **triage của input set hiện tại**. Không đồng nghĩa đã đạt Defect Recall@B,
đã qua hidden eval, hết lỗi dữ liệu hoặc đạt yêu cầu pháp lý.
Exit 0 nghĩa là thực thi thành công; quyết định nghiệp vụ vẫn có thể là HOLD/REWORK.

Không tăng budget tùy tiện để biến HOLD thành GO. Uncertainty ngoài top-B là giới hạn cần báo cáo;
thay đổi budget/pool thuộc run/protocol mới, không trộn với điểm chính thức B=20.

## 4. Pool review và đánh giá công bằng

`params.budget: 20`, `params.review_split: all` giữ pool demo ban đầu là 96 ảnh.
Có thể đặt review_split dev hoặc eval trong config của run, luôn ghi rõ trong output.
Trong giai đoạn còn tune thuật toán, dùng pool dev; chỉ xem/review eval sau khi freeze scorer.

Evaluator chính thức luôn lọc 40 ảnh eval rồi lấy top-20 theo metric chuẩn.
Queue top-20 toàn input không phải top-20 eval. Review thay hành động, không thay score,
nên không được tuyên bố primary metric tăng chỉ vì reviewer đổi KEEP/RECAPTURE.
Baseline và PoC phải cùng seed, pool, budget và policy. Không đọc `gt/` để chọn ngưỡng.

## 5. Output và vòng review

| File trong output directory | Nội dung |
|---|---|
| raw_predictions.csv | Score và đề xuất tự động đã validate |
| review_queue.csv | Queue top-B và trường reviewer trống |
| contact_sheet.html | Ảnh, score, đề xuất và nút export CSV; dùng renderer offline có sẵn |
| review_context.json | Binding input manifest, config, seed, scored table và queue |
| policy_snapshot.json | Phiên bản policy, budget, pool và thứ tự gate |
| ranked_review.csv | Prediction đầy đủ để evaluate, có hành động cuối và chứng cứ review |
| image_decisions.csv | auto/final action, review status, reason, owner từng ảnh |
| decision.json / decision_log.csv | Quyết định hiện tại / lịch sử append-only |
| audit_log.jsonl | Ai quyết định gì, trước/sau, lý do và run fingerprint |
| run_info.json | Runner ghi status, seed, runtime, machine và stats |

Sau khi scorer của nhóm đã implement:

```powershell
.\.venv\Scripts\python.exe -m src.main --track t02 --output out/poc --run-name poc --offline --seed 42
```

Mở contact sheet, reviewer nhập tên, chọn quyết định, điền note; `edit` điền KEEP/RECAPTURE.
Copy CSV export vào `out/poc/review_queue_reviewed.csv`, rồi chạy **đúng lệnh cũ**.
Giữ `review_context.json` của lượt tạo queue; không dùng file reviewed từ run khác.

Nếu input/config/scoring thay đổi, binding không khớp → lỗi thay vì áp review cũ.
Lưu trữ file reviewed cũ sang nơi riêng, chạy lại để tạo queue/binding mới rồi review lại.
Lỗi giữa chừng không để lại ranking/GO cũ: output cuối được vô hiệu hóa, ghi HOLD/RUN_FAILED;
file reviewer và audit/decision history được giữ lại.

## 6. Trạng thái bàn giao và kiểm thử

Lead đã triển khai adapter, policy và bridge review. Minh tiếp tục sở hữu UI/demo, nghiên cứu usability
và bằng chứng review thực tế; không đổi semantics của policy nếu chưa version lại.
Dương/Hạ chỉ cần hoàn thiện scorer theo giao diện chung; không cần viết lại orchestration.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_team06_integration.py -o addopts="" -q
```

Test dùng input/score/reviewer **synthetic riêng trong thư mục tạm**, không phải lời giải baseline/PoC,
không tạo metric nộp bài và không đọc GT. Có kiểm CLI qua runner thật, GO/HOLD/REWORK, override,
stale review, score/metadata invalid, audit, provenance, network/GT guard và output lỗi.
Baseline của Dương và PoC của Hạ đã tích hợp; CLI thật chạy offline trên đủ 96 ảnh.
Test synthetic ở trên dùng để kiểm tra semantics của policy; không thay số liệu chất lượng thật.
Calibration của PoC yêu cầu dev, không fallback sang eval. Cấu hình/feature/score không hữu hạn
báo input error (exit 2), integration ghi HOLD/RUN_FAILED thay vì KEEP giả.
