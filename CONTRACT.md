# Hợp đồng API

Bản đầy đủ và luôn tươi là `https://api.orilife.io/openapi.json` — sinh từ chính mã đang chạy.
Trang này nói những thứ một tệp đặc tả không nói được: cửa nào dùng khi nào, chỗ nào dễ hiểu sai,
và điều gì hệ **cố ý không** trả lời.

Base URL: `https://api.orilife.io`

---

## 1. Xác thực

| Cửa | Việc |
|---|---|
| `POST /api/signup` | Mở tài khoản. Thân JSON `{username, password}` |
| `POST /api/login` | Lấy khoá. Thân JSON `{username, password}` |
| `POST /api/logout` | Bỏ khoá hiện tại |
| `POST /api/logout-all` | Bỏ **mọi** khoá của tài khoản — dùng khi nghi lộ |
| `GET /api/me` | Tài khoản đang đăng nhập là ai |
| `GET /api/auth/did/challenge` → `POST /api/auth/did/verify` | Đăng nhập bằng khoá PhoenixKey, không mật khẩu |

Khoá đi trong header: `Authorization: Bearer <token>`. Sống **12 giờ**, hết hạn thì cửa trả `401`.

Luật tài khoản — đây là chỗ vấp đầu tiên của gần như mọi lần tích hợp:

- Tên đăng nhập **3–32 ký tự**, chỉ chữ thường, chữ số, dấu chấm và gạch dưới. **Không có gạch
  nối.** `vuon-cua-toi` sai; `vuon_cua_toi` đúng.
- Mật khẩu tối thiểu **10 ký tự**, ít nhất **hai nhóm ký tự**, và không nằm trong danh sách mật
  khẩu phổ biến.
- Sai luật trả `400` kèm câu nói rõ sai chỗ nào — hiện thẳng câu đó cho người dùng.

Ứng dụng chạy trong trình duyệt: dùng Bearer, **không** dùng cookie. Máy chủ mở CORS cho mọi
origin nhưng không gửi cookie khác origin, nên đường cookie chỉ hoạt động ở cùng origin.

---

## 2. Định danh

### Cửa gộp — không cần biết trước đang chụp gì

```
POST /api/identify/auto      files[] · lat? · lon? · species? · farm_id?
```

```json
{
  "ok": true,
  "kind": "tree",
  "kind_confidence": 0.82,
  "kind_need_confirm": false,
  "lane": "/api/identify",
  "result": { "...": "nguyên văn phản hồi của cửa đã chạy" },
  "message": "câu tiếng Việt cho người dùng"
}
```

- `result` là **nguyên văn** phản hồi của cửa đã chạy — không cắt trường, không đổi tên. Hình dạng
  của nó xem mục cửa tương ứng bên dưới.
- `kind` là `tree` · `fruit` · `animal`, hoặc `null` khi máy chưa nhận ra. `null` thì `result` cũng
  `null` — hệ nói "chưa biết" chứ không xếp bừa.
- `kind_need_confirm = true` ⟹ hiện `kind` như một **gợi ý** và để người dùng đổi, đừng nhảy thẳng.
- Con vật: cửa đích còn đòi `species` và `farm_id`. Thiếu thì `result` là `null` và `need` liệt kê
  hai trường ấy. Máy chủ **không đoán hộ loài** — loài đoán hộ sẽ được ghi vào hồ sơ cá thể mà
  không ai kiểm được.
- Cửa đích từ chối (`413` · `429` · `400`) thì mã trạng thái và header `Retry-After` **đi ra
  nguyên vẹn**, không bị bọc thành `200`.

Biết trước loại thì gọi thẳng cửa riêng, tiết kiệm một bước nhận loại.

### Ba cửa riêng

| Cửa | Tệp | Ghi chú |
|---|---|---|
| `POST /api/identify` | `files[]` | Nhiều góc thì chắc hơn hẳn một ảnh |
| `POST /api/identify/video` | `file` | Quay một vòng quanh cây. Clip **không** được lưu |
| `POST /api/fruit/identify` | `file` | `tree_id` thu hẹp về một cây; bỏ trống thì tìm cả vườn |
| `POST /api/animal/identify` | `image` | Cần `species` và `farm_id` |
| `POST /api/kind` | `file` | Chỉ hỏi *đang nhìn cái gì*, chưa định danh |

