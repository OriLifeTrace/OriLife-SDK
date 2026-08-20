"""The verifier has to produce EXACTLY the numbers production produced — not close, not "about".

`vectors.json` comes from the same code that runs on the OriLife server. If the verifier here ever
drifts away from those numbers, every record already anchored on chain would read as "tampered
with" while nobody tampered with anything — and a verifier that raises false alarms is worse than
no verifier, because it teaches people to ignore warnings.

Runs offline. No network, no dependencies, no server needed.
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
    """The same content with keys inserted in another order must produce the same bytes."""
    record = V["record"]
    shuffled = dict(reversed(list(record.items())))
    assert verify.canonical_json(record) == verify.canonical_json(shuffled)


def test_canonical_json_keeps_non_ascii_letters_as_themselves():
    """Turning an accented letter into `\\uXXXX` changes the bytes, and changed bytes change the
    hash. A real record name is used here, because real names carry accents."""
    name = V["record"]["name"]
    raw = verify.canonical_json({"name": name})
    assert name.encode("utf-8") in raw
    assert b"\\u" not in raw


def test_record_hash_matches_production():
    assert verify.record_hash(V["record"]) == V["record_hash_sha3_256"]


def test_verify_accepts_the_real_record_and_hash():
    assert verify.verify_record(V["record"], V["record_hash_sha3_256"]) is True


def test_verify_still_reads_the_old_records():
    """Records anchored before 2026-08 used the older algorithm and must NOT be re-hashed. They
    still have to be checkable today."""
    assert verify.record_algorithm(V["record_v1"]) == verify.HASH_ALGORITHM_LEGACY
    assert verify.verify_record(V["record_v1"], V["record_v1_hash_blake2b_256"]) is True


def test_one_changed_character_breaks_the_hash():
    tampered = dict(V["record"], name=str(V["record"].get("name", "")) + " ")
    assert verify.verify_record(tampered, V["record_hash_sha3_256"]) is False


def test_downgrading_the_declared_algorithm_does_not_help_an_attacker():
    """`hash_alg` sits INSIDE the hashed bytes, so editing it changes the content as well."""
    weakened = dict(V["record"], hash_alg=verify.HASH_ALGORITHM_LEGACY)
    assert verify.verify_record(weakened, V["record_hash_sha3_256"]) is False


def test_an_unknown_algorithm_is_refused_not_defaulted():
    """Falling back to the default on an unknown algorithm opens the exact door that a
    self-declared algorithm exists to close."""
    strange = dict(V["record"], hash_alg="rot13")
    assert verify.verify_record(strange, V["record_hash_sha3_256"]) is False


def test_garbage_input_returns_false_instead_of_raising():
    """The verifier runs inside somebody else's loop — raising here would crash their tool."""
    assert verify.verify_record(None, "abc") is False
    assert verify.verify_record({}, "") is False
    assert verify.verify_record({"v": 1}, None) is False


def test_summary_tells_a_tool_what_it_is_looking_at():
    s = verify.summarize(V["record"], V["record_hash_sha3_256"])
    assert s["hash_matches"] is True
    assert s["code"] == V["record"]["code"]
    assert s["missing_fields"] == []


def test_summary_separates_a_short_record_from_a_tampered_one():
    """A record MISSING fields and a COMPLETE record with a wrong hash are two different cases."""
    short = {"v": 2, "code": "ORI-0000000-AAAAAAAA"}
    s = verify.summarize(short, "0" * 64)
    assert s["missing_fields"], "it has to say which fields are missing"
    assert s["hash_matches"] is False


def test_content_id_helper_refuses_to_guess():
    try:
        verify.verify_content_id(b"x", "ln1q_abc")
    except NotImplementedError as e:
        assert "sha256_of" in str(e)
    else:
        raise AssertionError("it must refuse to guess the content-address format")


def test_sha256_helper_is_the_plain_one():
    import hashlib
    assert verify.sha256_of(b"abc") == hashlib.sha256(b"abc").hexdigest()
