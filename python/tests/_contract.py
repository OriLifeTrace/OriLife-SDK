"""Đường tới `contract/` — MỘT nơi giữ, mọi bộ kiểm trỏ về đây.

Trước đây bộ kiểm JavaScript đọc `../../python/tests/vectors.json`: gói JavaScript thò tay vào
ruột gói Python. Xuất bản riêng một gói là đứt đường đó, mà không lệnh nào báo. Nay cả hai bên
cùng trỏ vào `contract/`, không bên nào sở hữu dữ liệu của bên kia.
"""
from __future__ import annotations

import json
import os

CONTRACT_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "contract"))


def load(name: str):
    """Đọc một tệp trong `contract/`. Thiếu tệp thì NÉM — đừng trả rỗng rồi chạy tiếp,
    bộ kiểm 0 ca vẫn xanh và ai đọc cũng tưởng là đã kiểm."""
    with open(os.path.join(CONTRACT_DIR, name), encoding="utf-8") as fh:
        return json.load(fh)
