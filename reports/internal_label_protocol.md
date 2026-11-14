# Protocol nhãn nội bộ — T02 Raw QC Triage

Repo học viên **không có** `fixtures/t02_raw_qc/gt/`. Không có nhãn thì nhóm không
chốt được ngưỡng, không đo được baseline, và không biết PoC tốt lên hay xấu đi.
Tài liệu này mô tả bộ nhãn nhóm tự gán để dùng thay thế, cùng giới hạn của nó.

Nhãn nội bộ **không phải** ground truth của giảng viên. Mọi con số đo trên nó
phải ghi rõ là "đo trên nhãn nội bộ, N=…", không được trình bày như điểm chính thức.

## 1. Phạm vi

| Hạng mục | Quyết định |
|---|---|
| Split được gán nhãn | `dev` (56 ảnh) — **toàn bộ**, không lấy mẫu |
| Split **không** gán nhãn | `eval` (40 ảnh) |
| Số người gán | **1** (Quốc Hưng) — xem mục 3b |
| Công cụ | `reports/internal_label_sheet_t02_A_byscene.html`, mở offline bằng trình duyệt |

Gán hết 56 ảnh `dev` thay vì lấy mẫu vì số lượng đủ nhỏ (khoảng 10 phút một người),
và như vậy không phải chịu thêm sai số lấy mẫu khi ước lượng tỷ lệ lỗi.

**`eval` để nguyên.** Quy tắc 1 của lab cấm tune trên split eval. Nếu nhóm tự gán nhãn
eval rồi chỉnh ngưỡng theo đó thì vi phạm, dù nhãn là nhãn của nhóm. Chỉ khi đã chốt
và đóng băng tham số thì mới được gán một lần duy nhất để báo cáo, và phải ghi rõ
"gán sau khi freeze" kèm thời điểm.

## 2. Bảng phân loại

Dùng đúng từ vựng của schema giảng viên (`gt/labels.csv`) để số liệu so sánh được:

| `defect_type` | Nghĩa | `is_defect` |
|---|---|---:|
| `none` | Ảnh dùng được, không cần chụp lại | 0 |
| `blur` | Nhoè toàn ảnh hoặc nhoè vùng chính, mất chi tiết | 1 |
| `glare` | Cháy sáng, kể cả **cháy cục bộ** ở vùng quan trọng dù tổng thể ảnh vẫn ổn | 1 |
| `dark` | Thiếu sáng tới mức không đọc được nội dung | 1 |
| `compression` | Vỡ khối JPEG, nhiễu bậc thang thấy rõ | 1 |

`severity`: `0` nhẹ (vẫn dùng được, ghi nhận), `1` vừa (nên chụp lại), `2` nặng (bỏ).

### Hai quy ước dễ gây lệch nhau, chốt trước

**Ảnh đêm không mặc nhiên là `dark`.** Trong fixture này ảnh đêm của `cam_A` có độ nét
trung vị 1578, cao hơn ảnh ngày (944). Ảnh tối nhưng vẫn nhìn rõ nội dung thì gán `none`.
Chỉ gán `dark` khi nội dung thực sự không đọc được.

**`cam_B` mềm hơn `cam_A` theo hệ thống**, độ nét trung vị 236 so với 944 ở ảnh ban ngày.
Đó là đặc tính quang học, không phải lỗi. Khi gán nhãn `cam_B` phải so với ảnh `cam_B`
khác, không so với `cam_A`.

Hai quy ước này ứng với failure mode số 1 và số 3 mà handout bắt phải phân tích.

## 3. Quy trình

`docs/TEAM06.md` giao việc gán nhãn cho **Hưng và Phi Hùng**. Trên thực tế chỉ có
một người làm được, nên bộ nhãn này là **một người gán**. Ghi lại ở đây để người
chấm và Lead thấy đúng tình trạng, không suy ra từ phân công rằng đã có hai người.

Quy trình thực hiện ở mục 3b. Nếu sau đó Phi Hùng gán được một bộ độc lập, chạy
`tools/merge_internal_labels.py` với hai file của hai người — script tự nhận ra
và chuyển sang chế độ đo Cohen's κ, lúc đó mục 3b trở thành dự phòng.

## 3b. Quy trình thực tế: một người gán

Chỉ một người gán thì **không tính được Cohen's κ giữa hai người**. Không bịa
con số đó ra.

Thay vào đó đo **độ nhất quán test-retest** của chính người gán:

