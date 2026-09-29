"""Run the SHARED cases in `contract/conformance.json` against the Python implementation.

Each language's own suite only proves that side agrees with itself. Two sides that agree with
themselves and disagree with each other stay green on both — exactly the gap three real bugs went
through (see the top of `orilife/_wire.py`). This file and its twin
`javascript/test/conformance.test.mjs` run the SAME list of cases, so a side that drifts goes red.

Measurement boundary: pinned where a method calls `request()` — the MAPPING (path, field names,
encoding). The transport underneath (building multipart, waiting out a 429, typing errors) is held
by `test_client.py`. Green here does NOT mean everything is tested.
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

# The same bytes for every fake file — the content is not what is measured, the field name is.
_BLOB = b"\x01\x02\x03"


class _Recorder(Client):
    """The real client, with only the transport swapped for a notebook."""

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
    """Exactly what goes on the wire: drop empty values, stringify the rest."""
    return {k: str(v) for k, v in (mapping or {}).items() if v is not None}


def _filename(item):
    """The file name read back from what was passed in — a `(name, bytes)` tuple or a path string."""
    return item[0] if isinstance(item, tuple) else item


def _materialise(value):
    """Turn a file placeholder in a test case into a real file of this language.

    `$single_file` is deliberately built as a bare path STRING, because that is both the most
    natural way to pass a single file to the Python client and exactly the input that exposes the
    iterate-a-string-into-characters bug. Build it as a tuple like `$file` and the case stays green
    under the very mutant it is named after — measured 2026-09-08: with the string guard removed
    from `_as_file_list`, 57/57 cases were still green.
    """
    if isinstance(value, dict) and "$file" in value:
        return (value["$file"], _BLOB)
    if isinstance(value, dict) and "$single_file" in value:
        return value["$single_file"]
    if isinstance(value, list):
        return [_materialise(v) for v in value]
    return value


def _invoke(client, case):
    """Build the call from the argument spec in the contract, never guess from the case name."""
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
                f"case {case['name']!r} is missing required argument {arg['name']!r}")

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
        # Raising is not enough: it must raise BEFORE any byte leaves the machine. Raising after
        # the images went up over a weak link is a full minute of waiting for a known error.
        assert client.seen is None, "must refuse before sending, not after"
        return

    _invoke(client, case)
    seen = client.seen
    assert seen is not None, "the method never called request()"

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
    """A method without a case is a method nobody guards.

    This gate lives here and not in the generator: a generator that grades itself both sets the
    exam and marks it.
    """
    covered = {c["method"] for c in CASES}
    missing = sorted(set(GENERATED) - covered)
    assert not missing, f"no shared case yet for: {missing}"


def test_every_case_names_a_method_that_exists():
    unknown = sorted({c["method"] for c in CASES} - set(SPEC))
    assert not unknown, f"a case calls a method missing from the contract: {unknown}"
