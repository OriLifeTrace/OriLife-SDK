# OriLife SDK

Định danh **cá thể** — không phải "đây là cây sầu riêng", mà là "đây là **cây số 47** của vườn này".
Bằng chính ảnh chụp nó. Không tem, không mã QR, không thẻ gắn lên vật.

Bộ này là thứ bạn cần để viết một ứng dụng nói chuyện với OriLife, và cũng là thứ người khác cần
để **kiểm chứng** những gì OriLife nói mà không phải tin OriLife.

```
Base URL   https://api.orilife.io
Tài liệu   https://api.orilife.io/docs   ·   https://api.orilife.io/openapi.json
Cho máy    https://api.orilife.io/.well-known/orilife.json   ·   https://api.orilife.io/llms.txt
```

---

## Ba mươi giây

**Python** — không phụ thuộc thư viện nào, Python 3.9 trở lên:

```bash
pip install orilife
```

```python
from orilife import Client

client = Client()
client.signup("vuon_cua_toi", "vuon.sau.rieng.2026")

# Không phải hỏi người dùng đang chụp cây, quả hay con vật — máy tự nhận.
out = client.identify_auto(["anh.jpg"], lat=10.762, lon=106.660)
print(out["kind"], out["result"]["decision"])
```

**JavaScript** — trình duyệt, Node 18+, Deno, Bun, Cloudflare Workers:

```bash
npm install @orilife/sdk
```

```js
import { Client } from '@orilife/sdk';

const client = new Client();
await client.login('vuon_cua_toi', 'vuon.sau.rieng.2026');
const out = await client.identifyAuto([file], { lat: 10.762, lon: 106.660 });
```

**Không dùng bộ nào cả** — API là HTTP thuần:

```bash
curl -X POST https://api.orilife.io/api/identify/auto \
  -H "Authorization: Bearer $TOKEN" \
  -F 'files=@anh.jpg' -F 'lat=10.762' -F 'lon=106.660'
```

---

## Hai nửa, và nửa thứ hai mới là nửa quan trọng

```python
from orilife import Client   # gọi API  — bạn đang TIN OriLife
from orilife import verify   # kiểm chứng — bạn KHÔNG phải tin ai
```

`Client` hỏi máy chủ rồi chép lại câu trả lời. Nếu cách duy nhất để biết một bản ghi có thật là
hỏi chính máy chủ đã tạo ra nó thì hệ đó không chứng minh gì hết — nó đang lặp lại lời khai của
chính mình.

`verify` là đường thoát khỏi vòng lặp đó. Nó tính lại mã băm từ chính bản ghi, đối chiếu với con
số đã neo lên chuỗi Cardano. Không mạng, không phụ thuộc, không cần OriLife có mặt:

```python
from orilife import verify

record = json.load(open("ban-ghi-tai-ve.json"))   # tải từ bất kỳ đâu
onchain = "3f0a…"                                  # đọc trên trình duyệt khối

verify.verify_record(record, onchain)   # True nghĩa là chưa ai đụng vào bản ghi này
```

Cùng phép toán ấy chạy trong trình duyệt:

```js
import * as verify from '@orilife/sdk/verify';
verify.verifyRecord(record, onchain);
```

Hai bản cài đặt độc lập, cùng khớp một bộ vector sinh từ chính mã đang chạy trên máy chủ. Chi tiết
và cách tự làm lại bằng tay: [VERIFY.md](VERIFY.md).

---

## Nhận diện những gì

| Loại | Đăng ký | Nhận diện lại | Tình trạng |
|---|---|---|---|
| Cây | `POST /api/enroll` | `POST /api/identify` | Đang chạy ngoài vườn |
| Quả | `POST /api/fruit/enroll` | `POST /api/fruit/identify` | Đang chạy ngoài vườn |
| Con vật | `POST /api/animal/enroll` | `POST /api/animal/identify` | Chạy được; cửa còn đòi khai `species` và `farm_id` |
| Hoa, sản phẩm chế biến | — | — | **Chưa có tuyến nào** |

Bảng này không chép tay ở đây mà cũng nằm ở `/.well-known/orilife.json`, sinh từ bảng đường dẫn
thật của máy chủ. Danh sách chép tay thì đúng đúng một ngày.

