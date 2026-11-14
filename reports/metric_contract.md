# Metric contract · G06 / T02

Owner: Hoàng Trọng Trà – 2A202603342. Protocol `team06-submission-v1`.
Freeze UTC: **2026-11-14T14:24:33+00:00**. Xem `configs/protocol_freeze.json` để kiểm SHA-256 cấu hình, thuật toán, fixture manifest và nhãn nội bộ.

Đây là freeze được ghi nhận muộn của tham số đang tồn tại, trước lần sinh hồ sơ nộp này.
Không chứng minh đã chốt ở phút 30/180; nhóm đã quan sát dev trong phát triển.
Không có nhãn eval chính thức trong student repo; không suy diễn điểm BTC từ dev.

| Mục | Cam kết |
|---|---|
| Track / đơn vị | T02 Raw QC Triage / image |
| Primary | Defect Recall@B = số ảnh lỗi thuộc top-B / tổng ảnh lỗi trong split đánh giá; higher |
| Secondary | Precision@B = số ảnh lỗi thuộc top-B / số ảnh chọn; higher |
| Join / ranking | image_id; score giảm dần, pipeline hòa điểm theo image_id tăng dần; evaluator BTC giữ nguyên |
| Pool | 96 ảnh synthetic; 56 dev, 40 eval; tách theo scene gốc; không đổi fixture |
| Budget / seed | B=20 / 42; giống nhau cho Baseline và PoC |
| Queue demo | top-20 trên all 96; không đồng nhất với top-20 sau lọc split của evaluator |
| Baseline | score=-Laplacian variance toàn ảnh; ngưỡng hành động 186.855 kế thừa implementation của Dương trên dev; không có log tìm ngưỡng để chứng minh tối ưu; không chỉnh lại |
| PoC | toàn bộ tham số được ghi tường minh trong configs/lab.yaml; giữ nguyên DEFAULTS của Hạ; chuẩn camera/global chỉ fit dev; tham chiếu session theo batch không dùng nhãn |
| Action thresholds | keep_max=0.20, review_max=0.60; score không buộc trong [0,1] |
| Policy | t02-lead-v1, reports/group_report.md; review chỉ sửa hành động, không sửa score |
| Internal evaluation | 56 nhãn dev cuối, AI-assisted, SHA-256 cố định; chạy evaluator BTC với --split dev --budget 20; chỉ số in-sample, không phải heldout |
| Official evaluation | giữ --split eval, GT của giảng viên; chưa chạy được vì chưa có GT; không tạo nhãn giả cho 40 eval |
| Slices | light, camera_id, defect_type; tính số hit theo cùng top-20 dev toàn cục, không cấp B=20 riêng cho từng slice |
| Uncertainty | Wilson 95% cho Recall/Precision, chỉ mô tả tỷ lệ quan sát; tương quan trong scene, lựa chọn top-B và tune dev làm mất giả định Bernoulli độc lập; không dùng CI để tuyên bố tổng quát hóa hay ý nghĩa thống kê của chênh lệch |
| OOD | 10 BDD100K do sampler có sẵn chọn seed42, ưu tiên rare/fog, max-side640; không có QC GT; chỉ kiểm khả năng chạy và phân phối score, không báo accuracy; không tune sau xem |

Nếu baseline bằng 0, bảng ghi `baseline=0`, không chia phần trăm cho 0.
Không sửa metric/evaluator BTC. Thay đổi tham số/nhãn sau freeze cần protocol phiên bản mới và công bố lý do.

## Reproduce

```powershell
.venv/Scripts/python.exe -m tools.prepare_submission
```

Script xác minh freeze, manifest, chạy Baseline/PoC offline, join nhãn dev, gọi evaluator và sinh bảng, slices, CI và bằng chứng pipeline trong out/.
Bằng chứng human review phải do reviewer thật cung cấp; script không tự duyệt.
