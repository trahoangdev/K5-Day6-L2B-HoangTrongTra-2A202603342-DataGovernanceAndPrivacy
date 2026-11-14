# Demo T02 · Trà trình bày

Mở `team06_t02.pptx` (5 slide, có speaker notes), khoảng 3 phút.
`slides.md` và `slides_source.json` chứa nội dung sinh từ bằng chứng bằng `python -m tools.write_submission_report`.
File PowerPoint đã qua kiểm tra cấu trúc/layout và xem từng slide bằng renderer, chưa chạy trình chiếu PowerPoint native.

## Thao tác demo

1. Giới thiệu vấn đề và budget20, mở slide 1–2 (60 giây).
2. Chạy `.venv/Scripts/python.exe -m tools.prepare_submission --replay-confirmed-review`.
   Mở `reports/table1_baseline_vs_poc.md` và slide3 (45 giây).
   Nói rõ đây là dev nội bộ, primary không tăng, chưa có GT eval chính thức.
3. Mở `reports/submission/contact_sheet.html`, `reports/review_queue.csv`,
   `reports/submission/poc/decision.json` và audit log, chuyển slide4 (45 giây).
   Trà đã xem/chấp thuận20 RECAPTURE. 5 pending ngoài top20 giữ HOLD; không tăng budget.
4. Slide5 (25 giây): test, OOD không có QC GT, giới hạn đóng góp/thời hạn và bước tiếp theo.

Ảnh minh họa trên slide là fixture synthetic CC0-1.0 của BTC.
Không đưa ảnh/contact sheet BDD100K thật lên cloud hoặc repo.
Không dựng GO, score official, commit của thành viên khác hoặc tag đúng thời hạn khi chưa có bằng chứng.

## Rebuild PowerPoint

`build_slides.mjs` dùng bundled `@oai/artifact-tool`, không thêm dependency cho pipeline Python.
Truyền đường dẫn module artifact-tool, thư mục skill presentations và Python runtime làm ba đối số.
Finalizer không ghi đè file đã có: lưu bản cũ trước khi rebuild.
