# T02 Raw QC Triage

Team 6

Hoàng Trọng Trà · 2A202603342

Offline ranking, human review và quyết định batch

Notes: Mở đầu 20 giây. Nhóm chọn 20 ảnh cần kiểm trước khi dùng dữ liệu downstream. Evidence: reports/group_report.md. Fixture synthetic BTC CC0-1.0.

---

# Pipeline và protocol

96 ảnh synthetic: 56 dev, 40 eval

Baseline Laplacian và PoC blur / dark / glare / JPEG

Seed 42, B=20, tham số freeze trong submission.yaml

Load, score, rank, human review, decide

Notes: 40 giây. Chạy một lệnh prepare_submission --replay-confirmed-review. Dev calibration, không đọc GT. Tham chiếu session phụ thuộc batch. Freeze muộn, không tuyên bố mốc phút30. Sources: configs/protocol_freeze.json; BTC docs/tracks/T02.md; OpenCV Laplacian tutorial; SciPy binary_erosion docs.

---

# Kết quả trên dev nội bộ

Cả hai: Recall@20 20/34, Precision@20 20/20

PoC tăng ưu tiên glare/dark, giảm hit blur

Nhãn dev AI-assisted, đã dùng trong phát triển

Chưa có điểm eval chính thức từ BTC

Notes: 45 giây. Không tuyên bố tăng primary. Bảng editable lấy đúng JSON. img_18_3 blur bị đẩy khỏi top20 PoC. Wilson chỉ mô tả, không là CI tổng quát hóa. Sources: reports/metrics_baseline.json, metrics_poc.json, submission/slices.csv, uncertainty.json.

---

# Review của Trà và quyết định HOLD

Trà đã xem và chấp thuận RECAPTURE 20 ảnh

40 KEEP, 51 RECAPTURE, 5 ảnh chờ ngoài top-20

Audit giữ reviewer, lý do và before/after

Review không thay score hoặc budget

Notes: 45 giây. Mở reports/submission/contact_sheet.html, review_queue.csv, audit_log.jsonl và decision.json. Bằng chứng user confirmation được ghi riêng. Chưa xử lý5ảnh ngoàiqueue nên HOLD hợp policy. Không dựng GO để làm đẹp demo. Sources: reports/submission/review_confirmation.json; reports/submission/poc/decision.json; docs/T02_POLICY.md.

---

# Kiểm tra và giới hạn

140 passed, 39 skipped, 0 failed

10 ảnh BDD100K foggy chạy offline, không có QC GT

Mọi ảnh OOD bị đề xuất RECAPTURE, cần kiểm tra domain

Còn thiếu commit thực chất của thành viên thứ sáu

Bước tiếp theo: review phần chờ và chấm eval của BTC

Notes: 25 giây. Không đưa ảnh thật lên cloud. Không giả tag lịch sử hoặc commit tác giả khác. Trà tiếp quản các phần còn lại. Sources: reports/submission/tests.txt, ood_summary.json, team_contributions.csv. Sampler rare-first seed42, không đại diện phân phối thật. Tổng khoảng175giây.
