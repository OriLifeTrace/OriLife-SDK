"""Khách gọi API OriLife — không phụ thuộc thư viện ngoài, chạy trên Python 3.9 trở lên.

Vì sao không dùng `requests` hay `httpx`: bộ này sẽ chạy trong những chỗ không cài thêm được gì —
một máy tính nhúng ngoài đồng, một tác tử trong hộp cát, một hàm không máy chủ có trần dung lượng.
Thư viện chuẩn đủ làm mọi thứ ở đây, và một tệp không phụ thuộc thì kiểm được bằng mắt.

Ba việc bộ này làm hộ mà tự viết sẽ quên:

  • Chờ đúng nhịp khi bị hạn tần suất. Máy chủ trả 429 kèm `Retry-After`; thử lại ngay chỉ kéo
    dài thời gian bị chặn. Ở đây tự đọc header đó và ngủ đúng bấy nhiêu.
  • Chỉ thử lại việc thử lại được. Cửa ĐỌC hỏng vì mạng thì gọi lại vô hại; cửa GHI thì không —
    yêu cầu có thể đã tới nơi và đã tạo bản ghi. Bảng `_IDEMPOTENT` giữ ranh giới này.
  • Không diễn giải phần nội tạng. Phản hồi định danh có thể mang thêm trường số; bộ này chuyển
    nguyên văn cho ứng dụng mà KHÔNG đặt tên, KHÔNG giải nghĩa, KHÔNG dựng luật quyết định trên
    chúng. Quyết định thuộc về máy chủ; ứng dụng đọc `decision` và `confidence`.
"""
from __future__ import annotations

import json
import mimetypes
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple, Union

from .errors import NetworkError, RateLimitedError, ServerError, from_response

__all__ = ["Client", "DEFAULT_BASE_URL"]

DEFAULT_BASE_URL = "https://api.orilife.io"
_USER_AGENT = "orilife-sdk-python/1.0"

# Cửa gọi lại được mà không sinh thêm bản ghi. Mọi cửa khác chỉ thử lại khi lỗi là 429 hoặc 5xx —
# hai ca đó máy chủ đã nói thẳng là chưa làm gì.
_IDEMPOTENT = ("GET", "HEAD")

FileArg = Union[str, bytes, Tuple[str, bytes], Tuple[str, bytes, str]]


def _as_file(item: FileArg) -> Tuple[str, bytes, str]:
    """Nhận đường dẫn, khối byte, hoặc bộ ba, trả về (tên tệp, byte, kiểu nội dung)."""
    if isinstance(item, str):
        with open(item, "rb") as fh:
            data = fh.read()
        name = os.path.basename(item)
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        return name, data, ctype
    if isinstance(item, bytes):
        return "upload.jpg", item, "image/jpeg"
    if isinstance(item, tuple) and len(item) == 2:
        return item[0], item[1], (mimetypes.guess_type(item[0])[0] or "application/octet-stream")
    if isinstance(item, tuple) and len(item) == 3:
        return item
    raise TypeError("tệp phải là đường dẫn, bytes, (tên, bytes) hoặc (tên, bytes, kiểu)")


def _multipart(fields: Dict[str, Any], files: Sequence[Tuple[str, FileArg]]) -> Tuple[bytes, str]:
    """Dựng thân multipart bằng tay.

    Tự dựng thay vì dùng `email.mime` vì phần đó chèn ngắt dòng theo cách riêng của thư điện tử,
    và một byte thừa trong thân nhị phân là một tấm ảnh hỏng ở đầu bên kia.
    """
    boundary = f"----orilife{uuid.uuid4().hex}"
    out = bytearray()
    for key, value in fields.items():
        if value is None:
            continue
        out += f"--{boundary}\r\n".encode()
        out += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
        out += str(value).encode("utf-8") + b"\r\n"
    for key, item in files:
        name, data, ctype = _as_file(item)
        out += f"--{boundary}\r\n".encode()
        out += (f'Content-Disposition: form-data; name="{key}"; '
                f'filename="{name}"\r\n').encode()
        out += f"Content-Type: {ctype}\r\n\r\n".encode()
        out += data + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


