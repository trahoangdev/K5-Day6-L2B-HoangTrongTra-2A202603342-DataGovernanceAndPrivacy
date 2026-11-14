# Đối chiếu slide với guideline BTC

Đã đọc lại repo BTC ngày 2026-11-14, main `b0ce8bfd972315448aace86185c1a3e075754b93`.

Nguồn: [README, timeline và rubric](https://github.com/VinUni-AI20k/K5-Day6-L2-DataGovernanceAndPrivacy/blob/b0ce8bfd972315448aace86185c1a3e075754b93/README.md),
[T02](https://github.com/VinUni-AI20k/K5-Day6-L2-DataGovernanceAndPrivacy/blob/b0ce8bfd972315448aace86185c1a3e075754b93/docs/tracks/T02.md),
[quy ước reports](https://github.com/VinUni-AI20k/K5-Day6-L2-DataGovernanceAndPrivacy/blob/b0ce8bfd972315448aace86185c1a3e075754b93/reports/README.md).

| Yêu cầu liên quan | Slide / bằng chứng | Trạng thái |
|---|---|---|
| 3 đến 5 slide, showcase ngắn | index.html, 5 section, ghi chú tổng khoảng3 phút | Có |
| Nêu bài toán và nhóm | Slide1, đủ6 tên/mã/vai trò ban đầu | Có; không coi roster là chứng cứ Git |
| E2E một lệnh, đủ5 bước | Slide2/5; prepare_submission và clean_checkout.json | Có |
| Baseline Laplacian, PoC, cùng B/split/seed | Slide2/3; metrics JSON, config freeze | Có cho đánh giá nội bộ |
| Defect Recall@20 và Precision@20; không sửa metric | Slide3; bảng/chart sinh từ evaluator và CSV | Có, ghi rõ dev in sample |
| Official eval/heldout | Slide3/5 nêu chưa có GT giảng viên | Chưa có điểm chính thức |
| Contact sheet20, override/audit, decision có reason/owner | Slide4, review_queue.csv, confirmation, audit, decision.json | Có20 review thật; batch HOLD |
| Failure analysis: đêm hữu ích, glare, camera | Slide4/5 và ghi chú: ảnh synthetic, dev misses; đính chính suy luận camB | Có phân tích, không dựng lỗi camera chưa chứng minh |
| Reliability, offline, seed, tests, clean start | Slide5, 146 pass/39 skip,14 fixture manifests, clean checkout | Có bằng chứng |
| Kiểm10 OOD ở phần +24h | Slide5, ood_scores.csv/ood_summary.json | Có smoke test; chưa có QC GT và không chứng minh thời hạn |
| Team Git evidence từng người | Ghi chú slide1/5, team_contributions.csv | Chưa có commit thực chất của thành viên thứ6 |
| Tag demo180m/final24h đúng mốc | Slide5/ghi chú | Chưa xác minh, không tạo tag giả thời hạn |
| Provenance/privacy | Chỉ nhúng fixture synthetic; ảnh BDD local | Có; không tuyên bố tuân thủ pháp luật từ checklist |

Slide là bài trình bày chung của Team6. Tên Trà chỉ dùng cho vai trò lead hoặc reviewer thực tế.
Định dạng và nội dung đã đối chiếu; không tuyên bố toàn bộ điều kiện chấm điểm đã hoàn tất.
