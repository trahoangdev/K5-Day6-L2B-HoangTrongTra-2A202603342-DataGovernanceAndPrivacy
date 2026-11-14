# reports/

Team 6 đã sinh hồ sơ bằng `python -m tools.prepare_submission --replay-confirmed-review`.
Các `metrics_*.json` hiện là **internal dev in-sample**, không phải official eval.
`review_queue.csv` là 20 review thật được Trà xác nhận; `submission/` có before/after, binding, audit,
slices, CI mô tả và OOD metadata. Ảnh/contact sheet trong thư mục này chỉ là synthetic BTC.
Xem `group_report.md` để biết giới hạn và các điều kiện nộp chưa chứng minh được.

| File | Ai tạo | Cách tạo |
|---|---|---|
| `group_report.md` | nhóm | điền template |
| `metric_contract.md` | nhóm | điền ở phút 30 |
| `metrics_baseline.json` | **script** | `python -m src.evaluate --track tXX --pred out/baseline/<file> --run-name baseline --out reports/metrics_baseline.json` |
| `metrics_poc.json` | **script** | `python -m src.evaluate --track tXX --pred out/poc/<file> --run-name poc --out reports/metrics_poc.json` |
| `table1_baseline_vs_poc.md` | **script** | `python -m src.compare reports/metrics_baseline.json reports/metrics_poc.json --out reports/table1_baseline_vs_poc.md` |
| `review_queue.csv` | pipeline + reviewer | copy từ `out/poc/review_queue.csv` sau khi review (có cột reviewer/decision) |
| `decision_log.csv` | pipeline | copy từ `out/poc/decision_log.csv` |
| `team_contributions.csv` | nhóm | khớp với `git shortlog -sne --all` |

Các file metrics/table **không được sửa tay** — giảng viên sẽ chạy lại lệnh để đối chiếu.
