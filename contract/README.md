# `contract/` — một nguồn, nhiều bản cài

Thư mục này là **nguồn sự thật của SDK**. Mọi bản cài (Python, JavaScript, và bất kỳ ngôn ngữ nào
thêm sau) đều sinh ra từ đây hoặc bị kiểm bằng đây. Không bản cài nào được tự khai một cửa mà chỗ
này không có.

| Tệp | Là gì | Ai đọc |
|---|---|---|
| `methods.json` | Bảng cửa của SDK: tên hàm, động từ, đường, tên trường, tệp gửi dưới trường nào, có được gửi lại khi hỏng không | `tools/generate.py`, cả hai bộ kiểm hợp-lệ |
| `conformance.json` | Bộ ca kiểm dùng chung: gọi hàm này với tham số này thì đúng cái gì phải đi lên dây | `python/tests/test_conformance.py`, `javascript/test/conformance.test.mjs` |
| `vectors.json` | Bộ số kiểm chứng: mã thực thể, JSON chuẩn tắc, băm bản ghi | `test_verify.py`, `verify.test.mjs`, và mọi bản cài mới |
| `METHODS.md` | Bảng tra cho người đọc — **sinh tự động**, đừng sửa tay | người |

## Sửa gì thì làm gì

**Thêm hoặc đổi một cửa** → sửa `methods.json`, chạy `python3 tools/generate.py`, thêm ca vào
`conformance.json`, chạy hai bộ kiểm. Bỏ bước nào cũng có cổng bắt: quên sinh lại thì
`tools/generate.py --check` đỏ; quên thêm ca thì phép kiểm phủ-cửa đỏ ở cả hai ngôn ngữ.

**Sửa cách mã hoá một giá trị** (JSON gọn, khung bao, tâm vườn) → sửa `python/orilife/_wire.py` VÀ
`javascript/src/wire.js`, rồi thêm một ca vào `conformance.json` chạm được cả hai. Hai tệp `wire`
là chỗ duy nhất còn phải viết tay hai lần; `conformance.json` là thứ giữ chúng bằng nhau.

**Đổi thuật toán băm** → `vectors.json` phải sinh lại từ chính mã đang chạy trên máy chủ, không
gõ tay. Bản ghi đã neo lên chuỗi khối không được băm lại: xem `VERIFY.md`.

## Hai cổng, hai câu hỏi khác nhau — đừng gộp

| Cổng | Hỏi gì | Cần mạng | Hỏng thì |
|---|---|---|---|
| `tools/generate.py --check` | mã sinh có khớp hợp đồng không | không | đỏ |
| `tools/check_server_drift.py` | hợp đồng có khớp máy chủ đang chạy không | có | ba trạng thái: KHỚP / LỆCH / **KHÔNG ĐO ĐƯỢC** |

Cổng thứ hai trả về ba trạng thái chứ không phải hai, và trạng thái "không đo được" kêu to hơn
trạng thái "lệch". Một phép đo trả "ổn" đúng lúc nó không đo được gì thì màu xanh của nó vô nghĩa:
nó không nói *ổn*, nó nói *tôi không biết* bằng giọng của *ổn*.

## Vì sao thư mục này tồn tại

Trước ngày 2026-09-08, `python/orilife/client.py` và `javascript/src/client.js` là hai bản chép
tay của cùng một hợp đồng. Ba chỗ lệch đo được lúc gộp lại, không chỗ nào có phép kiểm nào bắt:

1. `create_farm(lat=10.762622, lon=106.660172)` gửi `center_json=[10.762622, 106.660172]` ở Python
   và `[10.762622,106.660172]` ở JavaScript — khác một dấu cách là khác byte.
2. `update_farm(boundary_json=[[10.7, 106.6]])` mã hoá JSON ở Python; ở JavaScript
   `URLSearchParams` ép chuỗi thành `10.7,106.6` và máy chủ nhận một thứ không phải JSON.
3. `identify_tree("photo.jpg")` ở Python duyệt CHUỖI thành từng ký tự rồi tải lên chín tệp một ký
   tự. Không hàm nào ném.

Cả ba đều im lặng. Mỗi bên đều có bộ kiểm riêng và cả hai đều xanh — bộ kiểm riêng chỉ chứng minh
một bên tự nhất quán với chính nó, nó không so hai bên với nhau. Đó là việc của `conformance.json`.

## Bộ ca kiểm phải phân biệt được HAI CỰC

Viết một ca thì hỏi trước: *"đầu vào của ca này có phân biệt được hai bên đột biến không?"* — hỏi
TRƯỚC câu "nó xanh hay đỏ". Ca xanh ở cả hai cực thì nó không kiểm gì.

Đo được ngày 2026-09-08: ca *"một tệp lẻ không bọc trong danh sách"* ban đầu dựng đầu vào giống
nhau cho cả hai ngôn ngữ, và khi gỡ hàng rào chuỗi trong `_as_file_list` thì 57/57 ca Python **vẫn
xanh**. Ca ấy mang đúng tên của lỗi nó bỏ lọt. Nay nó dùng chỗ giữ `$single_file`, dựng thành
chuỗi đường dẫn bên Python và đối tượng tệp bên JavaScript — hai lối dựng khác nhau là cố ý, vì
mỗi ngôn ngữ hỏng theo một kiểu riêng ở đúng chỗ đó.