class Client:
    """Một phiên làm việc với máy chủ OriLife.

        client = Client()
        client.login("vuon_cua_toi", "vuon.sau.rieng.2026")
        result = client.identify_auto(["anh.jpg"], lat=10.762, lon=106.660)

    Khoá sống 12 giờ. Hết hạn thì cửa trả 401 và bộ này ném `AuthError` — bắt lấy rồi gọi
    `login()` lại. Cố ý KHÔNG tự đăng nhập lại ngầm: giữ mật khẩu trong bộ nhớ suốt vòng đời ứng
    dụng để phòng khi cần là đổi một lỗi nhìn thấy được thành một rủi ro không nhìn thấy.
    """

    def __init__(self, base_url: str = DEFAULT_BASE_URL, *, token: Optional[str] = None,
                 timeout: float = 30.0, max_retries: int = 2,
                 user_agent: str = _USER_AGENT):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = float(timeout)
        self.max_retries = max(0, int(max_retries))
        self.user_agent = user_agent

    # ── tầng vận chuyển ────────────────────────────────────────────────────────────────────

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if extra:
            headers.update(extra)
        return headers

    def request(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None,
                fields: Optional[Dict[str, Any]] = None,
                files: Optional[Sequence[Tuple[str, FileArg]]] = None,
                json_body: Optional[Any] = None, timeout: Optional[float] = None) -> Any:
        """Gọi một cửa. Ném lỗi có kiểu khi phía kia từ chối; trả về dữ liệu đã giải mã khi xong."""
        url = self.base_url + path
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            if clean:
                url += "?" + urllib.parse.urlencode(clean)

        body: Optional[bytes] = None
        extra: Dict[str, str] = {}
        if files:
            body, ctype = _multipart(fields or {}, files)
            extra["Content-Type"] = ctype
        elif json_body is not None:
            body = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            extra["Content-Type"] = "application/json"
        elif fields:
            body = urllib.parse.urlencode({k: v for k, v in fields.items()
                                           if v is not None}).encode("utf-8")
            extra["Content-Type"] = "application/x-www-form-urlencoded"

        attempt = 0
        while True:
            try:
                return self._once(method, url, body, extra, timeout or self.timeout, path)
            except RateLimitedError as e:
                # Chờ đúng nhịp máy chủ bảo. Đây là ca DUY NHẤT ngủ theo số của phía kia thay vì
                # theo công thức của mình — phía kia biết hàng chờ của nó, mình thì không.
                if attempt >= self.max_retries:
                    raise
                time.sleep(min(e.retry_after, 60.0))
            except (ServerError, NetworkError):
                if attempt >= self.max_retries or method.upper() not in _IDEMPOTENT:
                    raise
                time.sleep(min(2.0 ** attempt, 8.0))
            attempt += 1

    def _once(self, method: str, url: str, body: Optional[bytes],
              extra: Dict[str, str], timeout: float, path: str) -> Any:
        req = urllib.request.Request(url, data=body, method=method.upper(),
                                     headers=self._headers(extra))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                return self._decode(raw, resp.headers)
        except urllib.error.HTTPError as e:
            raw = e.read()
            payload: Any
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:                                   # noqa: BLE001 — thân không phải JSON
                payload = {"error": raw.decode("utf-8", "replace")[:400]}
            raise from_response(e.code, payload, path=path, headers=e.headers) from None
        except urllib.error.URLError as e:
            raise NetworkError(f"Không kết nối được máy chủ: {e.reason}", path=path) from None
        except TimeoutError:
            raise NetworkError("Máy chủ không trả lời kịp.", path=path) from None

    @staticmethod
    def _decode(raw: bytes, headers: Any) -> Any:
        ctype = (headers.get("Content-Type") or "") if hasattr(headers, "get") else ""
        if "json" in ctype:
            return json.loads(raw.decode("utf-8"))
        return raw

    # ── xác thực ───────────────────────────────────────────────────────────────────────────

    def signup(self, username: str, password: str) -> dict:
        """Mở tài khoản mới và giữ luôn khoá.

        Luật: tên đăng nhập 3–32 ký tự, chỉ chữ thường, chữ số, dấu chấm và gạch dưới — KHÔNG có
        gạch nối. Mật khẩu tối thiểu 10 ký tự, ít nhất hai nhóm ký tự, và không nằm trong danh
        sách mật khẩu phổ biến. Sai luật thì máy chủ trả 400 kèm câu nói rõ sai chỗ nào.
        """
        data = self.request("POST", "/api/signup",
                            json_body={"username": username, "password": password})
        return self._keep_token(data)

    def login(self, username: str, password: str) -> dict:
        data = self.request("POST", "/api/login",
                            json_body={"username": username, "password": password})
        return self._keep_token(data)

    def _keep_token(self, data: Any) -> dict:
        if isinstance(data, dict) and data.get("token"):
            self.token = data["token"]
        return data if isinstance(data, dict) else {"ok": True}

    def me(self) -> dict:
        return self.request("GET", "/api/me")

    def logout(self) -> dict:
        out = self.request("POST", "/api/logout")
        self.token = None
        return out

    # ── cửa công khai: gọi được khi CHƯA đăng nhập ─────────────────────────────────────────

    def health(self) -> dict:
        """Máy chủ còn sống và hôm nay làm được gì.

        Đọc `features` rồi mới quyết định hiện màn hình nào. Danh sách đó sinh từ bảng đường dẫn
        thật của máy chủ nên nó không lạc hậu — viết cứng danh sách năng lực ở phía ứng dụng thì
        máy chủ thêm năng lực mà ứng dụng vẫn giấu, còn máy chủ bỏ thì ứng dụng vẫn mời gọi.
        """
        return self.request("GET", "/api/health")

    def describe(self) -> dict:
        """Bản khai dịch vụ cho máy — cửa nào không cần khoá, trần bao nhiêu, loại nào có tuyến."""
        return self.request("GET", "/.well-known/orilife.json")

    def endpoints(self) -> dict:
        return self.request("GET", "/api")

    def species_catalog(self) -> dict:
        return self.request("GET", "/api/species/catalog")

    def resolve(self, code: str) -> dict:
        """Tra một mã `ORI-…`.

        Ba trạng thái: `public` (xem được), `restricted` (có thật, chủ chưa mở), `unknown`.
        `unknown` KHÔNG kèm lý do, và cố ý như vậy: nếu "mã sai" trả lời khác "mã riêng tư" thì
        người dò mã sẽ đếm được vườn người khác. Đừng suy ra sự tồn tại từ chỗ khác biệt.
        """
        return self.request("GET", f"/api/resolve/{urllib.parse.quote(code)}")

    def tree_by_code(self, code: str) -> dict:
        """Xuất xứ của một cây theo MÃ in trên phiếu — cho người mua, không cần tài khoản.

        Cây riêng tư và cây không tồn tại trả về CÙNG mã 404. Đừng viết "mã sai" lên màn hình.
        """
        return self.request("GET", f"/api/tree_by_code/{urllib.parse.quote(code)}")

    def lookup_fruit(self, image: FileArg) -> dict:
        """Ảnh một quả → ứng viên trong tập công khai. Không cần tài khoản, không giữ dữ liệu ai."""
        return self.request("POST", "/api/fruit/lookup", files=[("file", image)])

    # ── định danh ──────────────────────────────────────────────────────────────────────────

    def identify_auto(self, images: Iterable[FileArg], *, lat: Optional[float] = None,
                      lon: Optional[float] = None, species: Optional[str] = None,
                      farm_id: Optional[str] = None) -> dict:
        """MỘT cửa cho mọi loại: máy tự nhận cây, quả hay con vật rồi định danh luôn.

        Không phải hỏi người dùng đang chụp gì. Trả về `kind`, `lane` (cửa đã chạy) và `result`
        là nguyên văn phản hồi của cửa đó.

        Con vật: cửa đích còn đòi `species` và `farm_id`. Thiếu thì `result` là None và `need`
        liệt kê hai trường ấy — máy chủ KHÔNG đoán hộ loài, vì loài đoán hộ sẽ được ghi vào hồ sơ
        cá thể mà không ai kiểm được.
        """
        return self.request("POST", "/api/identify/auto",
                            fields={"lat": lat, "lon": lon,
                                    "species": species, "farm_id": farm_id},
                            files=[("files", f) for f in images])

    def identify_tree(self, images: Iterable[FileArg], *, lat: Optional[float] = None,
                      lon: Optional[float] = None, last_tree: Optional[str] = None) -> dict:
        """Nhận diện lại một cây. Gửi nhiều ảnh từ nhiều góc thì chắc hơn hẳn một ảnh.

        Toạ độ là tuỳ chọn nhưng nên gửi: nó thu hẹp vùng so khớp và làm mã truy xuất ổn định hơn.
        """
        return self.request("POST", "/api/identify",
                            fields={"lat": lat, "lon": lon, "last_tree": last_tree,
                                    "source": "sdk"},
                            files=[("files", f) for f in images])

    def identify_tree_video(self, video: FileArg, *, lat: Optional[float] = None,
                            lon: Optional[float] = None) -> dict:
        """Quay một vòng quanh cây thay vì chụp rời. Clip KHÔNG được lưu, chỉ dùng rồi bỏ."""
        return self.request("POST", "/api/identify/video",
                            fields={"lat": lat, "lon": lon, "source": "sdk"},
                            files=[("file", video)], timeout=max(self.timeout, 120.0))

    def identify_fruit(self, image: FileArg, *, tree_id: Optional[str] = None) -> dict:
        """Nhận diện lại một quả. `tree_id` thu hẹp về đúng một cây; bỏ trống thì tìm cả vườn."""
        return self.request("POST", "/api/fruit/identify",
                            fields={"tree_id": tree_id}, files=[("file", image)])

    def identify_animal(self, image: FileArg, *, species: str, farm_id: str) -> dict:
        return self.request("POST", "/api/animal/identify",
                            fields={"species": species, "farm_id": farm_id},
                            files=[("image", image)])

    def identify_kind(self, image: FileArg) -> dict:
        """Chỉ hỏi ĐANG NHÌN CÁI GÌ, chưa định danh. Dùng khi muốn tự điều hướng luồng."""
        return self.request("POST", "/api/kind", files=[("file", image)])

    # ── đăng ký ────────────────────────────────────────────────────────────────────────────

    def enroll_tree(self, images: Iterable[FileArg], *, name: str,
                    lat: Optional[float] = None, lon: Optional[float] = None,
                    farm_id: Optional[str] = None, species: Optional[str] = None) -> dict:
        """Đăng ký một cây mới.

        Đây là cửa GHI: gọi lại sau khi mạng đứt có thể tạo cây thứ hai, nên bộ này KHÔNG tự thử
        lại. Bắt `NetworkError` rồi hỏi lại `list_trees()` xem cây đã vào chưa trước khi gửi lại.
        """
        return self.request("POST", "/api/enroll",
                            fields={"name": name, "lat": lat, "lon": lon,
                                    "farm_id": farm_id, "species": species},
                            files=[("files", f) for f in images])

    def verify_add(self, tree_id: str, images: Iterable[FileArg]) -> dict:
        """Xác nhận đúng cây rồi bổ sung góc chụp — cách làm hồ sơ dày lên theo thời gian."""
        return self.request("POST", "/api/verify_add", fields={"tree_id": tree_id},
                            files=[("files", f) for f in images])

    def list_trees(self, *, farm_id: Optional[str] = None) -> dict:
        return self.request("GET", "/api/trees", params={"farm_id": farm_id})

    # ── bằng chứng ─────────────────────────────────────────────────────────────────────────

    def provenance(self, tree_id: str) -> dict:
        """Mã, địa chỉ ảnh, địa chỉ bản ghi, mã băm, trạng thái neo — nguyên liệu để tự kiểm."""
        return self.request("GET", f"/api/provenance/{urllib.parse.quote(tree_id)}")

    def timeline(self, entity_type: str, entity_id: str) -> dict:
        return self.request("GET", f"/api/{entity_type}/{urllib.parse.quote(entity_id)}/timeline")

    def proof(self, entity_type: str, entity_id: str, event_id: str) -> dict:
        """Đường dẫn Merkle chứng minh một sự kiện thuộc gốc đã neo lên chuỗi."""
        return self.request(
            "GET",
            f"/api/{entity_type}/{urllib.parse.quote(entity_id)}"
            f"/proof/{urllib.parse.quote(event_id)}")