Phản hồi định danh cây:

```json
{
  "ok": true,
  "decision": "MATCH",
  "tree_id": "…",
  "name": "cây sầu riêng số 47",
  "query_id": "…",
  "confidence": "cao",
  "allow_enroll_new": true,
  "needs_location_update": false,
  "warnings": [],
  "candidates": [ { "tree_id": "…", "name": "…", "relation": "owner", "…": "…" } ]
}
```

- `confidence` là một **mức thô** (`cao` · `vừa` · `thấp`), không phải điểm số. Đừng dựng luật
  quyết định lên nó — quyết định đã nằm ở `decision`.
- `allow_enroll_new` là cờ **đọc thẳng**, đừng suy ra từ `decision`. Nó mở đường "không phải cây
  nào cả, tạo cây mới".
- `query_id` giữ lại: gửi kèm khi báo đúng/sai qua `/api/identify_verdict`. Đó là cách hệ học từ
  thực địa, và là thứ rẻ nhất một ứng dụng có thể đóng góp.
- `candidates[].relation` là `owner` · `granted` · `public`. Khoảng cách và số ngày chỉ có mặt cho
  cá thể mà người xem được quyền đọc riêng tư — cắt bớt là để người ta không tam giác đạc ra vị
  trí vườn người khác.

Phản hồi có thể mang thêm trường ngoài danh sách này. **Chuyển tiếp nguyên văn cho ứng dụng, đừng
dựng luật quyết định trên chúng** — chúng là dữ liệu đo đạc, hình dạng có thể đổi, và bộ này cố ý
không giải nghĩa chúng.

---

## 3. Đăng ký và bồi hồ sơ

| Cửa | Việc |
|---|---|
| `POST /api/enroll` | Đăng ký cây mới: `files[]` · `name` · `lat?` · `lon?` · `farm_id?` · `species?` |
| `POST /api/verify_add` | Xác nhận đúng cây rồi bổ sung góc chụp: `tree_id` · `files[]` |
| `POST /api/fruit/enroll` · `POST /api/fruit/add_view` | Cùng khuôn, cho quả |
| `POST /api/animal/enroll` | Cho con vật |
| `GET /api/capture/plan` | Còn thiếu góc nào và nên chụp gì tiếp |

Đây là những cửa **GHI**. Gọi lại sau khi mạng đứt có thể tạo bản ghi thứ hai, nên bộ công cụ
**không tự gửi lại** — bắt `NetworkError` rồi hỏi lại danh sách trước khi gửi lại.

Hồ sơ dày lên theo thời gian là cách hệ khoẻ lên: `verify_add` sau mỗi lần nhận diện đúng đáng giá
hơn nhiều so với chụp thật nhiều góc trong một buổi.

---

## 4. Lối công khai — không cần tài khoản

| Cửa | Việc |
|---|---|
| `POST /api/fruit/lookup` | Ảnh một quả → ứng viên trong tập công khai |
| `POST /api/fruit/scan` → `POST /api/fruit/scan/choose` | Luồng quét tại quầy |
| `GET /api/resolve/{code}` | Tra một mã `ORI-…` |
| `GET /api/species/catalog` | Danh mục loài |
| `GET /api/health` | Máy chủ còn sống và làm được gì |
| `GET /api` | Mục lục mọi cửa |

`/api/resolve/{code}` trả một trong ba trạng thái:

| | |
|---|---|
| `public` | Cá thể có thật, chủ đã mở — xem được |
| `restricted` | Có thật, chủ chưa mở |
| `unknown` | Không tra được |

`unknown` **không kèm lý do**. Nếu "mã sai" trả lời khác "mã có thật nhưng riêng tư" thì người dò
mã sẽ đếm được vườn người khác. Đừng suy ra sự tồn tại từ chỗ khác biệt — không có chỗ khác biệt
nào để suy.

