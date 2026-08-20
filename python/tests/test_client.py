"""Khách gọi API phải cư xử đúng ở những chỗ người ta hay tự viết sai.

Bốn chỗ đó, và cả bốn đều chỉ lộ ra khi mạng xấu hoặc máy chủ bận — tức là đúng lúc không ai ngồi
xem nhật ký:

  • 429 kèm `Retry-After`: chờ đúng nhịp máy chủ bảo, không phải nhịp của mình.
  • Cửa GHI hỏng giữa chừng: KHÔNG tự gửi lại, vì yêu cầu có thể đã tới nơi và đã tạo bản ghi.
  • Lỗi phải có KIỂU, vì ứng dụng xử 401 khác 413 khác 429 — gộp một chuỗi là đẩy việc phân loại
    sang cho người viết ứng dụng.
  • Câu cho người dùng lấy từ `error`/`message`, không lấy từ `detail` (khuôn của tầng kiểm tham
    số, thường là cấu trúc chứ không phải câu).

Dựng một máy chủ giả bằng thư viện chuẩn — không mạng ra ngoài, chạy được trong hộp cát.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from orilife import Client, errors  # noqa: E402

SEEN: list = []
SCRIPT: list = []


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):        # im lặng, đừng làm bẩn đầu ra bài kiểm
        pass

    def _serve(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        SEEN.append({"method": self.command, "path": self.path,
                     "headers": dict(self.headers), "body": body})
        status, payload, extra = SCRIPT.pop(0) if SCRIPT else (200, {"ok": True}, {})
        raw = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    do_GET = do_POST = _serve


@pytest.fixture()
def server():
    SEEN.clear()
    SCRIPT.clear()
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_token_travels_as_a_bearer_header(server):
    SCRIPT.append((200, {"ok": True, "token": "abc123"}, {}))
    SCRIPT.append((200, {"ok": True, "username": "vuon_cua_toi"}, {}))
    c = Client(server)
    c.login("vuon_cua_toi", "vuon.sau.rieng.2026")
    assert c.token == "abc123"
    c.me()
    assert SEEN[1]["headers"]["Authorization"] == "Bearer abc123"


def test_login_body_is_json_not_a_query_string(server):
    """Gửi mật khẩu trong chuỗi truy vấn là để nó rơi vào nhật ký của mọi máy trên đường đi."""
    SCRIPT.append((200, {"ok": True, "token": "t"}, {}))
    Client(server).login("ai_do", "mat.khau.dai.that")
    assert "?" not in SEEN[0]["path"]
    assert SEEN[0]["headers"]["Content-Type"] == "application/json"
    assert json.loads(SEEN[0]["body"])["password"] == "mat.khau.dai.that"


def test_images_go_up_as_multipart_with_their_bytes_intact(server):
    SCRIPT.append((200, {"ok": True, "kind": "tree", "result": {}}, {}))
    c = Client(server, token="t")
    c.identify_auto([("cay.jpg", b"\xff\xd8\x00binary\xff\xd9")], lat=10.5)
    body = SEEN[0]["body"]
    assert b"multipart" in SEEN[0]["headers"]["Content-Type"].encode()
    assert b'name="files"; filename="cay.jpg"' in body
    assert b"\xff\xd8\x00binary\xff\xd9" in body, "byte ảnh bị đổi trên đường đi"
    assert b'name="lat"' in body and b"10.5" in body


def test_empty_form_fields_are_left_out_not_sent_as_the_word_none(server):
    """Gửi chuỗi 'None' vào một trường toạ độ là dựng dữ liệu rác ở đầu bên kia."""
    SCRIPT.append((200, {"ok": True}, {}))
    Client(server, token="t").identify_auto([("a.jpg", b"x")])
    assert b"None" not in SEEN[0]["body"]
    assert b'name="lat"' not in SEEN[0]["body"]


def test_a_rate_limit_is_waited_out_for_exactly_as_long_as_asked(server):
    SCRIPT.append((429, {"ok": False, "error": "Máy đang bận"}, {"Retry-After": "1"}))
    SCRIPT.append((200, {"ok": True}, {}))
    t0 = time.monotonic()
    out = Client(server, token="t").health()
    waited = time.monotonic() - t0
    assert out["ok"] is True
    assert waited >= 1.0, f"chỉ chờ {waited:.2f}s — không đọc header Retry-After"


def test_a_rate_limit_that_never_clears_surfaces_as_a_typed_error(server):
    for _ in range(5):
        SCRIPT.append((429, {"ok": False, "error": "Máy đang bận"}, {"Retry-After": "0.01"}))
    with pytest.raises(errors.RateLimitedError) as e:
        Client(server, token="t", max_retries=1).health()
    assert e.value.retry_after == 0.01


def test_a_read_that_fails_on_the_server_is_retried(server):
    SCRIPT.append((500, {"ok": False, "error": "hỏng"}, {}))
    SCRIPT.append((200, {"ok": True}, {}))
    assert Client(server, token="t").health()["ok"] is True
    assert len(SEEN) == 2


def test_a_write_that_fails_is_never_retried_by_itself(server):
    """Cửa GHI gửi lại sau khi hỏng có thể tạo bản ghi thứ hai. Người gọi phải tự quyết."""
    SCRIPT.append((500, {"ok": False, "error": "hỏng"}, {}))
    SCRIPT.append((200, {"ok": True}, {}))
    with pytest.raises(errors.ServerError):
        Client(server, token="t").enroll_tree([("a.jpg", b"x")], name="cây 1")
    assert len(SEEN) == 1, "đã tự gửi lại một cửa GHI"


@pytest.mark.parametrize("status,kind", [
    (400, errors.InvalidRequestError),
    (401, errors.AuthError),
    (403, errors.PermissionError_),
    (404, errors.NotFoundError),
    (413, errors.TooLargeError),
    (422, errors.InvalidRequestError),
    (500, errors.ServerError),
])
def test_each_status_becomes_its_own_kind_of_error(server, status, kind):
    SCRIPT.append((status, {"ok": False, "error": "câu cho người dùng"}, {}))
    with pytest.raises(kind) as e:
        Client(server, token="t", max_retries=0).resolve("ORI-0000000-AAAAAAAA")
    assert e.value.message == "câu cho người dùng"
    assert e.value.status == status


def test_the_message_shown_to_a_person_never_comes_from_the_validation_shape(server):
    """`detail` là khuôn của tầng kiểm tham số — hiện nó lên màn hình là đổ chuỗi kỹ thuật vào
    mắt nông dân."""
    SCRIPT.append((422, {"detail": [{"loc": ["body", "files"], "msg": "field required"}]}, {}))
    with pytest.raises(errors.InvalidRequestError) as e:
        Client(server, token="t", max_retries=0).lookup_fruit(("a.jpg", b"x"))
    assert "loc" not in e.value.message
    assert e.value.payload["detail"], "vẫn phải giữ nguyên thân gốc cho người gỡ lỗi"


def test_an_unreachable_server_is_a_network_error_not_a_server_error(server):
    """Hai ca khác nhau: một ca yêu cầu CHƯA tới nơi, ca kia đã tới rồi."""
    with pytest.raises(errors.NetworkError):
        Client("http://127.0.0.1:1", timeout=1.0, max_retries=0).health()


def test_unknown_response_fields_are_handed_through_untouched(server):
    """Bộ này không diễn giải nội tạng so khớp. Trường lạ đi thẳng cho ứng dụng, không bị cắt."""
    SCRIPT.append((200, {"ok": True, "decision": "MATCH", "confidence": "cao",
                         "truong_moi_cua_may_chu": 42}, {}))
    out = Client(server, token="t").identify_tree([("a.jpg", b"x")])
    assert out["truong_moi_cua_may_chu"] == 42
