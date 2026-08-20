"""Bộ kiểm chứng phải cho ra ĐÚNG những con số mà máy sản xuất đã tạo — không xấp xỉ, không "gần".

`vectors.json` sinh ra từ chính mã đang chạy trên máy chủ OriLife. Nếu một ngày bộ kiểm ở đây lệch
khỏi những con số đó thì mọi bản ghi đã neo lên chuỗi sẽ đọc thành "bị sửa" trong khi không ai sửa
gì — một bộ kiểm chứng báo động giả còn tệ hơn không có, vì nó dạy người dùng bỏ qua cảnh báo.

Chạy được ngoại tuyến. Không mạng, không phụ thuộc, không cần máy chủ.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from orilife import verify  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "vectors.json"), encoding="utf-8") as fh:
    V = json.load(fh)


def test_codes_match_the_production_generator():
    for case in V["codes"]:
        got = verify.entity_code(case["entity_id"], case["gps"])
        assert got == case["code"], f"{case['entity_id']}: {got} ≠ {case['code']}"


def test_a_code_without_coordinates_still_has_a_shape():
    code = verify.entity_code("khong-toa-do", None)
    assert code.startswith("ORI-0000000-")
    assert len(code) == len("ORI-") + 7 + 1 + 8


def test_the_same_entity_always_gets_the_same_code():
    a = verify.entity_code("cay-so-47", [11.5449, 107.4123])
    b = verify.entity_code("cay-so-47", [11.5449, 107.4123])
    assert a == b


def test_canonical_json_is_byte_stable_across_key_order():
    """Bản ghi cùng nội dung nhưng khoá nhập vào theo thứ tự khác phải ra cùng byte."""
    record = V["record"]
    shuffled = dict(reversed(list(record.items())))
    assert verify.canonical_json(record) == verify.canonical_json(shuffled)


def test_canonical_json_keeps_vietnamese_letters_as_themselves():
    """Chuyển chữ có dấu thành `\\uXXXX` là đổi byte, và đổi byte là đổi mã băm."""
    raw = verify.canonical_json({"name": "cây sầu riêng"})
    assert "cây sầu riêng".encode("utf-8") in raw
    assert b"\\u" not in raw


def test_record_hash_matches_production():
    assert verify.record_hash(V["record"]) == V["record_hash_sha3_256"]


def test_verify_accepts_the_real_record_and_hash():
    assert verify.verify_record(V["record"], V["record_hash_sha3_256"]) is True


def test_verify_still_reads_the_old_records():
    """110 bản ghi neo trước 2026-08 dùng thuật toán cũ và KHÔNG được băm lại. Chúng phải kiểm được."""
    assert verify.record_algorithm(V["record_v1"]) == verify.HASH_ALGORITHM_LEGACY
    assert verify.verify_record(V["record_v1"], V["record_v1_hash_blake2b_256"]) is True


def test_one_changed_character_breaks_the_hash():
    tampered = dict(V["record"], name=str(V["record"].get("name", "")) + " ")
    assert verify.verify_record(tampered, V["record_hash_sha3_256"]) is False


def test_downgrading_the_declared_algorithm_does_not_help_an_attacker():
    """`hash_alg` nằm TRONG phần được băm, nên sửa nó là đổi luôn nội dung."""
    weakened = dict(V["record"], hash_alg=verify.HASH_ALGORITHM_LEGACY)
    assert verify.verify_record(weakened, V["record_hash_sha3_256"]) is False


def test_an_unknown_algorithm_is_refused_not_defaulted():
    """Rơi về mặc định khi gặp thuật toán lạ là mở đúng cánh cửa mà việc tự khai dựng ra để đóng."""
    strange = dict(V["record"], hash_alg="rot13")
    assert verify.verify_record(strange, V["record_hash_sha3_256"]) is False


def test_garbage_input_returns_false_instead_of_raising():
    """Bộ kiểm chạy trong vòng lặp của người khác — ném ngoại lệ ở đây là làm sập công cụ của họ."""
    assert verify.verify_record(None, "abc") is False
    assert verify.verify_record({}, "") is False
    assert verify.verify_record({"v": 1}, None) is False


def test_summary_tells_a_tool_what_it_is_looking_at():
    s = verify.summarize(V["record"], V["record_hash_sha3_256"])
    assert s["hash_matches"] is True
    assert s["code"] == V["record"]["code"]
    assert s["missing_fields"] == []


def test_summary_separates_a_short_record_from_a_tampered_one():
    """Bản ghi THIẾU trường và bản ghi ĐỦ mà lệch băm là hai ca khác hẳn nhau."""
    short = {"v": 2, "code": "ORI-0000000-AAAAAAAA"}
    s = verify.summarize(short, "0" * 64)
    assert s["missing_fields"], "phải nói ra là thiếu trường"
    assert s["hash_matches"] is False


def test_content_id_helper_refuses_to_guess():
    try:
        verify.verify_content_id(b"x", "ln1q_abc")
    except NotImplementedError as e:
        assert "sha256_of" in str(e)
    else:
        raise AssertionError("phải từ chối đoán định dạng địa chỉ nội dung")


def test_sha256_helper_is_the_plain_one():
    import hashlib
    assert verify.sha256_of(b"abc") == hashlib.sha256(b"abc").hexdigest()