`POST /api/identify/auto` là cửa gộp: gửi ảnh, máy tự nhận loại rồi định danh luôn. Ứng dụng
**không phải hỏi người dùng đang chụp cái gì** — đẩy việc phân loại sang cho con người vì máy chưa
làm chính là hình dạng OriLife sinh ra để phá.

---

## Hai lối vào

**Lối công khai — không cần tài khoản.** Cho ứng dụng người mua: khách chụp một quả đang bày, hoặc
quét mã trên phiếu, và tra ra nguồn gốc.

```python
Client().lookup_fruit("qua.jpg")             # ảnh một quả → ứng viên công khai
Client().resolve("ORI-w3gv5j2-A7K9PQ2M")     # tra một mã
Client().species_catalog()                   # danh mục loài
Client().health()                            # máy chủ làm được gì hôm nay
```

**Lối chủ vườn — cần khoá.** Đăng ký cây, nhận diện lại, ghi nhật ký chăm sóc, dựng 3D, neo bằng
chứng. Mỗi tài khoản chỉ so khớp **trong vườn của chính mình** — vừa là riêng tư, vừa là độ chính
xác, vì hai cây cùng loài ở hai tỉnh không có cơ hội lẫn vào nhau.

Luật tài khoản, đọc trước khi gọi dòng đầu tiên: tên đăng nhập 3–32 ký tự, chỉ **chữ thường, chữ
số, dấu chấm và gạch dưới** — không có gạch nối. Mật khẩu tối thiểu 10 ký tự, ít nhất hai nhóm ký
tự, không nằm trong danh sách mật khẩu phổ biến. Khoá sống 12 giờ.

---

## Ba điều nên biết trước khi viết dòng đầu tiên

**Đọc năng lực, đừng viết cứng.** `GET /api/health` trả `features` sinh từ bảng đường dẫn thật.
Ứng dụng đọc nó rồi mới quyết định hiện màn hình nào — máy chủ thêm năng lực là dùng được ngay,
không cần bản cập nhật.

**"Chưa chắc" là một kết quả, không phải lỗi.** Hệ trả `uncertain` thay vì đoán bừa. Đừng thử lại,
đừng hiện vòng xoay — hãy hỏi người dùng, hoặc mời chụp thêm một góc.

**`unknown` khi tra mã không kèm lý do, và cố ý như vậy.** Nếu "mã sai" trả lời khác "mã có thật
nhưng riêng tư" thì người dò mã sẽ đếm được vườn người khác. Đừng suy ra sự tồn tại từ chỗ khác
biệt — không có chỗ khác biệt nào.

---

## Lỗi

Mỗi mã trạng thái là một lớp lỗi riêng, vì ứng dụng phải xử chúng theo những cách khác hẳn nhau.

| Mã | Lớp | Ứng dụng nên làm |
|---|---|---|
| — | `NetworkError` | Yêu cầu có thể **chưa tới nơi**. Cửa đọc thì gọi lại; cửa ghi thì hỏi lại trạng thái trước |
| 400 · 422 | `InvalidRequestError` | Thiếu trường hoặc không đạt luật. Hiện `message` cho người dùng |
| 401 | `AuthError` | Khoá hết hạn. Đăng nhập lại rồi gọi lại |
| 403 | `PermissionError` | Không có quyền. Xin khoá mới **không** giúp |
| 404 | `NotFoundError` | Đừng viết "không tồn tại" lên màn hình — xem mục `unknown` ở trên |
| 413 | `TooLargeError` | Nén nhỏ lại rồi gửi lại, đừng thử lại nguyên trạng |
| 429 | `RateLimitedError` | Chờ đúng `retry_after` giây. Bộ này tự chờ hộ |
| 5xx | `ServerError` | Thử lại giãn dần — nhưng chỉ với cửa đọc |

Câu trong `message` là câu máy chủ đã viết sẵn cho người dùng đọc. **Hiện thẳng câu đó**, đừng tự
dịch mã lỗi thành câu của mình: máy chủ biết ngữ cảnh, ứng dụng thì không.

---

## Giới hạn

