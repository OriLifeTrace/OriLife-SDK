# Porting OriLife to a platform this repository does not ship

This SDK ships two languages. It is meant to work on far more than two platforms.

That does **not** mean we will write ten SDKs. It means the protocol is written down precisely
enough, and the acceptance tests are executable enough, that you can write a conforming client for
your platform in an afternoon — and *prove* it conforms without asking us.

Read this if you are on Swift, Kotlin, Rust, Go, Dart, C#, PHP, Elixir, an embedded C target, or a
shell script.

---

## 1. What actually makes a strange platform able to use this system

Two things, and only two:

1. **A wire contract it can reach with whatever HTTP it has.** This part is easy and already
   solved: HTTP/1.1, JSON, `multipart/form-data`, a bearer token. Every platform has this.
2. **The ability to check the answer without trusting us.** This is the hard part, and it is what a
   client library actually buys you. A traceability system whose claims can only be checked by
   asking the system is repeating its own claim.

Point 2 is arithmetic — hashing, canonical serialisation, base32 — and it must produce *identical
bytes* everywhere. That is why the acceptance test for a port is a set of numbers, not a code
review.

## 2. Three routes we considered, and why this one

| Route | What it costs | Why not / why yes |
|---|---|---|
| **(a) HTTP contract + docs precise enough to hand-write a client** | one document, two JSON files | **Chosen.** Works on every platform including ones we have never heard of, including `curl` in a shell script. Weakness: each porter re-implements retry and the verifier — answered by shipping the verifier as executable vectors rather than as prose |
| (b) Generate clients for N languages from the specification | N build pipelines, N package registries, N release cadences, N sets of generated-code ergonomics | The generated client is the easy half. OpenAPI describes the *wire*, not the *hash arithmetic* — so the part that matters, the verifier, still cannot be generated. We would carry N pipelines and still hand-write N verifiers |
| (c) One compiled core (Rust/C) exposed through WASM and FFI | a toolchain, a binary artefact per target, hundreds of kilobytes of WASM | Best fidelity for the verifier, and dead on arrival against the real constraint. Our users are on weak phones and thin connections; a binary blob is a download. It also ends "you can audit this by reading it", which is the reason the verifier is worth anything |

The deciding argument for (a): a stranger must be able to check a record **without running our
code**. Every route that makes verification depend on shipping our binary makes the system less
checkable, not more. So the deliverable is a specification plus vectors — and (a) is the only route
where that is the *primary* artefact rather than a by-product.

## 3. What "conforming" means — two files, both executable

You have a conforming implementation when both pass:

| File | Checks | Needs a network |
|---|---|---|
| `contract/vectors.json` | the verifier: entity codes, canonical JSON, record hashes, old-record compatibility | no |
| `contract/conformance.json` | the client: which path, which field name, which file field, how values are encoded | no |

Neither needs a server, an account, or a photograph. If you can run JSON and assertions on your
platform, you can prove conformance offline in a few seconds.

`contract/methods.json` tells your test runner how to build each call: which arguments are
positional, which are optional, which become form fields, query parameters, path segments or
uploaded files. Both bundled test runners are small enough to read as a model —
`python/tests/test_conformance.py` and `javascript/test/conformance.test.mjs`.

Do the verifier first. A client that calls the API but cannot check a record is the half that
already exists everywhere; the verifier is the half that makes the system worth integrating.

## 4. The verifier, stated completely

Standard library arithmetic only. No network, no state.

### 4.1 Canonical JSON

Serialise with **keys sorted by Unicode code point**, **no whitespace at all** (`,` and `:` as
separators), and **non-ASCII characters left as themselves** — never escaped to `\uXXXX`. Encode
the result as UTF-8.

All three rules are load-bearing. A different key order, one space after a colon, or an accented
Vietnamese letter turned into an escape — each on its own changes the hash while the content is
identical, and whoever is verifying concludes the record was tampered with.

> JavaScript trap: `Array.prototype.sort()` compares UTF-16 code units, which differs from code
> point order outside the basic multilingual plane. Sort by code point explicitly.

### 4.2 Which hash algorithm

Read it **from the record**, never guess it from a date:

```
if record.hash_alg is present and non-empty:  use it
else if int(record.v or 1) <= 1:              use blake2b-256
else:                                          use sha3-256
```

Only two algorithms are allowed: `sha3-256` and `blake2b-256`. Anything else **fails verification**
and must never fall back to a default — falling back opens the exact door that letting a record
declare its own algorithm was meant to close. `hash_alg` sits *inside* the hashed bytes, so editing
it to force a weaker algorithm has already changed the content.

`blake2b-256` means BLAKE2b with a 32-byte **output length**, not BLAKE2b-512 truncated to 32
bytes. The length is mixed into the initial value; the two differ. `contract/vectors.json` has a
case that catches this.

### 4.3 Entity code

The public code of one individual is `ORI-<geohash7>-<8 characters>`:

- **Suffix**: BLAKE2b of the entity id (UTF-8), **8-byte output**; render the leading 40 bits as 8
  characters of **Crockford base32**, alphabet `0123456789ABCDEFGHJKMNPQRSTVWXYZ` (no I, L, O or U,
  so a person reading a code aloud cannot confuse them with 1 and 0). Take five bits at a time from
  the most significant end.
