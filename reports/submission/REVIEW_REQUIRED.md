# Trà cần review 20 ảnh

**Đã hoàn tất:** Trà đã xem và xác nhận RECAPTURE cả20 trong chat.
Kết quả ở `../review_queue.csv`, phạm vi xác nhận ở `review_confirmation.json`, before/after và audit ở `poc/`.
Các hướng dẫn dưới đây được giữ để tái lập quy trình hoặc thực hiện review mới; không còn yêu cầu xác nhận lại lượt20 này.

Mở `contact_sheet.html` để xem đủ 20 ảnh; đề xuất của AI ở `review_proposals.csv`.
Các đề xuất đều là RECAPTURE, với lý do riêng từng ảnh; **chưa phải quyết định của Trà**.
Đặc biệt kiểm tra img_07_2, img_20_2 (ảnh tối nhưng còn hữu ích?) và img_18_2 (lóa đèn cục bộ).

Có thể xác nhận cụ thể trong chat sau khi xem, hoặc dùng contact sheet điền reviewer, quyết định, note rồi export CSV.
Đổi đề xuất bằng edit + KEEP/RECAPTURE. File xuất đặt tại `out/submission/poc/review_queue_reviewed.csv` rồi chạy lại một lệnh prepare_submission.

Chưa có xác nhận: quyết định HOLD được giữ nguyên. Sau 20 review vẫn có thể HOLD vì 5 ảnh REVIEW ngoài top-20.
Không tăng budget hoặc tự gán tên reviewer để che giới hạn này. Cần run/protocol bổ sung nếu muốn review ngoài budget.
