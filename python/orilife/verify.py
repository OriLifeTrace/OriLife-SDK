"""Kiểm chứng ĐỘC LẬP — chạy được mà không cần tin OriLife, không cần mạng, không cần mô hình.

Đây là phần quan trọng nhất của cả bộ này, và cũng là phần nhỏ nhất.

Một hệ truy xuất nguồn gốc chỉ đáng tin ở mức người ngoài kiểm được nó. Nếu cách duy nhất để biết
một bản ghi có thật là hỏi chính máy chủ đã tạo ra nó thì hệ đó không chứng minh gì hết — nó chỉ
đang lặp lại lời khai của chính mình. Tệp này là đường thoát khỏi vòng lặp đó: đưa vào một bản ghi
JSON tải từ bất kỳ đâu và một mã băm đọc từ trình duyệt khối Cardano, hàm ở đây nói bản ghi có
đúng là thứ đã băm ra con số kia không.

Chỉ dùng thư viện chuẩn Python. Không mạng, không phụ thuộc, không trạng thái. Đọc hết tệp này
trong mười phút là kiểm được toàn bộ phép toán — đó là chủ ý, vì một bộ kiểm chứng mà người ta
phải tin thì vô nghĩa.

Ba phép, và ranh giới giữa chúng phải nói rõ vì trộn hai phép đầu là lỗi hay gặp nhất:

  entity_code()      sinh MÃ người đọc được từ định danh nội bộ + toạ độ thô. Dùng blake2b.
  record_hash()      băm BẢN GHI để neo lên chuỗi. Dùng thuật toán mà chính bản ghi khai.
  verify_record()    kiểm một bản ghi có khớp mã băm đã neo không.

Hai hàm đầu dùng hai hàm băm KHÁC NHAU và đó không phải nhầm lẫn. Mã đã in ra QR, đã nằm trong
siêu dữ liệu của mọi lần neo cũ, nên nó không được đổi bao giờ; còn thuật toán băm bản ghi thì có
đường nâng cấp (xem `record_algorithm`). Ai "đồng bộ" hai chỗ này về một hàm băm là làm hỏng toàn
bộ mã đã phát ra ngoài đời.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Optional, Sequence

__all__ = [
    "geohash", "entity_code", "canonical_json", "hash_bytes", "sha256_of",
    "record_algorithm", "record_hash", "verify_record", "verify_content_id",
    "missing_fields", "summarize",
    "RECORD_VERSION", "HASH_ALGORITHM", "HASH_ALGORITHM_LEGACY",
]

_GEOHASH_ALPHABET = "0123456789bcdefghjkmnpqrstuvwxyz"
# Crockford base32: bỏ I, L, O, U để người đọc mã bằng mắt không nhầm với 1 và 0.
_CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

RECORD_VERSION = 2
HASH_ALGORITHM = "sha3-256"          # bản ghi sinh từ 2026-08 trở đi
HASH_ALGORITHM_LEGACY = "blake2b-256"  # bản ghi v=1, trước 2026-08, không tự khai

# Bảng thuật toán ĐƯỢC PHÉP. Thêm dòng ở đây là cách duy nhất để bộ kiểm chấp nhận một thuật toán
# mới. Thuật toán ngoài bảng trả về sai, KHÔNG âm thầm rơi về mặc định — rơi về mặc định là mở
# đúng cánh cửa mà việc tự khai thuật toán dựng ra để đóng.
_HASHERS = {
    "sha3-256": lambda b: hashlib.sha3_256(b).hexdigest(),
    "blake2b-256": lambda b: hashlib.blake2b(b, digest_size=32).hexdigest(),
}


def geohash(lat: float, lon: float, precision: int = 7) -> str:
    """Geohash chuẩn (thuật toán Niemeyer). Bảy ký tự ≈ ô 150 m — đủ để nói "vùng nào", không đủ
    để chỉ đúng một gốc cây. Đó là lý do mã công khai chỉ mang bảy ký tự."""
    lat_range = [-90.0, 90.0]
    lon_range = [-180.0, 180.0]
    out: list = []
    bit = 0
    acc = 0
    even = True
    while len(out) < precision:
        if even:
            mid = (lon_range[0] + lon_range[1]) / 2
            if lon > mid:
                acc |= 1 << (4 - bit)
                lon_range[0] = mid
            else:
                lon_range[1] = mid
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if lat > mid:
                acc |= 1 << (4 - bit)
                lat_range[0] = mid
            else:
                lat_range[1] = mid
        even = not even
        if bit < 4:
            bit += 1
        else:
            out.append(_GEOHASH_ALPHABET[acc])
            bit = 0
            acc = 0
    return "".join(out)


def _crockford(data: bytes, n_chars: int) -> str:
    number = int.from_bytes(data, "big")
    total_bits = len(data) * 8
    chars = []
    for i in range(n_chars):
        shift = total_bits - 5 * (i + 1)
        if shift < 0:
            index = (number << (-shift)) & 0x1F
        else:
            index = (number >> shift) & 0x1F
        chars.append(_CROCKFORD_ALPHABET[index])
    return "".join(chars)


def entity_code(entity_id: str, gps: Optional[Sequence[float]] = None) -> str:
    """Mã công khai ổn định của một cá thể: `ORI-<geohash7>-<8 ký tự>`.

    Ổn định theo định danh nội bộ và vị trí thô, nên cùng cá thể luôn ra cùng mã. Không có toạ độ
    thì phần giữa là bảy số không — mã vẫn dùng được, chỉ mất phần gợi vùng.

    Dùng để ĐỐI CHIẾU: cầm mã in trên phiếu, gọi hàm này với định danh mà máy chủ trả về, hai bên
    phải ra cùng một chuỗi. Lệch nghĩa là một trong hai đầu đã đổi.
    """
    digest = hashlib.blake2b(entity_id.encode("utf-8"), digest_size=8).digest()
    suffix = _crockford(digest, 8)
    if gps and len(gps) == 2 and gps[0] is not None and gps[1] is not None:
        cell = geohash(float(gps[0]), float(gps[1]), 7)
    else:
        cell = "0000000"
    return f"ORI-{cell}-{suffix}"


def canonical_json(record: dict) -> bytes:
    """Tuần tự hoá TẤT ĐỊNH: khoá sắp xếp, không khoảng trắng thừa, giữ nguyên chữ ngoài ASCII.

    Ba lựa chọn đó đều bắt buộc và đều đã có chỗ vấp thật ở các hệ khác: thứ tự khoá khác nhau,
    một dấu cách sau dấu hai chấm, hay một chữ tiếng Việt bị chuyển thành `\\uXXXX` — mỗi thứ đều
    đủ để mã băm lệch trong khi nội dung y hệt. Bản ghi không khớp mã băm thì người kiểm kết luận
    là bị sửa, chứ không kết luận là do khác cách tuần tự hoá.
    """
    return json.dumps(record, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def hash_bytes(data: bytes, algorithm: str = HASH_ALGORITHM) -> str:
    """Băm `data`. Thuật toán ngoài bảng cho phép → ValueError, không rơi về mặc định."""
    fn = _HASHERS.get((algorithm or "").strip().lower())
    if fn is None:
        raise ValueError(f"thuật toán băm không hỗ trợ: {algorithm!r} (có: {sorted(_HASHERS)})")
    return fn(data)


def record_algorithm(record: dict) -> str:
    """Thuật toán băm CỦA CHÍNH BẢN GHI NÀY — đọc từ bản ghi, không đoán theo thời điểm.

    Bản ghi từ v2 tự khai ở khoá `hash_alg`. Bản ghi cũ không có khoá đó: `v<=1` nghĩa là blake2b.
    Thiếu cả `v` cũng coi là v=1 — bản ghi càng cũ càng thiếu trường, nên mặc định phải nghiêng về
    phía cũ thì lịch sử mới kiểm được.
    """
    declared = str(record.get("hash_alg") or "").strip().lower()
    if declared:
        return declared
    try:
        version = int(record.get("v") or 1)
    except (TypeError, ValueError):
        version = 1
    return HASH_ALGORITHM_LEGACY if version <= 1 else HASH_ALGORITHM


def record_hash(record: dict) -> str:
    """Băm bản ghi bằng thuật toán HIỆN HÀNH. Dùng khi tự dựng bản ghi mới.

    Muốn KIỂM một bản ghi đã có thì gọi `verify_record`, đừng so tay với hàm này: bản ghi cũ băm
    bằng blake2b nên so với sha3 sẽ lệch, và lệch đó đọc thành "bị sửa".
    """
    return hash_bytes(canonical_json(record), HASH_ALGORITHM)


def verify_record(record: dict, expected_hash: str) -> bool:
    """Bản ghi này có đúng là thứ đã băm ra `expected_hash` không?

    Đây là hàm dành cho người kiểm chứng. Đưa vào JSON bản ghi lấy từ kho lưu trữ và con số đọc
    trên trình duyệt khối, nhận về True hoặc False. Tự chọn thuật toán theo chính bản ghi, nên
    người kiểm KHÔNG cần biết bản ghi thuộc thời nào.

    Không có đường hạ cấp: khoá `hash_alg` nằm TRONG phần được băm, nên sửa nó để ép dùng thuật
    toán yếu hơn là đã đổi luôn nội dung, và mã băm không còn khớp.
    """
    if not isinstance(record, dict) or not expected_hash or not isinstance(expected_hash, str):
        return False
    try:
        got = hash_bytes(canonical_json(record), record_algorithm(record))
    except ValueError:
        return False
    return got == expected_hash.strip().lower()


def verify_content_id(data: bytes, content_id: str) -> bool:
    """Byte tải về có đúng là byte mà địa chỉ nội dung này trỏ tới không?

    Kho lưu trữ của OriLife đánh địa chỉ theo nội dung: định danh của một tệp sinh ra từ chính
    byte của tệp đó. Nghĩa là người kiểm không phải tin kho — tải byte về, băm lại, so với địa chỉ.

    ⚠️ Hàm này KHÔNG tự dựng lại địa chỉ. Nó cần một trường `sha256` đi kèm bản ghi để đối chiếu;
    định dạng địa chỉ nội dung có nhiều phiên bản và đoán nhầm phiên bản sẽ trả về "sai" cho một
    tệp hoàn toàn đúng — báo động giả trong một bộ kiểm chứng còn tệ hơn không kiểm, vì nó dạy
    người dùng bỏ qua cảnh báo. Dùng `sha256_of()` rồi tự so với trường `sha256` trong bản ghi.
    """
    raise NotImplementedError(
        "Địa chỉ nội dung có nhiều phiên bản định dạng — dùng sha256_of(data) rồi so với trường "
        "`images[i].sha256` trong bản ghi. Xem VERIFY.md."
    )


def sha256_of(data: bytes) -> str:
    """SHA-256 của một khối byte, dạng chữ thường — để so với trường `sha256` trong bản ghi."""
    return hashlib.sha256(data).hexdigest()


def missing_fields(record: dict, required: Iterable[str] = ()) -> list:
    """Trường bắt buộc nào vắng mặt. Mặc định kiểm bộ tối thiểu của một bản ghi cá thể.

    Có mặt để một bộ kiểm tự động phân biệt được hai ca rất khác nhau: bản ghi ĐỦ mà mã băm lệch
    (nghi bị sửa) với bản ghi THIẾU trường (nhiều khả năng tải hụt hoặc lấy nhầm mảnh).
    """
    required = tuple(required) or ("v", "code", "gps", "enrolled_at", "images")
    return [k for k in required if k not in record]


def summarize(record: dict, expected_hash: Optional[str] = None) -> dict:
    """Một dòng tóm tắt cho công cụ dòng lệnh và cho tác tử: bản ghi này nói gì, có khớp không."""
    images: Any = record.get("images") or []
    return {
        "code": record.get("code"),
        "version": record.get("v"),
        "algorithm": record_algorithm(record),
        "enrolled_at": record.get("enrolled_at"),
        "n_images": len(images) if isinstance(images, (list, tuple)) else 0,
        "has_3d": bool(record.get("model3d")),
        "missing_fields": missing_fields(record),
        "hash_matches": (verify_record(record, expected_hash)
                         if expected_hash else None),
    }