- **Middle**: standard geohash (Niemeyer) of the coordinates at precision 7, alphabet
  `0123456789bcdefghjkmnpqrstuvwxyz`. Seven characters is roughly a 150 m cell — enough to say
  *which area*, not enough to point at one trunk.
- No coordinates → the middle is seven zeroes. The code still works; it loses the area hint.

Note that the code and the record hash use **different** hash functions, and that is deliberate,
not an oversight. Codes are already printed on labels and already sit in the metadata of past
anchorings, so they can never change; the record hash has an upgrade path. "Harmonising" the two
would break every code already out in the world.

### 4.4 Verifying

`verify_record(record, expected_hash)` = canonical-JSON the record, hash it with **the algorithm
the record declares**, compare against `expected_hash` lowercased and trimmed.

Return **false**, do not raise, for junk input (null record, empty hash, unknown algorithm). Your
verifier runs inside somebody else's loop; throwing there crashes their tool.

Also implement `missing_fields()`: a **complete** record whose hash does not match (suspect
tampering) and a record **missing fields** (far more often a truncated download) are two different
situations and must not read the same.

## 5. The client, stated completely

### 5.1 Transport

- Base URL `https://api.orilife.io`. Token in `Authorization: Bearer <token>`, **never** a cookie —
  CORS is open to every origin with credentials off, so cookies do not travel cross-origin.
- Token lives 12 hours. On `401`, log in again; do **not** keep the password in memory to re-login
  silently. That trades a visible error for an invisible risk.
- Uploads are `multipart/form-data`. Fields whose value is absent are **dropped**, never sent as
  the string `"null"` — sending it builds junk data at the far end.
- Default timeout 30 s. Video endpoints need at least 120 s (`contract/methods.json` carries
  `timeout_min_seconds` where it applies).

### 5.2 Retrying — the line that matters

| Failure | Retry? |
|---|---|
| `429` | Yes. Sleep **exactly** the number of seconds in `Retry-After` (cap it at 60 s). Do not invent your own pace — the server knows its queue, you do not |
| `5xx` or network failure on `GET`/`HEAD` | Yes, with a doubling gap capped at 8 s. A read costs nothing to repeat |
| `5xx` or network failure on anything else | **No.** The request may have arrived and already created a record. Surface the error; let the caller ask `list_trees()` whether the write landed |
| `4xx` other than 429 | No. Nothing about repeating it will change the answer |

### 5.3 Errors must be typed

One error string forces every application to re-derive the same sorting rules, and everyone gets
it slightly wrong. Map status to a distinct type: `400`/`422` invalid request · `401` auth ·
`403` permission · `404` not found · `413` too large · `429` rate limited · `5xx` server ·
transport failure network.

Carry the server's own sentence on every one of them, taken from `error`, then `message`, and only
then `detail`. `detail` is the shape the parameter-validation layer produces — usually a structure,
not a sentence — and displaying it is the fastest way to put a technical string in front of a
farmer. **Show the server's sentence.** It knows the context; your application does not.

### 5.4 Do not interpret the internals

Responses carry fields beyond what is documented. Pass them to the application **verbatim**. Do not
name them, do not explain them, do not build decision rules on them. Branch on `decision`; treat an
unrecognised value as `UNCERTAIN` and ask the person.

### 5.5 Do not build a silent shell

Three rules, each of which has cost somebody a real incident:

- A response that does not match the contract → **throw**. Never `catch { return [] }`. An empty
  list and a failed call must reach two different screens.
- Never fill missing data with a plausible default. A padded value does not stop where it was
  padded; it travels into a comparison somewhere else, where it can no longer say it was missing.
- `404` on several endpoints means *private* **or** *absent*, deliberately indistinguishable. Never
  print "this tree does not exist".

## 6. Weak devices, thin connections, no connection

These are the operating conditions, not an edge case.

- **The read half works offline, by construction.** Verification touches no network. Fetch the
  provenance record and the images once, keep them, and check them on a phone with the radio off.
  Both bundled implementations have a test asserting the verifier issues no request; keep that test
  in your port.
- **Send fewer, better photos.** Several angles beat one photo, but each angle costs a megabyte on
  a field connection. `capture_plan()` tells you what is actually missing, so you ask for the one
  photo that helps instead of four that do not.
- **Fail before uploading, not after.** Validate required arguments and image counts *before* the
  bytes leave the device. A rejection that arrives after a two-minute upload is two minutes of
  someone's day and their data allowance.
- **Every call needs a timeout and a bounded retry.** An unbounded retry on a thin connection is
  indistinguishable from a hang.
- **Ask for narrow reads.** `list_animals(limit=…, offset=…)`, `list_trees(farm_id=…)`. Do not pull
  the whole holding to show one screen.
- **Do not require the endpoint index.** `supports()` costs one request and caches; on a server
  that lacks `GET /api` it answers false rather than raising, because "I cannot ask" and "the
  answer is no" lead to the same decision.

## 7. Checklist for a new port

1. Verifier passes every case in `contract/vectors.json`.
2. Client passes every case in `contract/conformance.json`, driven by `contract/methods.json`.
3. Required arguments and image-count limits throw **before** any byte is sent — the conformance
   runner asserts this, do not weaken it.
4. Retry policy matches section 5.2, including the `Retry-After` sleep.
5. Errors are typed and carry the server's own sentence.
6. A test asserts the verifier makes no network call.
7. Tell us, and we will link your port from `README.md`. We will not adopt it into this repository:
   a port is best maintained by the people who use it on that platform.
