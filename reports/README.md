# reports/

Team 6 đã sinh hồ sơ bằng `python -m tools.prepare_submission --replay-confirmed-review`.
Các `metrics_*.json` hiện là **internal dev in-sample**, không phải official eval.
`review_queue.csv` là 20 review thật được Trà xác nhận; `submission/` có before/after, binding, audit,
slices, CI mô tả và OOD metadata. Ảnh/contact sheet trong thư mục này chỉ là synthetic BTC.
Decision log chuẩn ở `reports/decision_log.csv`, giữ lịch sử cũ và chỉ append quyết định run mới.
Xem `group_report.md` để biết giới hạn và các điều kiện nộp chưa chứng minh được.

| File | Ai tạo | Cách tạo |
|---|---|---|
| `group_report.md` | nhóm + script | `python -m tools.write_submission_report` từ bằng chứng đã lưu; không coi đây là lượt chạy test mới |
| `metric_contract.md` | nhóm | protocol/freeze đã ghi nhận, có công bố giới hạn thời điểm |
| `metrics_baseline.json` | **script** | `python -m tools.prepare_submission --replay-confirmed-review` gọi evaluator BTC với nhãn dev nội bộ |
| `metrics_poc.json` | **script** | cùng lệnh prepare_submission; split dev, B=20, không phải official eval |
| `table1_baseline_vs_poc.md` | **script** | `python -m src.compare reports/metrics_baseline.json reports/metrics_poc.json --out reports/table1_baseline_vs_poc.md` |
| `review_queue.csv` | pipeline + reviewer | 20 quyết định Trà đã xác nhận, giữ reviewer/note và binding, replay không tạo review mới |
| `decision_log.csv` | pipeline + exporter | append từ `out/submission/poc/decision_log.csv`, không ghi đè lịch sử |
| `team_contributions.csv` | nhóm | khớp với `git shortlog -sne --all` |

Các file metrics/table **không được sửa tay** — giảng viên sẽ chạy lại lệnh để đối chiếu.

`submission/` chỉ giữ 15 file bằng chứng cần cho report, demo và replay. Bộ PoC gốc gồm
raw predictions, image decisions, decision, review context và audit được giữ nguyên khi chạy lại.
Baseline snapshots, queue trống, policy/run-info trùng lặp, checklist review đã xong và log kiểm tra chi tiết ở `out/`.
Exporter không sao chép các file này trở lại reports.

`submission/tests.txt` là kết quả pytest đã ghi nhận, dùng được khi clone sạch. Muốn cập nhật,
chạy pytest, lưu đầy đủ stdout/stderr vào file này rồi sinh lại report/demo; thiếu summary sẽ báo lỗi rõ ràng.
