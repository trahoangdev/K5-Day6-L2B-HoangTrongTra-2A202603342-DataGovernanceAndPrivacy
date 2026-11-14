# Metric contract (khai báo bắt buộc — chốt ở phút 30, trước khi chạy eval)

> Các metric chuẩn đã được cài trong `src/metrics/tracks.py`. File này là nơi nhóm **cam kết** cách dùng chúng.
> Không đổi testset, threshold hay trọng số sau khi đã thấy kết quả eval.

| Mục | Khai báo của nhóm |
|---|---|
| Track | G06 · T02 Raw QC Triage |
| Primary metric (tên đúng như evaluator in ra) | Defect Recall@B; báo kèm Precision@B, B=20 |
| Tăng tốt hay giảm tốt? | higher cho Recall/Precision; lower cho false alarm và runtime |
| Đơn vị đánh giá (image / region / pair / release / batch / case …) | image |
| Công thức + numerator / denominator | Recall = số ảnh lỗi thật trong top-B / tổng ảnh lỗi thật của split. Precision = số ảnh lỗi thật trong top-B / số ảnh được chọn. |
| Cách ghép prediction ↔ GT (IoU? id? tolerance?) | Join bằng image_id, không IoU. Lọc split trước top-B, score giảm dần; pipeline hòa điểm theo image_id tăng dần. Giữ evaluator BTC nguyên bản. |
| Candidate pool cố định | Fixture T02: 96 ảnh synthetic, 56 dev/40 eval theo scene gốc, không đổi split/ảnh. Hidden eval chính thức do BTC giữ, nhóm chưa có N/GT. |
| Review budget B / K | B=20 cho cả Baseline và PoC. Queue demo review_split=all trên 96 ảnh; metric top-B sau lọc split là pool riêng. |
| Seed | 42 |
| Threshold policy (chọn trên dev như thế nào) | Giữ Baseline 186.855 đã triển khai trên dev, chưa có log tìm ngưỡng tối ưu. PoC giữ nguyên bộ trọng số/ngưỡng đã phát triển trên dev, KEEP<0.20; REVIEW từ 0.20 đến dưới 0.60; RECAPTURE từ 0.60. Camera/global chỉ fit dev; session reference theo batch không dùng nhãn. Toàn bộ giá trị trong configs/lab.yaml, hash trong protocol_freeze.json. Không chỉnh sau eval. |
| Eval split (không dùng để tune) | eval cho fixture/hidden do giảng viên chấm. Báo cáo hiện tại dùng --split dev trên 56 nhãn nội bộ AI-assisted, là in-sample; không suy diễn thành kết quả heldout. |
| Chỉ số lỗi xấu (miss / false alarm / false reject) | Miss: ảnh lỗi ngoài top-B. False alarm: ảnh sạch trong top-B, theo light/camera. Theo dõi ảnh đêm hữu ích bị loại, glare cục bộ bị bỏ sót và sai lệch theo camera. |
| Slices sẽ báo cáo (≥2) | light và camera_id; bổ sung defect_type. Dùng cùng top-20 của toàn split, không cấp budget riêng cho từng slice. |
| Cách báo độ bất định khi N nhỏ (Wilson CI / bootstrap) | Wilson 95% mô tả Recall/Precision; frame cùng scene, chọn top-B và tune dev vi phạm giả định độc lập. Không dùng CI để tuyên bố tổng quát hóa hoặc ý nghĩa thống kê của chênh lệch. |
| Ngày giờ chốt + người chốt | 14/11/2026 21:24:33 UTC+7 (2026-11-14T14:24:33+00:00); Hoàng Trọng Trà – 2A202603342. Ghi nhận muộn trước lần sinh hồ sơ, sau phát triển trên dev; không chứng minh đã chốt phút 30/180. Protocol team06-submission-v1. |

Nếu baseline = 0 thì ghi rõ "baseline = 0" thay vì phần trăm cải thiện.
