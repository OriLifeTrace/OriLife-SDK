"""Chạy bộ ca DÙNG CHUNG `contract/conformance.json` trên bản cài Python.

Bộ kiểm riêng của mỗi ngôn ngữ chỉ chứng minh bên đó tự nhất quán với chính nó. Hai bên tự nhất
quán mà lệch nhau thì vẫn xanh cả hai — đó đúng là chỗ ba lỗi thật đã đi qua (xem đầu tệp
`orilife/_wire.py`). Tệp này và bản song sinh `javascript/test/conformance.test.mjs` chạy CÙNG một
danh sách ca, nên một bên lệch là một bên đỏ.

Ranh giới đo: chốt ở chỗ hàm gọi ra `request()` — phần ÁNH XẠ (đường, tên trường, cách mã hoá).
Tầng vận chuyển bên dưới (dựng multipart, chờ 429, phân loại lỗi) do `test_client.py` giữ. Xanh ở
đây KHÔNG có nghĩa là đã kiểm hết.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _contract import load  # noqa: E402
from orilife import Client  # noqa: E402

CONTRACT = load("methods.json")
CASES = load("conformance.json")["cases"]
SPEC = {m["name"]: m for m in CONTRACT["methods"]}
GENERATED = [m["name"] for m in CONTRACT["methods"] if m.get("generated", True)]

# Cùng một khối byte cho mọi tệp giả — nội dung không phải thứ đang đo, tên trường mới là.
_BLOB = b"\x01\x02\x03"


class _Recorder(Client):
    """Client thật, chỉ thay tầng vận chuyển bằng một cuốn sổ."""

    def __init__(self):
        super().__init__("https://x.test", token="k", max_retries=0)
        self.seen = None

    def request(self, method, path, *, params=None, fields=None, files=None,
                json_body=None, timeout=None):
        self.seen = {
            "verb": method,
            "path": path,
            "query": _clean(params),
            "fields": _clean(fields),
            "files": [[key, _filename(item)] for key, item in (files or [])],
            "json": json_body,
            "timeout": timeout,
        }
        return {"ok": True, "token": "tok"}


def _clean(mapping):
    """Đúng cái đi lên dây: bỏ giá trị rỗng, ép chuỗi phần còn lại."""
    return {k: str(v) for k, v in (mapping or {}).items() if v is not None}


def _filename(item):
    """Tên tệp đọc ra từ thứ đã đưa vào — bộ `(tên, byte)` hoặc chuỗi đường dẫn."""
    return item[0] if isinstance(item, tuple) else item


def _materialise(value):
    """Chỗ giữ tệp trong ca kiểm thành một tệp thật của ngôn ngữ này.

    `$single_file` cố ý dựng thành CHUỖI đường dẫn trần, vì đó vừa là lối tự nhiên nhất để đưa
    một tệp lẻ vào bản Python, vừa là đúng cái đầu vào làm lộ lỗi duyệt-chuỗi-thành-ký-tự. Dựng
    nó thành bộ như `$file` thì ca này xanh dưới chính đột biến nó mang tên — đo được ngày
    2026-09-08: gỡ hàng rào chuỗi trong `_as_file_list` mà 57/57 ca vẫn xanh.
    """
    if isinstance(value, dict) and "$file" in value:
        return (value["$file"], _BLOB)
    if isinstance(value, dict) and "$single_file" in value:
        return value["$single_file"]
    if isinstance(value, list):
        return [_materialise(v) for v in value]
    return value


def _invoke(client, case):
    """Dựng lệnh gọi từ đặc tả tham số trong hợp đồng, không đoán theo tên ca."""
    spec = SPEC[case["method"]]
    args = {k: _materialise(v) for k, v in case["args"].items()}
    positional = [a for a in spec.get("args", []) if a.get("positional")]
    optional = [a for a in spec.get("args", []) if not a.get("positional")]

    call_args = []
    for arg in positional:
        if arg["name"] in args:
            call_args.append(args[arg["name"]])
        elif arg["kind"] == "json_payload":
            call_args.append(None)
        else:
            raise AssertionError(
                f"ca {case['name']!r} thiếu tham số bắt buộc {arg['name']!r}")

    call_kwargs = {}
    for arg in optional:
        if arg["kind"] == "varfields":
            call_kwargs.update(args.get(arg["name"]) or {})
        elif arg["name"] in args:
            call_kwargs[arg["name"]] = args[arg["name"]]

    return getattr(client, case["method"])(*call_args, **call_kwargs)


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_the_wire_shape_is_the_one_the_contract_declares(case):
    client = _Recorder()

    if case.get("throws"):
        with pytest.raises((ValueError, TypeError)):
            _invoke(client, case)
        # Ném là chưa đủ: nó phải ném TRƯỚC khi có byte nào rời máy. Ném sau khi đã tải ảnh lên
        # trên đường truyền yếu là cả phút chờ để nhận một lỗi lẽ ra biết trước.
        assert client.seen is None, "phải chặn trước khi gửi, không phải sau"
        return

    _invoke(client, case)
    seen = client.seen
    assert seen is not None, "hàm không gọi ra request() lần nào"

    want = case["expect"]
    assert seen["verb"] == want["verb"]
    assert seen["path"] == want["path"]
    if "query" in want:
        assert seen["query"] == want["query"]
    if "fields" in want:
        assert seen["fields"] == want["fields"]
    if "files" in want:
        assert seen["files"] == [list(f) for f in want["files"]]
    if "json" in want:
        assert seen["json"] == want["json"]
    if "timeout_seconds_at_least" in want:
        assert seen["timeout"] is not None
        assert seen["timeout"] >= want["timeout_seconds_at_least"]

    for key, value in (case.get("after") or {}).items():
        assert getattr(client, key) == value


def test_every_generated_method_has_at_least_one_case():
    """Một cửa không có ca nào là một cửa không ai canh.

    Cổng này ở đây chứ không ở bộ sinh: bộ sinh mà tự chấm điểm cho mình thì nó vừa ra đề vừa
    chấm bài.
    """
    covered = {c["method"] for c in CASES}
    missing = sorted(set(GENERATED) - covered)
    assert not missing, f"chưa có ca kiểm dùng chung cho: {missing}"


def test_every_case_names_a_method_that_exists():
    unknown = sorted({c["method"] for c in CASES} - set(SPEC))
    assert not unknown, f"ca kiểm gọi cửa không có trong hợp đồng: {unknown}"
