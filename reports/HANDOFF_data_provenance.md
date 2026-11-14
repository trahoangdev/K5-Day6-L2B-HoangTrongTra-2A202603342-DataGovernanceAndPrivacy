# Bàn giao từ Data & Provenance → cả nhóm (T02)

Nguyễn Quốc Hưng · nhánh `feat/team06-data`.
Phân công và vai trò xem `docs/TEAM06.md`; tài liệu này chỉ nói những gì **dữ liệu
bắt buộc** phải tính đến.

Đọc mục 1 trước khi viết `features.py` / `scoring.py`.

---

## 1. Hai ràng buộc với thuật toán

### 1.1 `cam_A/night` không có mẫu nào ở `dev`

| camera | light | dev | eval |
|---|---|---:|---:|
| cam_A | day | 24 | 20 |
| cam_A | dusk | 12 | **0** |
| cam_A | night | **0** | 8 |
| cam_B | day | 12 | **0** |
| cam_B | dusk | 4 | 4 |
| cam_B | night | 4 | 8 |

Quy tắc 1 của lab chỉ cho chỉnh ngưỡng trên `dev`. Nên **không thể** hiệu chỉnh
ngưỡng riêng cho `cam_A/night`, mà tầng đó chiếm 8/40 ảnh eval — 20%.

Hệ quả: đừng chuẩn hoá theo cặp `(camera_id, light)`. Chuẩn hoá theo riêng
`camera_id` thì an toàn, cả hai camera đều có mặt ở hai split. Hoặc chuẩn hoá
**trong từng cảnh gốc** (`img_NN` có 4 biến thể) — cách này không phụ thuộc split,
nhưng giả định mỗi cảnh có ít nhất một biến thể sạch.

Kiểm trong code: `src.team06.data.uncalibratable_strata(images)` trả về
`['cam_A/night']`. Nếu một hôm nó trả về khác, nghĩa là fixture đã đổi.

### 1.2 Ngưỡng toàn cục sẽ báo nhầm có hệ thống

Độ nét trung vị (Laplacian variance):

| camera | day | dusk | night |
|---|---:|---:|---:|
| cam_A | 944 | 777 | **1578** |
| cam_B | **236** | 174 | 350 |

- `cam_B` mềm hơn `cam_A` gấp 4 lần ở ảnh ngày. Đó là quang học camera, không
  phải lỗi ảnh. Một ngưỡng chung sẽ quét gần hết `cam_B` vào hàng đợi review.
- Ảnh đêm `cam_A` **nét hơn** ảnh ngày (1578 so với 944). "Tối = lỗi" là sai.

Hai điều này đúng là hai trong ba failure mode mà `docs/tracks/T02.md` mục 5
bắt phải phân tích.

---

## 2. Trạng thái dữ liệu

| Hạng mục | Kết quả |
|---|---|
| Manifest 14 track | **14 PASS, 0 FAIL** |
| Schema `images.csv` | đủ cột, không null, `image_id` không trùng |
| Rò rỉ split | không — 24 cảnh gốc, không cảnh nào ở cả hai split |
| Phân tầng | lệch, xem mục 1.1 |
| Nhãn nội bộ | **chưa có ai gán** |

Chạy lại: `python tools/data_audit.py --track t02 --out reports/data_audit_t02.md`

### Lỗi đã sửa: CRLF làm hỏng hash

`fixtures/t02_raw_qc/images.csv` bị hash trong `manifest.csv` và có 97 dòng. Máy
nào đặt `core.autocrlf=true` (mặc định Windows) sẽ checkout ra file dài thêm đúng
97 byte → sha256 lệch → `strict_provenance` dừng `src.main` với **exit 2**.

Không riêng T02: **cả 14 track** đều có file text nằm trong manifest, tổng cộng
hơn 160 file — `t06_release_gate` một mình đã 124 file `.json`/`.txt`.

`.gitattributes` của Trà (`* text=auto eol=lf`) xử lý được phần lớn. Nhánh này
thêm một dòng chặt hơn:

```
fixtures/** -text
```

`text=auto` để git **tự đoán** file nào là text, nên một đuôi file lạ vẫn có thể
bị sửa line ending. `-text` nói thẳng: đừng đụng vào bất cứ thứ gì dưới `fixtures/`.

**Nếu bạn clone trước khi có nhánh này và đang bị exit 2:**

```bash
git rm --cached -r . && git reset --hard
```

---

## 3. Nhãn nội bộ

Repo không có `fixtures/*/gt/`, nên muốn chốt ngưỡng phải tự gán nhãn.
`docs/TEAM06.md` giao việc này cho **Hưng và Phi Hùng**, nhưng thực tế chỉ
**một người (Hưng)** gán được.

Hệ quả phải nói rõ với Lead: **không có Cohen's κ giữa hai người**. Thay bằng
độ nhất quán test-retest của chính người gán — yếu hơn, và không phát hiện được
thiên lệch mà người gán giữ nhất quán. Nếu Phi Hùng gán thêm được một bộ độc lập
thì chạy lại script là có κ thật.

Quy trình đầy đủ ở `reports/internal_label_protocol.md`. Tóm tắt:

```bash
# lượt 1: toàn bộ 56 ảnh dev
python tools/make_label_sheet.py --track t02 --split dev --annotator A --by-scene
# nghỉ ít nhất 15 phút, rồi lượt 2: 20 ảnh ngẫu nhiên, thứ tự khác
python tools/make_label_sheet.py --track t02 --split dev --annotator A \
    --sample 20 --suffix retest --seed 7
```

Mở file HTML sinh ra, gán, bấm Export CSV, lưu thành
`reports/internal_labels_t02_A.csv` và `..._A_retest.csv`, rồi:

```bash
python tools/merge_internal_labels.py \
    --a reports/internal_labels_t02_A.csv \
    --b reports/internal_labels_t02_A_retest.csv
```

Script tự nhận ra cùng một người và in ở chế độ TEST-RETEST.
Ngưỡng nhận: ≥ 0,70.

Hai quy ước chốt trước, chính là chỗ hai người dễ lệch nhau nhất:

1. **Ảnh đêm nhìn rõ nội dung vẫn là `none`**, không phải `dark`.
2. **Ảnh `cam_B` so với `cam_B` khác**, không so với `cam_A`.

Không gán split `eval`. Gán rồi chỉnh ngưỡng theo đó là vi phạm quy tắc 1.
