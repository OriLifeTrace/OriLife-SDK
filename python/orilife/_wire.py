"""Cách dựng thân yêu cầu — dùng chung cho mọi cửa, và phải KHỚP TỪNG BYTE với bản JavaScript.

Tệp này là bản Python của `javascript/src/wire.js`. Hai tệp cố ý viết cùng một phép biến đổi, và
`contract/conformance.json` là thứ giữ chúng bằng nhau: mỗi ca trong đó khai đúng cái đi lên dây,
rồi cả hai ngôn ngữ chạy lại đúng danh sách ca ấy.

Cái đã sai trước khi có tệp này (đo 2026-09-08, trên bản `origin/main`):

  • `create_farm(lat=10.762, lon=106.66)` gửi `center_json=[10.762, 106.66]` ở Python và
    `[10.762,106.66]` ở JavaScript. Khác một dấu cách là khác byte; cửa nào băm thân yêu cầu để
    chống-trùng sẽ đọc hai lượt gửi giống hệt nhau thành hai lượt khác nhau.
  • `update_farm(boundary_json=[[10.7, 106.6]])` mã hoá JSON ở Python, còn ở JavaScript thì
    `URLSearchParams` gọi `String([[10.7,106.6]])` và gửi lên `10.7,106.6` — máy chủ nhận một
    chuỗi không phải JSON, và không bên nào báo lỗi.
  • `identify_tree("photo.jpg")` ở Python duyệt CHUỖI thành từng ký tự rồi tải lên 9 tệp một ký
    tự. Không hàm nào ném, máy chủ nhận đủ 9 tệp rác.

Cả ba đều là lỗi im lặng: không có ngoại lệ, không có mã lỗi, chỉ có dữ liệu sai ở đầu kia.
"""
from __future__ import annotations

import json
import mimetypes
import os
import urllib.parse
import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

__all__ = [
    "FileArg", "_as_file", "_as_file_list", "_one_file", "_bbox_fields", "_center_json",
    "_encode_containers", "_multipart", "_quote",
]

FileArg = Union[str, bytes, Tuple[str, bytes], Tuple[str, bytes, str]]


def _quote(value: Any) -> str:
    """Một đoạn đường dẫn, đã thoát. `safe=''` để dấu `/` trong định danh không cắt đường dẫn."""
    return urllib.parse.quote(str(value), safe="")


def _as_file(item: FileArg) -> Tuple[str, bytes, str]:
    """Nhận đường dẫn, khối byte, hoặc bộ; trả về (tên tệp, byte, kiểu nội dung)."""
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
    raise TypeError("a file must be a path, bytes, (name, bytes) or (name, bytes, content type)")


def _as_file_list(images: Union[FileArg, Iterable[FileArg]]) -> List[FileArg]:
    """Gom "một ảnh hoặc nhiều ảnh" về một danh sách.

    Một đường dẫn là `str`, mà `str` thì duyệt được — nên coi tham số là dãy mà không có hàng rào
    này sẽ biến "photo.jpg" thành chín tệp một ký tự. Chặn ngay ở đây thay vì tải rác lên.
    """
    if isinstance(images, (str, bytes, tuple)):
        return [images]
    return list(images)


def _one_file(images: Union[FileArg, Iterable[FileArg]], message: str) -> FileArg:
    """Đúng MỘT ảnh cho cửa chỉ nhận một ảnh — thừa thì ném, đừng lặng lẽ bỏ bớt."""
    items = _as_file_list(images)
    if len(items) != 1:
        raise ValueError(message)
    return items[0]


def _bbox_fields(bbox: Any) -> Dict[str, Any]:
    """Khung bao thành bốn trường biểu mẫu máy chủ chờ.

    Nhận `(x, y, w, h)` hoặc `{"x":…, "y":…, "w":…, "h":…}`. Thứ khác thì ném: một khung bị bỏ qua
    trong im lặng nghĩa là quả được ghi từ CẢ khung hình thay vì từ quả — một bản ghi sai, tệ hơn
    một lỗi nhìn thấy được.
    """
    if bbox is None:
        return {}
    if isinstance(bbox, dict):
        try:
            x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
        except KeyError as e:
            raise ValueError(f"bbox dict is missing key {e}; expected x, y, w, h") from None
    else:
        box = list(bbox)
        if len(box) != 4:
            raise ValueError("bbox must hold exactly four numbers: (x, y, w, h)")
        x, y, w, h = box
    return {"bbox_x": x, "bbox_y": y, "bbox_w": w, "bbox_h": h}


def _compact_json(value: Any) -> str:
    """JSON KHÔNG dấu cách thừa — đúng thứ `JSON.stringify` bên JavaScript sinh ra.

    `json.dumps` mặc định chèn một dấu cách sau dấu phẩy; JavaScript thì không. Cùng một lệnh gọi
    ở hai ngôn ngữ ra hai chuỗi khác nhau, và không bên nào tự biết.
    """
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _center_json(lat: Any, lon: Any) -> Optional[str]:
    """Tâm vườn: đủ CẢ hai nửa mới gửi. Nửa toạ-độ không phải một chỗ nào cả."""
    if lat is None or lon is None:
        return None
    return _compact_json([lat, lon])


def _encode_containers(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Trường tự do: mảng và ánh xạ mã hoá JSON, còn lại giữ nguyên; `None` bị loại.

    `boundary_json=[[lat, lon], …]` phải tới máy chủ dưới dạng CHUỖI JSON. Để nguyên rồi phó mặc
    tầng dựng biểu mẫu thì mỗi ngôn ngữ ép chuỗi một kiểu.
    """
    return {k: (_compact_json(v) if isinstance(v, (list, dict, tuple)) else v)
            for k, v in fields.items() if v is not None}


def _multipart(fields: Dict[str, Any],
               files: Sequence[Tuple[str, FileArg]]) -> Tuple[bytes, str]:
    """Dựng thân multipart bằng tay.

    Viết ở đây thay vì dùng `email.mime` vì mô-đun đó ngắt dòng theo lối thư điện tử, mà thừa một
    byte trong thân nhị phân là một tấm ảnh hỏng ở đầu kia.
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
