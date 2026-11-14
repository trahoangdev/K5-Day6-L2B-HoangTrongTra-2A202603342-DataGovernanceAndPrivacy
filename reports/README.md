# Reports của Team 6 · T02

Bộ chính theo mẫu BTC: group_report.md, metric_contract.md, metrics_baseline.json, metrics_poc.json,
table1_baseline_vs_poc.md, review_queue.csv, decision_log.csv và team_contributions.csv.

Chỉ giữ thêm bằng chứng cần kiểm chứng: audit_log.jsonl (review thật), internal_labels_t02_final.csv (gold dev nội bộ)
và adjudication_img_18_3.json (nguồn gốc quyết định nhãn). Binding input/score/reviewer ở configs/protocol_freeze.json.
Không đưa snapshot, handoff, nhãn trung gian, log kiểm tra hoặc file sinh tạm vào reports.

```powershell
python -m tools.prepare_submission --replay-confirmed-review
```

Lệnh dùng runner/evaluator BTC nguyên gốc, xuất metrics và bảng so sánh ở reports; prediction, contact sheet,
GT dev đã join, slices và CI ở out/submission. Decision log chỉ append, audit review gốc không bị ghi đè.
Report và slide là bản nộp cuối; các con số lấy từ output script, không sửa metric để đẹp số.
Kết quả hiện tại là dev nội bộ có AI hỗ trợ gán nhãn, không phải official eval/hidden eval của giảng viên.