1. Gán hết 56 ảnh `dev`, xuất CSV thành `reports/internal_labels_t02_A.csv`.
2. Đóng phiếu lại, **nghỉ ít nhất 15 phút** làm việc khác.
3. Sinh phiếu lượt hai, 20 ảnh lấy ngẫu nhiên trong 56 ảnh đó, thứ tự xáo khác:

   ```bash
   python tools/make_label_sheet.py --track t02 --split dev --annotator A \
       --sample 20 --suffix retest --seed 7
   ```

4. Gán lại 20 ảnh ấy **không nhìn kết quả lượt một**, xuất thành
   `reports/internal_labels_t02_A_retest.csv`.
5. So hai lượt:

   ```bash
   python tools/merge_internal_labels.py \
       --a reports/internal_labels_t02_A.csv \
       --b reports/internal_labels_t02_A_retest.csv
   ```

   Script tự nhận ra cùng một người và in ở chế độ TEST-RETEST.

Con số này yếu hơn κ giữa hai người và phải hiểu đúng: nó bắt được **tiêu chí
không ổn định**, nhưng **không** bắt được thiên lệch mà người gán giữ nhất quán
từ đầu tới cuối. Một người tin sai rằng mọi ảnh đêm đều là `dark` sẽ đạt
test-retest gần 1,0 trong khi bộ nhãn sai hệ thống.

Báo cáo ghi nguyên văn: *"một người gán, N=56, không đo được κ giữa hai người;
độ nhất quán test-retest trên 20 ảnh = …"*.

## 3c. Có dùng tiền-gán-nhãn bằng máy

Trước khi gán, người gán đã xem một **bảng gợi ý do máy sinh** (Claude Code), đề
xuất nhãn cho cả 56 ảnh dựa trên quan sát ảnh ở kích thước thật cộng với số đo
`laplacian_variance`, `saturated_fraction`, `dark_fraction`. Người gán duyệt lại
từng ảnh và tự quyết nhãn cuối.

Kết quả đối chiếu: **trùng 55/56 (98,2%)**, lệch duy nhất ở `img_22_1`, chỗ người
gán chọn `blur` còn máy đề xuất `none`.

**Con số 98,2% này không phải bằng chứng nhãn đúng.** Hai bộ không độc lập — người
gán nhìn gợi ý trước khi quyết. Nó chỉ cho biết người gán phần lớn đồng ý với gợi
ý, điều đó là hiển nhiên. Ghi lại ở đây để người chấm biết đúng cách bộ nhãn này
ra đời, không để ai trích dẫn nhầm thành độ chính xác.

### Thiên lệch đo được: nhãn trùng với feature của baseline

Sau khi gán xong, phân bố độ nét theo nhãn:

| Nhãn | n | `laplacian_variance` | trung vị |
|---|---:|---|---:|
| `none` | 22 | 782 – 1907 | 1103 |
| `blur` | 15 | 2 – 773 | 6 |

Hai nhóm **tách hoàn toàn**: `none` thấp nhất 782, `blur` cao nhất 773, khe hở 9
đơn vị. Nghĩa là một **ngưỡng Laplacian toàn cục** đặt quanh 777 tái tạo được
đúng phần `blur`/`none` của bộ nhãn này trên `dev`.

Baseline mà `docs/tracks/T02.md` quy định **chính là** một ngưỡng Laplacian toàn
cục. Nên đo trên bộ nhãn này, baseline sẽ đạt gần tối đa ở phần blur, và PoC rất
khó chứng minh là hơn — **không phải vì PoC dở, mà vì bộ nhãn được gán bằng đúng
tiêu chí mà baseline dùng**.

Hệ quả cho nhóm khi đọc kết quả:

- Không kết luận "PoC không hơn baseline" từ riêng bộ nhãn này.
- Phần có giá trị phân biệt nằm ở `dark`, `glare`, `compression` — những lỗi mà
  ngưỡng độ nét không giải quyết được. Nên báo metric tách theo `defect_type`,
  không chỉ một con số gộp.
- Nhãn của giảng viên (`gt/`) không có thiên lệch này, nên thứ hạng baseline/PoC
  khi chấm chính thức có thể khác hẳn.

## 3d. Kết quả thực tế

| Chỉ số | Giá trị | Ngưỡng | Đạt |
|---|---:|---:|:--:|
| N lượt 1 (toàn bộ `dev`) | 56 | — | — |
| N lượt 2 (mẫu gán lại) | 20 | — | — |
| Nhất quán `is_defect` | 0,900 | — | — |
| **Cohen's κ test-retest trên `is_defect`** | **0,800** | 0,70 | ✓ |
| Nhất quán `defect_type` | 0,850 | 0,70 | ✓ |
| Ảnh phải đối soát | 3 / 20 | — | — |

