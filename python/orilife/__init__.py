"""Bộ công cụ OriLife — định danh cá thể bằng chính ảnh chụp nó.

Hai nửa, cố ý tách rời:

    from orilife import Client       # gọi API: định danh, đăng ký, đọc dòng thời gian
    from orilife import verify       # kiểm chứng ĐỘC LẬP: không mạng, không phụ thuộc

Nửa thứ hai là nửa quan trọng. `Client` chỉ hỏi máy chủ và chép lại câu trả lời — dùng nó thì bạn
đang tin OriLife. `verify` tính lại mã băm từ chính bản ghi, nên nó kiểm được lời khai của OriLife
mà không cần OriLife có mặt. Một hệ truy xuất nguồn gốc chỉ đáng tin ở mức người ngoài kiểm được
nó, nên nửa kiểm chứng không phụ thuộc bất cứ thứ gì ngoài thư viện chuẩn.
"""
from . import verify
from .client import DEFAULT_BASE_URL, Client
from .errors import (
    AuthError,
    InvalidRequestError,
    NetworkError,
    NotFoundError,
    OriLifeError,
    RateLimitedError,
    ServerError,
    TooLargeError,
)

__version__ = "1.0.0"

__all__ = [
    "Client", "DEFAULT_BASE_URL", "verify", "__version__",
    "OriLifeError", "NetworkError", "AuthError", "NotFoundError",
    "TooLargeError", "InvalidRequestError", "RateLimitedError", "ServerError",
]
