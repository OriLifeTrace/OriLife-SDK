"""Lỗi có KIỂU — để ứng dụng phân biệt được ba thứ mà một chuỗi lỗi trộn làm một.

Ba thứ đó là: lỗi do người dùng (ảnh mờ, mật khẩu yếu), lỗi do ứng dụng (hết hạn khoá, gọi sai
cửa), và lỗi do phía kia (máy chủ bận, mạng đứt). Ứng dụng phải xử ba thứ này theo ba cách khác
hẳn nhau — hiện câu hướng dẫn, đăng nhập lại, hoặc chờ rồi thử lại — nên gộp chúng vào một
`Exception` chung là đẩy việc phân loại sang cho người viết ứng dụng, mỗi người tự đoán một kiểu.

Mọi lỗi ở đây đều mang `message`: câu tiếng Việt máy chủ đã viết sẵn cho người dùng đọc. Hiện
thẳng câu đó, đừng tự dịch mã lỗi thành câu của mình — máy chủ biết ngữ cảnh còn ứng dụng thì không.
"""
from __future__ import annotations

from typing import Any, Optional

__all__ = [
    "OriLifeError", "NetworkError", "AuthError", "PermissionError_",
    "NotFoundError", "TooLargeError", "InvalidRequestError", "RateLimitedError",
    "ServerError", "from_response",
]


class OriLifeError(Exception):
    """Gốc của mọi lỗi bộ này ném ra. Bắt cái này là bắt hết."""

    def __init__(self, message: str, *, status: Optional[int] = None,
                 payload: Any = None, path: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.payload = payload
        self.path = path

    def __str__(self) -> str:                     # noqa: D105 — câu cho người đọc, không cho máy
        head = f"[{self.status}] " if self.status else ""
        return f"{head}{self.message}"


class NetworkError(OriLifeError):
    """Không nói chuyện được với máy chủ: mất mạng, quá hạn chờ, tên miền không tra được.

    KHÁC hẳn `ServerError`. Ở đây yêu cầu có thể CHƯA từng tới nơi, nên với một cửa GHI (đăng ký
    cây, ghi nhật ký) thì thử lại là có thể tạo bản ghi thứ hai. Cửa ĐỌC thì thử lại thoải mái.
    """


class AuthError(OriLifeError):
    """401 — chưa đăng nhập, hoặc khoá đã hết hạn. Xin khoá mới rồi gọi lại."""


class PermissionError_(OriLifeError):
    """403 — đã đăng nhập nhưng không có quyền với thứ đang đụng tới. Xin khoá mới KHÔNG giúp."""


class NotFoundError(OriLifeError):
    """404 — không có thứ đó.

    Cẩn thận khi suy diễn: nhiều cửa cố ý trả 404 cho cả "không tồn tại" lẫn "của người khác", để
    người lạ dò mã không đếm được vườn người ta. Đừng viết "cây này không tồn tại" lên màn hình.
    """


class TooLargeError(OriLifeError):
    """413 — vượt trần dung lượng. Nén ảnh nhỏ lại rồi gửi lại, đừng thử lại nguyên trạng."""


class InvalidRequestError(OriLifeError):
    """400 hoặc 422 — thiếu trường, sai kiểu, hoặc không đạt luật (mật khẩu yếu, tên sai khuôn)."""


class RateLimitedError(OriLifeError):
    """429 — gọi quá dày.

    `retry_after` là số giây máy chủ bảo chờ. CHỜ ĐÚNG bấy nhiêu rồi hãy gọi lại; thử lại ngay là
    thứ mã 429 dựng ra để ngăn, và làm vậy chỉ kéo dài thời gian bị chặn.
    """

    def __init__(self, message: str, *, retry_after: float = 1.0, **kw):
        super().__init__(message, **kw)
        self.retry_after = retry_after


class ServerError(OriLifeError):
    """5xx — yêu cầu tới nơi rồi và phía kia hỏng. Thử lại được, nên giãn dần khoảng cách."""


_BY_STATUS = {
    400: InvalidRequestError,
    401: AuthError,
    403: PermissionError_,
    404: NotFoundError,
    413: TooLargeError,
    422: InvalidRequestError,
    429: RateLimitedError,
}


def _message_of(payload: Any, fallback: str) -> str:
    """Câu cho người dùng, theo đúng thứ tự ưu tiên mà máy chủ dùng.

    Máy chủ đặt câu dễ đọc ở `error` hoặc `message`; `detail` là khuôn của tầng kiểm tham số nên
    nó thường là một cấu trúc, không phải câu. Lấy `detail` làm câu hiện lên màn hình là cách
    nhanh nhất để một chuỗi kỹ thuật rơi vào mắt nông dân.
    """
    if isinstance(payload, dict):
        for key in ("error", "message"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        detail = payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
    return fallback


def from_response(status: int, payload: Any, *, path: str = "", headers: Any = None):
    """Dựng đúng lớp lỗi từ một phản hồi. Trả về ngoại lệ, người gọi tự `raise`."""
    message = _message_of(payload, f"Máy chủ trả về mã {status}.")
    cls = _BY_STATUS.get(status) or (ServerError if status >= 500 else OriLifeError)
    if cls is RateLimitedError:
        after = None
        if headers is not None:
            raw = headers.get("Retry-After") if hasattr(headers, "get") else None
            try:
                after = float(raw) if raw is not None else None
            except (TypeError, ValueError):
                after = None
        if after is None and isinstance(payload, dict):
            try:
                after = float(payload.get("retry_after"))
            except (TypeError, ValueError):
                after = None
        return RateLimitedError(message, retry_after=(after if after and after > 0 else 1.0),
                                status=status, payload=payload, path=path)
    return cls(message, status=status, payload=payload, path=path)
