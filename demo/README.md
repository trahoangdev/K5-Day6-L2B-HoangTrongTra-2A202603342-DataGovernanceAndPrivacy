# Slide chung Team 6 · T02

**Mở `index.html` trực tiếp bằng Chrome/Edge/Firefox.** File HTML tự chứa font, ảnh synthetic, CSS và JavaScript, không cần internet hoặc cài dependency để trình chiếu.
Có5 slide, thời lượng khoảng3 phút. Trang mở đầu ghi đủ6 thành viên và phân công ban đầu. Tên reviewer thật chỉ xuất hiện ở phần bằng chứng review.

## Điều khiển

- Mũi tên, PageUp/PageDown, Space hoặc nút Trước/Tiếp: chuyển slide.
- Home/End: đầu/cuối; nút số hoặc URL `#slide-3`: đến slide cụ thể.
- F: toàn màn hình; N: ghi chú diễn giả; O: tổng quan5 slide.
- P hoặc In/PDF: in đủ5 trang ngang, không in phần điều khiển/ghi chú.
- Điện thoại dọc: nội dung xếp lại để đọc; vuốt ngang để đổi slide.

Liên kết báo cáo/contact sheet cần giữ cấu trúc repo. Bản trình chiếu chính vẫn tự chứa khi chỉ copy một file HTML.
Ảnh đều từ fixture synthetic CC0 của BTC, không nhúng ảnh BDD100K thật.
Font Manrope theo SIL Open Font License, license nằm trong HTML và `Manrope-OFL.txt`.

## Nội dung theo guideline BTC

1. Bài toán T02, budget20 và6 thành viên Team6.
2. Pipeline5 bước, Baseline/PoC, dev/eval, seed và freeze.
3. Metric sinh bằng script, so sánh cùng budget/pool; nêu rõ kết quả dev nội bộ.
4. Human review, audit, HOLD và failure cases có ảnh.
5. Reliability, checkout sạch,10 OOD, lệnh demo và giới hạn còn lại.

Xem `GUIDELINE_CHECK.md` để đối chiếu yêu cầu và bằng chứng. Không tự gán điểm rubric.

## Sinh lại từ bằng chứng

```powershell
python -m tools.build_demo_html
```

Lệnh dùng JSON/CSV đã commit trong reports; không cần mạng, không sửa số liệu bằng tay.
Font được lấy lại từ HTML đã có. Source layout ở `slides.template.html`.
`python -m tools.write_submission_report` chỉ sinh report/contribution; không ghi đè slide HTML.

## Kịch bản demo khoảng3 phút

- Slide1:25 giây, bài toán và nhóm.
- Slide2:40 giây,5 bước, baseline/PoC và protocol.
- Slide3:40 giây, số liệu dev; primary không tăng, chưa có score official.
- Slide4:45 giây, mở contact sheet/review/audit và decision;5 ảnh ngoài top20 giữ HOLD.
- Slide5:30 giây, reliability/OOD và giới hạn.

Chuẩn bị terminal trước khi trình bày và chạy:

```powershell
python -m tools.prepare_submission --replay-confirmed-review
```

Đây là replay20 quyết định Trà đã xác nhận, không phải20 lượt review mới.
Bản PowerPoint cũ đã được thay bằng HTML dùng chung cho Team6.
