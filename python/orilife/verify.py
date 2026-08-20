"""INDEPENDENT verification — works without trusting OriLife, without a network, without a model.

This is the most important part of the package, and also the smallest.

A traceability system is only as trustworthy as an outsider's ability to check it. If the only way
to know whether a record is real is to ask the very server that produced it, the system proves
nothing — it is repeating its own claim. This file is the way out of that loop: hand it a record
in JSON, downloaded from anywhere, and a hash read off a Cardano block explorer, and the functions
here say whether that record is really the thing that hashed to that number.

Standard library only. No network, no dependencies, no state. Reading this file end to end takes
about ten minutes and shows you the whole computation — that is the point, because a verifier you
have to take on faith is worthless.

Three operations, and the boundary between them matters, because mixing the first two is the most
common mistake:

  entity_code()      derives the human-readable CODE from an internal id plus coarse coordinates.
                     Uses blake2b.
  record_hash()      hashes a RECORD for anchoring on chain. Uses the algorithm the record itself
                     declares.
  verify_record()    checks whether a record matches the hash that was anchored.

The first two use DIFFERENT hash functions, and that is not an oversight. Codes are already
printed on QR labels and already sit in the metadata of every past anchoring, so they must never
change; the record hash, by contrast, has an upgrade path (see `record_algorithm`). "Harmonising"
the two onto one hash function would break every code already out in the world.
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
# Crockford base32: I, L, O and U are dropped so that a person reading a code by eye cannot
# confuse them with 1 and 0.
_CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

RECORD_VERSION = 2
HASH_ALGORITHM = "sha3-256"            # records created from 2026-08 onwards
HASH_ALGORITHM_LEGACY = "blake2b-256"  # v=1 records, before 2026-08, which declare nothing

# The table of ALLOWED algorithms. Adding a line here is the only way to make this verifier accept
# a new one. An algorithm outside the table returns false and does NOT quietly fall back to the
# default — falling back would open the exact door that self-declared algorithms exist to close.
_HASHERS = {
    "sha3-256": lambda b: hashlib.sha3_256(b).hexdigest(),
    "blake2b-256": lambda b: hashlib.blake2b(b, digest_size=32).hexdigest(),
}


def geohash(lat: float, lon: float, precision: int = 7) -> str:
    """Standard geohash (Niemeyer's algorithm). Seven characters is roughly a 150 m cell — enough
    to say "which area", not enough to point at one trunk. That is why the public code carries
    exactly seven."""
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
    """The stable public code of one individual: `ORI-<geohash7>-<8 characters>`.

    Stable in the internal id and the coarse position, so the same individual always gets the same
    code. Without coordinates the middle section is seven zeroes — the code still works, it just
    loses the hint about the area.

    Use it to CROSS-CHECK: take the code printed on a slip, call this function with the id the
    server returned, and the two strings must be identical. A mismatch means one of the two ends
    has changed.
    """
    digest = hashlib.blake2b(entity_id.encode("utf-8"), digest_size=8).digest()
    suffix = _crockford(digest, 8)
    if gps and len(gps) == 2 and gps[0] is not None and gps[1] is not None:
        cell = geohash(float(gps[0]), float(gps[1]), 7)
    else:
        cell = "0000000"
    return f"ORI-{cell}-{suffix}"


def canonical_json(record: dict) -> bytes:
    """DETERMINISTIC serialisation: keys sorted, no stray whitespace, non-ASCII letters left alone.

    All three choices are mandatory and all three have caused real incidents in other systems: a
    different key order, one space after a colon, or an accented letter turned into `\\uXXXX` —
    each is enough to shift the hash while the content is identical. A record that does not match
    its hash is read as tampered with, not as differently serialised.
    """
    return json.dumps(record, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def hash_bytes(data: bytes, algorithm: str = HASH_ALGORITHM) -> str:
    """Hash `data`. An algorithm outside the allowed table raises ValueError; it never falls back
    to the default."""
    fn = _HASHERS.get((algorithm or "").strip().lower())
    if fn is None:
        raise ValueError(f"unsupported hash algorithm: {algorithm!r} (known: {sorted(_HASHERS)})")
    return fn(data)


def record_algorithm(record: dict) -> str:
    """The hash algorithm OF THIS PARTICULAR RECORD — read from the record, not guessed from a date.

    Records from v2 onwards declare it in `hash_alg`. Older records have no such key: `v<=1` means
    blake2b. A record with no `v` at all is treated as v=1 too — the older a record is the more
    fields it lacks, so the default has to lean towards the past for history to stay checkable.
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
    """Hash a record with the CURRENT algorithm. Use it when building a new record yourself.

    To CHECK an existing record call `verify_record` instead of comparing against this by hand: an
    old record was hashed with blake2b, so comparing it against sha3 will differ, and that
    difference reads as "tampered with".
    """
    return hash_bytes(canonical_json(record), HASH_ALGORITHM)


def verify_record(record: dict, expected_hash: str) -> bool:
    """Is this record really the thing that hashed to `expected_hash`?

    This is the function for the person doing the checking. Feed it record JSON pulled from
    storage and the number shown on a block explorer, get back True or False. It picks the
    algorithm from the record itself, so the checker does NOT need to know which era the record
    comes from.

    There is no downgrade path: the `hash_alg` key sits INSIDE the hashed bytes, so editing it to
    force a weaker algorithm has already changed the content, and the hash no longer matches.
    """
    if not isinstance(record, dict) or not expected_hash or not isinstance(expected_hash, str):
        return False
    try:
        got = hash_bytes(canonical_json(record), record_algorithm(record))
    except ValueError:
        return False
    return got == expected_hash.strip().lower()


def verify_content_id(data: bytes, content_id: str) -> bool:
    """Are the bytes you downloaded really the bytes this content address points at?

    OriLife's storage is content-addressed: a file's identifier is derived from the bytes of that
    file. Which means a checker does not have to trust the store — download the bytes, hash them
    again, compare with the address.

    NOTE: this function does NOT rebuild the address. It needs a `sha256` field carried alongside
    the record to compare against; the content-address format has several versions, and guessing
    the wrong one would report "invalid" for a perfectly good file — a false alarm in a verifier
    is worse than no verifier, because it teaches people to ignore warnings. Use `sha256_of()` and
    compare against the record's `sha256` field yourself.
    """
    raise NotImplementedError(
        "The content-address format has several versions — use sha256_of(data) and compare it "
        "with the `images[i].sha256` field in the record. See VERIFY.md."
    )


def sha256_of(data: bytes) -> str:
    """SHA-256 of a blob, lowercase hex — to compare with the `sha256` field in a record."""
    return hashlib.sha256(data).hexdigest()


def missing_fields(record: dict, required: Iterable[str] = ()) -> list:
    """Which required fields are absent. By default checks the minimum set of an individual record.

    It exists so that an automated checker can tell apart two very different situations: a
    COMPLETE record whose hash does not match (suspect tampering) and a record MISSING fields
    (more likely a truncated download or the wrong fragment).
    """
    required = tuple(required) or ("v", "code", "gps", "enrolled_at", "images")
    return [k for k in required if k not in record]


def summarize(record: dict, expected_hash: Optional[str] = None) -> dict:
    """A one-line summary for command-line tools and for agents: what this record says, and
    whether it matches."""
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
