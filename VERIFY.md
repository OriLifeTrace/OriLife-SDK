# Kiểm chứng độc lập

Mục tiêu của trang này: sau khi đọc xong, bạn kiểm được một bản ghi OriLife **mà không cần tin
OriLife**, và nếu muốn thì làm lại toàn bộ bằng tay không cần bộ công cụ nào.

Một hệ truy xuất nguồn gốc chỉ đáng tin ở mức người ngoài kiểm được nó. Nếu cách duy nhất để biết
một bản ghi có thật là hỏi chính máy chủ đã tạo ra nó thì hệ đó không chứng minh gì — nó đang lặp
lại lời khai của chính mình.

---

## Ba câu hỏi, ba lớp trả lời

| Câu hỏi | Trả lời bằng | Cần tin ai |
|---|---|---|
| Bản ghi này có bị sửa sau khi neo không? | Băm lại bản ghi, so với con số trên chuỗi | Không ai |
| Ảnh này có đúng là ảnh trong bản ghi không? | Băm lại byte ảnh, so với `sha256` trong bản ghi | Không ai |
| Sự kiện này có nằm trong lịch sử đã neo không? | Đường dẫn Merkle | Không ai |
| Bản ghi này có mô tả đúng cái cây ngoài đời không? | — | **Không kiểm bằng mã được** |

Dòng cuối là ranh giới thật, và nói ra thì tốt hơn để người ta tự phát hiện. Mã băm chứng minh dữ
liệu **không đổi** kể từ lúc neo. Nó không chứng minh dữ liệu **đúng** lúc được tạo ra. Không hệ
thống nào làm được điều đó bằng mật mã học; phần ấy do quy trình và người chịu trách nhiệm gánh.

---

## Nhanh nhất: dùng bộ công cụ

```python
import json, urllib.request
from orilife import Client, verify

prov = Client().provenance("<tree_id>")["provenance"]
# {'code': 'ORI-…', 'record_cid': '…', 'record_hash': '…', 'images': [{'cid': …, 'sha256': …}], 'anchor': {…}}

# Kho lưu trữ đánh địa chỉ theo NỘI DUNG, nên tải từ nút nào cũng ra cùng byte.
record = json.load(urllib.request.urlopen(f"https://lampnet.cloud/{prov['record_cid']}"))

print(verify.summarize(record, prov["record_hash"]))
# {'code': 'ORI-…', 'algorithm': 'sha3-256', 'hash_matches': True, 'missing_fields': [], …}
```

Con số `prov["record_hash"]` cũng nằm trên chuỗi Cardano. Đừng dừng ở chỗ so với thứ máy chủ vừa
đưa cho bạn — đó vẫn là lời khai của một bên. Mở giao dịch trên trình duyệt khối và đọc bằng mắt
(mục kế tiếp); `prov["anchor"]` có mã giao dịch.

---

## Làm lại bằng tay, không cần bộ công cụ

### Bước 1 — Đọc con số trên chuỗi

Mỗi lần neo là một giao dịch Cardano có **metadata nhãn 1454**:

```json
{
  "t":    "OriLifeTrace",
  "code": "ORI-w3gv5j2-A7K9PQ2M",
  "cid":  "<địa chỉ bản ghi trong kho lưu trữ>",
  "h":    "<64 ký tự hex — mã băm của bản ghi>",
  "a":    "sha3-256"
}
```

Trường `a` là thuật toán đã băm ra `h`. Nó có mặt để bạn không phải đoán, và để bản ghi cũ vẫn
kiểm được sau khi hệ đổi thuật toán.

Lịch sử quét của một cá thể neo riêng, **nhãn 1455**: `{"t":"OriLifeMerkle","root":…,"n":…}` —
một giao dịch đại diện cả chuỗi sự kiện.

Mở giao dịch trên bất kỳ trình duyệt khối nào (`cexplorer.io`, `cardanoscan.io`). Trường `network`
trong `/api/anchor/status` cho biết đang neo trên mạng nào.

### Bước 2 — Lấy bản ghi

`GET /api/provenance/{tree_id}` trả `record_cid` — địa chỉ bản ghi trong kho lưu trữ. Tải nó về:

```
https://lampnet.cloud/<record_cid>
```

Kho ấy đánh địa chỉ bằng chính byte của tệp, nên tải từ **bất kỳ nút nào** cũng ra cùng nội dung —
không phải tin nút nào cả. Ảnh nằm ở đúng chỗ đó theo `images[i].cid`.

Cửa này chỉ mở cho cá thể mà chủ đã đặt công khai. Cá thể riêng tư và cá thể không tồn tại trả về
**cùng một** mã 404 — cố ý như vậy, để người dò mã không đếm được vườn người khác.

### Bước 3 — Băm lại

Tuần tự hoá bản ghi theo đúng ba quy tắc này, rồi băm bằng thuật toán mà trường `a` khai:

1. **Khoá sắp xếp** theo điểm mã Unicode, ở mọi tầng.
2. **Không khoảng trắng thừa** — dấu phân cách đúng là `,` và `:`.
3. **Giữ nguyên chữ ngoài ASCII** — `cây sầu riêng` viết thẳng, không thành `cây…`.

Bằng Python thuần, không cần cài gì:

```python
import hashlib, json

canonical = json.dumps(record, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False).encode("utf-8")
print(hashlib.sha3_256(canonical).hexdigest())      # phải bằng trường "h" trên chuỗi
```

Bản ghi cũ (trước 2026-08) không có trường `hash_alg` và dùng `blake2b` đầu ra **32 byte**:

```python
hashlib.blake2b(canonical, digest_size=32).hexdigest()
```

> Cắt ngắn BLAKE2b-512 xuống 32 byte **không** cho ra kết quả này. BLAKE2b nhét độ dài đầu ra vào
> giá trị khởi tạo, nên hai thứ đó là hai hàm băm khác nhau. Đây là chỗ một bản cài đặt dựa vào
> `openssl blake2b512` sẽ sai — và sai theo hướng báo động giả, tức là kết luận "bị sửa" cho một
> bản ghi hoàn toàn lành.

### Bước 4 — Kiểm ảnh

Mỗi ảnh trong bản ghi có trường `sha256`. Tải byte ảnh về, băm lại, so:

```python
hashlib.sha256(open("anh-tai-ve.jpg","rb").read()).hexdigest()
```

---

## Ba chỗ dễ sai

**Đổi thuật toán khai trong bản ghi không giúp được kẻ sửa.** Trường `hash_alg` nằm **bên trong**
phần được băm. Sửa nó để ép người kiểm dùng một hàm băm yếu hơn là đã đổi luôn nội dung, nên mã
băm không còn khớp. Đây là lý do trường đó phải nằm trong bản ghi chứ không nằm cạnh bản ghi.

**Thuật toán lạ phải bị từ chối, không được rơi về mặc định.** Bộ kiểm ở đây trả về "sai" khi gặp
một tên thuật toán ngoài bảng cho phép. Rơi về mặc định là mở đúng cánh cửa mà việc bản ghi tự
khai thuật toán dựng ra để đóng.

**Bản ghi THIẾU trường khác hẳn bản ghi ĐỦ mà lệch mã băm.** Ca thứ nhất gần như luôn là tải hụt
hoặc lấy nhầm mảnh; ca thứ hai mới đáng báo động. `summarize()` tách hai ca này ra bằng trường
`missing_fields` — một công cụ tự động gộp chúng lại sẽ sinh báo động giả, mà báo động giả trong
bộ kiểm chứng còn tệ hơn không kiểm, vì nó dạy người dùng bỏ qua cảnh báo.

---

## Mã cá thể

Mã in trên phiếu có dạng `ORI-<geohash7>-<8 ký tự>`:

- **geohash7** — ô lưới khoảng 150 m. Đủ để nói "vùng nào", **không** đủ để chỉ đúng một gốc cây.
  Đó là chủ ý: một mã công khai không được dẫn người lạ tới tận vườn.
- **8 ký tự** — Crockford base32 của `blake2b(định danh cá thể, 8 byte)`. Bảng chữ Crockford bỏ
  các chữ `I`, `L`, `O`, `U` để người đọc bằng mắt không nhầm với `1` và `0`.
- Không có toạ độ thì phần giữa là bảy số không. Mã vẫn dùng được, chỉ mất phần gợi vùng.

```python
from orilife import verify
verify.entity_code("<entity_id>", [10.762622, 106.660172])
```

Hàm sinh mã dùng **blake2b**, còn hàm băm bản ghi dùng thuật toán bản ghi tự khai. Hai chỗ này cố
ý khác nhau: mã đã in ra giấy và đã nằm trong metadata của mọi lần neo cũ nên không được đổi bao
giờ, còn thuật toán băm bản ghi thì có đường nâng cấp. Ai "đồng bộ" hai chỗ về một hàm băm là làm
hỏng toàn bộ mã đã phát ra ngoài đời.

---

## Bộ vector

`python/tests/vectors.json` sinh ra từ chính mã đang chạy trên máy chủ OriLife: mã cá thể, một bản
ghi đầy đủ kèm mã băm, và một bản ghi thời cũ kèm mã băm thời cũ. Cả bản Python lẫn bản JavaScript
đều đối chiếu với bộ này.

Hai bản cài đặt độc lập cùng khớp một bộ vector là bằng chứng mạnh hơn hẳn một bản tự kiểm lấy
mình: một lỗi phải xuất hiện y hệt ở cả hai ngôn ngữ mới lọt được.

```bash
cd python && python -m pytest tests/test_verify.py -q
cd javascript && node --test test/verify.test.mjs
```

Cả hai chạy **ngoại tuyến**. Nếu chúng cần mạng thì chúng đã không còn là bộ kiểm chứng độc lập.
