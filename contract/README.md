# `contract/` — one source, several implementations

This directory is **the SDK's source of truth**. Every implementation (Python, JavaScript, and any
language added later) is either generated from it or tested against it. No implementation may
declare an endpoint that is not recorded here.

| File | What it is | Who reads it |
|---|---|---|
| `methods.json` | The SDK's endpoint table: method name, verb, path, field names, which field each file travels under, whether a failed call may be retried | `tools/generate.py`, both conformance suites |
| `conformance.json` | The shared test cases: call this method with these arguments and exactly this must go on the wire | `python/tests/test_conformance.py`, `javascript/test/conformance.test.mjs` |
| `vectors.json` | The verification vectors: entity codes, canonical JSON, record hashes | `test_verify.py`, `verify.test.mjs`, and every new implementation |
| `METHODS.md` | The lookup table for people — **generated**, do not edit by hand | people |

## What to do for each kind of change

**Add or change an endpoint** → edit `methods.json`, run `python3 tools/generate.py`, add cases to
`conformance.json`, run both test suites. Every skipped step has a gate that catches it: forget to
regenerate and `tools/generate.py --check` goes red; forget the cases and the coverage test goes
red in both languages.

**Change how a value is encoded** (compact JSON, bounding box, farm centre) → edit `python/orilife/_wire.py` AND `javascript/src/wire.js`, then add a case to
`conformance.json` that reaches both. The two `wire` files are the only place still written twice
by hand; `conformance.json` is what keeps them equal.

**Change the hash algorithm** → `vectors.json` must be regenerated from the code that actually runs
on the server, never typed by hand. Records already anchored on chain must not be re-hashed: see
`VERIFY.md`.

## Two gates, two different questions — do not merge them

| Gate | Asks | Needs network | On failure |
|---|---|---|---|
| `tools/generate.py --check` | does the generated code match the contract | no | red |
| `tools/check_server_drift.py` | does the contract match the running server | yes | three states: MATCH / DRIFT / **UNMEASURABLE** |

The second gate returns three states, not two, and "unmeasurable" is louder than "drift". A
measurement that reports "fine" exactly when it measured nothing makes its green meaningless: it
does not say *fine*, it says *I do not know* in the voice of *fine*.

## Why this directory exists

Before 2026-09-08, `python/orilife/client.py` and `javascript/src/client.js` were two hand-written
copies of the same contract. Three mismatches were measured when they were merged, and no test
caught any of them:

1. `create_farm(lat=10.762622, lon=106.660172)` sent `center_json=[10.762622, 106.660172]` from
   Python and `[10.762622,106.660172]` from JavaScript — one space apart is different bytes.
2. `update_farm(boundary_json=[[10.7, 106.6]])` JSON-encoded the value in Python; in JavaScript
   `URLSearchParams` stringified it to `10.7,106.6` and the server received something that is not
   JSON.
3. `identify_tree("photo.jpg")` in Python iterated the STRING character by character and uploaded
   nine one-character files. No function raised.

All three were silent. Each side had its own test suite and both were green — a per-language suite
only proves that one side agrees with itself; it never compares the two. That is the job of
`conformance.json`.

## Test cases must tell the TWO EXTREMES apart

Before writing a case, ask: *"can the input of this case tell the two mutants apart?"* — ask it
BEFORE asking "is it green or red". A case that is green at both extremes tests nothing.

Measured on 2026-09-08: the case *"a single file not wrapped in a list"* originally built the same
input for both languages, and with the string guard removed from `_as_file_list` all 57/57 Python
cases **stayed green**. The case carried the very name of the bug it let through. It now uses the
`$single_file` placeholder, built as a bare path string in Python and as a file object in
JavaScript — the two constructions differ on purpose, because each language breaks in its own way
at exactly that spot.