| | |
|---|---|
| Một tệp | 20 MB |
| Một lô ảnh | 64 MB |
| Video | 80 MB |
| Khoá sống | 12 giờ |
| Quá dày | `429` kèm header `Retry-After` |

Trần được đếm ngay khi byte đang lên, nên `413` về **trước khi** tải xong — không phải chờ hết
băng thông rồi mới biết là hỏng.

---

## Trình duyệt, bot và tác tử

CORS mở cho mọi origin, kèm **không** gửi cookie khác origin. Nghĩa là trang web ở bất kỳ đâu cũng
gọi được, mà không trang nào mượn được phiên đăng nhập của người dùng — khoá phải đi bằng header
`Authorization: Bearer`, và cả lớp CSRF biến mất.

Cho thứ đọc bằng máy:

| | |
|---|---|
| `GET /.well-known/orilife.json` | Bản khai dịch vụ: cửa nào không cần khoá, trần bao nhiêu, loại nào có tuyến |
| `GET /llms.txt` | Bản đồ một trang cho tác tử ngôn ngữ |
| `GET /openapi.json` | Đặc tả từng cửa, sinh mã client được |

---

## Trong kho này có gì, và cố ý không có gì

**Có:** khách gọi API (Python, JavaScript), bộ kiểm chứng độc lập, hợp đồng API, ví dụ chạy được.

**Không có:** phần nhận diện. Cách máy quyết định hai tấm ảnh là cùng một cá thể nằm trên máy chủ
và không rời khỏi đó.

Ranh giới ấy không phải mới dựng cho kho này — nó đã có sẵn ở tầng phản hồi của máy chủ: điểm số
chi tiết và mọi tham số nội bộ của phép so khớp đều **không đi ra ngoài cửa API**. Ứng dụng nhận
`decision` và một mức tin cậy thô, không nhận nội tạng. Hai lý do, và lý do thứ hai
quan trọng hơn lý do thứ nhất: nội tạng lộ ra thì đối thủ chép được, mà kẻ gian còn biến hệ thành
máy dò để thử đến khi lọt.

Nói cách khác: mọi thứ **phía ngoài** ranh giới đó thì mở, gồm cả toàn bộ đường kiểm chứng — thứ
duy nhất bạn cần để bắt OriLife nói dối. Phần **bên trong** thì đóng.

---

## Chạy bài kiểm

```bash
cd python && python -m pytest tests/ -q      # 34 bài, chạy được ngoại tuyến
cd javascript && node --test test/           # 23 bài, không cài gì thêm
```

Bộ kiểm chứng của hai ngôn ngữ đối chiếu với **cùng một** bộ vector sinh từ mã đang chạy trên máy
chủ (`python/tests/vectors.json`). Hai bản cài đặt độc lập cùng khớp một bộ vector là bằng chứng
mạnh hơn hẳn một bản tự kiểm lấy mình.

---

## Đọc tiếp

- [CONTRACT.md](CONTRACT.md) — hợp đồng API đầy đủ: từng cửa, từng trường, từng khuôn lỗi
- [VERIFY.md](VERIFY.md) — kiểm chứng độc lập, kể cả cách làm lại bằng tay không cần bộ này
- [SECURITY.md](SECURITY.md) — giữ khoá, và những thứ không bao giờ được nhúng vào ứng dụng
- [examples/](examples/) — ví dụ chạy được

---

## In English

OriLife identifies **individuals** — not "this is a durian tree" but "this is **tree 47** in this
orchard" — from photographs alone. No tags, no QR codes, nothing attached to the object.

This repository holds the official client SDKs (Python, JavaScript), the public API contract, and
an **independent verifier**. The verifier is the part that matters: it recomputes record hashes
from the record itself and checks them against what was anchored on Cardano, so a third party can
confirm OriLife's claims without trusting — or even contacting — OriLife. It has no dependencies
and needs no network.

The recognition engine is not here and will not be. Everything outside the API response boundary
is open, including the entire verification path; everything inside stays closed.

API docs (Vietnamese): <https://api.orilife.io/docs>. Machine-readable service descriptor:
<https://api.orilife.io/.well-known/orilife.json>.

---

Apache-2.0. Bằng chứng neo trên Cardano, dữ liệu lưu phân tán trên LampNet.