---

## 5. Bằng chứng

| Cửa | Việc |
|---|---|
| `GET /api/provenance/{tree_id}` | Mã, địa chỉ ảnh, địa chỉ bản ghi, mã băm, trạng thái neo |
| `GET /api/{entity_type}/{id}/timeline` | Dòng thời gian có xích băm |
| `GET /api/{entity_type}/{id}/proof/{event_id}` | Đường dẫn Merkle của một sự kiện |
| `POST /api/animal/trust/verify-inclusion` | Kiểm một bản ghi thuộc gốc đã neo — ai cũng gọi được |

`entity_type` ∈ `tree` · `fruit` · `farm` · `animal` · `plot`.

Cách tự kiểm những con số này mà không cần tin OriLife: [VERIFY.md](VERIFY.md).

---

## 6. Hình dạng lỗi

Một khuôn cho mọi mã 4xx/5xx:

```json
{ "ok": false, "error": "câu tiếng Việt cho người dùng", "detail": "…" }
```

`429` mang thêm `retry_after` và header `Retry-After`.

⚠️ Một số cửa trả **`200` kèm `ok: false`** — đó là "việc không làm được", không phải "yêu cầu
hỏng". Ứng dụng phải đọc `ok`, không được chỉ đọc mã trạng thái.

| Mã | Nghĩa | Ứng dụng nên làm |
|---|---|---|
| 400 · 422 | Thiếu trường, sai kiểu, không đạt luật | Hiện `error` cho người dùng |
| 401 | Chưa đăng nhập hoặc khoá hết hạn | Đăng nhập lại rồi gọi lại |
| 403 | Không có quyền | Khoá mới **không** giúp |
| 404 | Không tìm thấy | Đừng viết "không tồn tại" — xem mục `unknown` |
| 413 | Vượt trần | Nén nhỏ lại, đừng thử lại nguyên trạng |
| 429 | Gọi quá dày | Chờ đúng `Retry-After` giây |
| 5xx | Phía kia hỏng | Thử lại giãn dần, chỉ với cửa đọc |

---

## 7. Trần

| | |
|---|---|
| Một tệp | 20 MB |
| Một lô ảnh trong một lượt | 64 MB |
| Video | 80 MB |

Trần đếm ngay khi byte đang lên, nên `413` về **trước khi** tải xong — người dùng ở nơi sóng yếu
không phải chờ hết băng thông rồi mới biết là hỏng.

---

## 8. Cho máy đọc

| | |
|---|---|
| `GET /.well-known/orilife.json` | Bản khai dịch vụ — cửa công khai, trần, loại thực thể có tuyến |
| `GET /llms.txt` | Bản đồ một trang cho tác tử ngôn ngữ |
| `GET /openapi.json` | Đặc tả từng cửa |
| `GET /robots.txt` | Phần công khai cho thu thập |

Bản khai dựng từ bảng đường dẫn thật của máy chủ, nên nó không hứa được cửa mã không có.

---

## 9. Bốn thứ hệ cố ý không trả lời

Nói ra để không ai mất thời gian đi tìm.

**Điểm số chi tiết của phép so khớp.** Ứng dụng nhận `decision` và một mức tin cậy thô; mọi tham
số nội bộ của phép so khớp không đi ra ngoài cửa API. Lộ ra thì đối thủ chép được, mà kẻ gian còn
biến hệ thành máy dò để thử đến khi lọt.

**Toạ độ chính xác của cá thể người khác.** Toạ độ ra cửa công khai bị làm thô. Khoảng cách và số
ngày chỉ có với cá thể mà người xem được quyền đọc riêng tư.

**Sự tồn tại của cá thể riêng tư.** Riêng tư và không tồn tại trả cùng một câu trả lời.

**Đoán thay người dùng.** Không rõ thì hệ nói `uncertain` hoặc `unknown`. Đó là kết quả, không
phải lỗi — đừng thử lại, hãy hỏi người dùng hoặc mời chụp thêm một góc.