Phân bố nhãn cuối: `none` 22 · `blur` 15 · `compression` 9 · `dark` 6 · `glare` 4.
Tỷ lệ lỗi trên `dev`: 34/56 = 60,7%.

File cuối: `reports/internal_labels_t02_final.csv`, có cột `source` ghi mỗi ảnh
đến từ đâu (`pass1_only` 36 · `pass1+retest_agreed` 17 · `adjudicated` 3).

### Lượt 2 phải làm lại — và vì sao chi tiết này đáng ghi

Lần gán lượt 2 **đầu tiên** cho κ = **0,500**, trượt ngưỡng. Ma trận chéo cho thấy
5 ảnh bị chuyển từ `none` sang `blur`, và cả 5 đều nằm trong nhóm **nét nhất tập
dữ liệu**: `img_12_1` (877), `img_11_1` (1086), `img_00_1` (1366), `img_20_0`
(1439), `img_14_1` (1547). Dải `blur` của lượt đó trải từ 2 đến 1439 — tức gần
hết thang độ nét, không còn ranh giới nào.

Đó không phải vạch bị xê dịch mà là lượt gán không áp một tiêu chí nhất quán.
Gán lại cẩn thận thì κ lên 0,800.

Ghi lại vì nó chứng minh bước test-retest **có tác dụng thật**: nếu bỏ qua, nhóm
đã chốt ngưỡng thuật toán trên một bộ nhãn mà chính người gán không tái lập được.

### Ba ảnh đối soát

| Ảnh | Lượt 1 | Lượt 2 | Chốt | Lý do |
|---|---|---|---|---|
| `img_08_2` | compression | blur | **compression** | Nét 479 so với 1037/1050 của hai ảnh sạch cùng cảnh — cả hai lượt đều coi là lỗi, chỉ khác loại. Ở cỡ thật thấy rõ vỡ khối JPEG. Không ảnh hưởng metric chính vì `is_defect` = 1 ở cả hai lượt. |
| `img_11_1` | none | blur | **none** | Nét 1086, gần bằng ảnh sạch nhất cùng cảnh (1112). |
| `img_12_1` | none | blur | **none** | Nét 877, là ảnh **nét nhất** cảnh đó (166 · 877 · 183 · 43). Gọi nó là `blur` mâu thuẫn với quy ước "so trong cùng cảnh". |

## 4. Ngưỡng chấp nhận

Vì chỉ một người gán, ngưỡng áp lên chỉ số test-retest:

| Chỉ số | Ngưỡng | Nếu không đạt |
|---|---|---|
| Nhất quán test-retest trên `is_defect` (20 ảnh) | ≥ 0,70 | Xem lại quy ước ở mục 2, gán lại từ đầu |
| Nhất quán test-retest trên `defect_type` | ≥ 0,70 | Gộp các loại hay nhầm nhau, ghi vào report |
| Số ảnh chưa gán | 0 | Gán nốt trước khi dùng |

Dưới 0,70 nghĩa là tiêu chí "thế nào là lỗi" của chính người gán còn chưa ổn định.
Chỉnh ngưỡng thuật toán theo một bộ nhãn như vậy là chỉnh theo nhiễu.

Nếu sau này có bộ nhãn thứ hai của người khác, ngưỡng κ ≥ 0,70 giữa hai người
thay thế bảng trên, vì nó mạnh hơn.

## 5. Giới hạn phải nêu trong báo cáo

- **Một người gán.** Không có κ giữa hai người, nên không biết liệu người khác
  nhìn cùng bộ ảnh có ra kết quả tương tự không. Test-retest bắt được tiêu chí
  không ổn định, nhưng **không** bắt được thiên lệch mà người gán giữ nhất quán
  từ đầu tới cuối — ví dụ tin sai rằng mọi ảnh đêm đều là `dark`.
- **Nhãn trùng tiêu chí với baseline** ở phần blur — xem mục 3c. Đây là giới hạn
  nặng nhất của bộ nhãn này.
- N=56, chỉ trên `dev`. Khoảng tin cậy của mọi tỷ lệ rất rộng; không kết luận mạnh từ chênh lệch vài ảnh.
- Người gán nhãn cũng là người viết thuật toán → có thiên lệch xác nhận. Giảm bớt bằng cách
  gán nhãn **trước** khi nhìn điểm số của pipeline, và ghi lại thời điểm.
- Bảng phân loại là của nhóm suy ra từ handout, chưa chắc khớp cách giảng viên gán.
  Sai lệch hệ thống ở đây sẽ không lộ ra cho tới khi chấm bằng `gt/` thật.
- Nhãn nội bộ dùng để **chốt ngưỡng và bắt lỗi logic**, không dùng để tuyên bố thành tích.
