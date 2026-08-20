# OriLife SDK for Python

Identify an **individual** — not "this is a durian tree" but "this is **tree 47** in this orchard"
— from photographs alone. No tags, no QR codes, nothing attached to the object.

This package is what you need to write an application that talks to OriLife, and also what anyone
else needs to **check** what OriLife says without having to trust OriLife.

```
Base URL   https://api.orilife.io
API docs   https://api.orilife.io/docs   ·   https://api.orilife.io/openapi.json
```

Python 3.9 or newer. No dependencies.

---

## Thirty seconds

```bash
pip install orilife
```

```python
from orilife import Client

client = Client()
client.login("my_orchard", "durian.orchard.2026")

# Recognise a tree again. Several photos from several angles beat a single photo.
out = client.identify_tree(["photo.jpg"], lat=10.762, lon=106.660)
print(out["decision"], out.get("confidence"))
```

The same call without this package, because the API is plain HTTP:

```bash
curl -X POST https://api.orilife.io/api/identify \
  -H "Authorization: Bearer $TOKEN" \
  -F 'files=@photo.jpg' -F 'lat=10.762' -F 'lon=106.660'
```

---

## Two halves, and the second one is the one that matters

```python
from orilife import Client   # calls the API   — you are TRUSTING OriLife
from orilife import verify   # verification    — you trust nobody
```

`Client` asks the server and repeats its answer. If the only way to know whether a record is real
is to ask the very server that produced it, the system proves nothing — it is repeating its own
claim.

`verify` is the way out of that loop. It recomputes the hash from the record itself and compares
it with the number anchored on Cardano. No network, no dependencies, no OriLife in the room:

```python
import json
from orilife import verify

record = json.load(open("downloaded-record.json"))   # from anywhere
onchain = "3f0a…"                                    # read off a block explorer

verify.verify_record(record, onchain)   # True means nobody has touched this record
```

The JavaScript package computes the same numbers, and both are checked against one set of vectors
in `tests/vectors.json`. Two independent implementations agreeing on one set of vectors is far
stronger evidence than one implementation checking itself. Details, including how to redo the
computation by hand: [VERIFY.md](../VERIFY.md).

---

## What can be recognised

| Subject | Enrol | Recognise again |
|---|---|---|
| Tree | `enroll_tree()` | `identify_tree()` · `identify_tree_video()` |
| Fruit | `enroll_fruit()` · `add_fruit_view()` | `identify_fruit()` · `lookup_fruit()` |
| Animal | `enroll_animal()` | `identify_animal()` · `scan_animal()` |

`identify_auto()` is the combined door: send photos, the server works out what kind of subject it
is looking at and identifies the individual. Your application never has to ask the user what they
are photographing — pushing the sorting work onto a person because the machine cannot do it is
exactly the shape OriLife exists to remove.

**Not every server serves every endpoint.** `identify_auto()`, `describe()` and `/llms.txt` exist
on servers that declare them and answer 404 elsewhere; there is no silent fallback to another
endpoint, because quietly changing what an answer means is worse than an error. Ask first:

```python
if client.supports("/api/identify/auto"):
    out = client.identify_auto(["photo.jpg"], lat=10.762, lon=106.660)
else:
    out = client.identify_tree(["photo.jpg"], lat=10.762, lon=106.660)
```

`supports()` reads the server's endpoint listing once per client and remembers it, so calling it
in a loop costs one request in total.

---

## Two ways in

**The public way — no account.** For buyer-facing applications: someone photographs a fruit on a
stall, or scans the code on a slip, and reads where it came from.

```python
Client().lookup_fruit("fruit.jpg")            # one photo → public candidates
Client().resolve("ORI-w3gv5j2-A7K9PQ2M")      # look up a code
Client().tree_by_code("ORI-w3gv5j2-A7K9PQ2M") # provenance of one tree
Client().species_catalog()                    # the species this server knows
Client().health()                             # what the server can do today
```

**The grower's way — needs a token.** Enrol subjects, recognise them again, keep a care log,
anchor evidence. Each account only ever matches **within its own farm** — that is privacy and
accuracy at once, because two trees of the same species in two provinces never get the chance to
be confused.

Account rules, worth reading before the first call: username 3–32 characters, **lowercase
letters, digits, dots and underscores** only — no hyphens. Password at least 10 characters, at
least two character classes, not in the common-password list. A token lives 12 hours.

---

## Everything the client exposes

**Session**

| Method | Endpoint |
|---|---|
| `signup(username, password)` | `POST /api/signup` |
| `login(username, password)` | `POST /api/login` |
| `me()` | `GET /api/me` |
| `logout()` | `POST /api/logout` |
| `logout_all()` | `POST /api/logout-all` — ends every session on every device |

**Open without a token**

| Method | Endpoint |
|---|---|
| `health()` | `GET /api/health` |
| `endpoints()` | `GET /api` |
| `supports(path)` | reads `GET /api` once, then answers from memory |
| `describe()` | `GET /.well-known/orilife.json` |
| `species_catalog()` | `GET /api/species/catalog` |
| `resolve(code)` | `GET /api/resolve/{code}` |
| `tree_by_code(code)` | `GET /api/tree_by_code/{code}` |
| `lookup_fruit(image)` | `POST /api/fruit/lookup` |

**Recognising**

| Method | Endpoint |
|---|---|
| `identify_auto(images, lat=, lon=, species=, farm_id=)` | `POST /api/identify/auto` |
| `identify_tree(images, lat=, lon=, last_tree=)` | `POST /api/identify` |
| `identify_tree_video(video, lat=, lon=)` | `POST /api/identify/video` |
| `identify_fruit(image, tree_id=)` | `POST /api/fruit/identify` |
| `identify_animal(image, species=, farm_id=)` | `POST /api/animal/identify` |
| `scan_animal(image, farm_id=, species=)` | `POST /api/animal/scan` |
| `identify_kind(image)` | `POST /api/kind` |

**Enrolling**

| Method | Endpoint |
|---|---|
| `enroll_tree(images, name=, lat=, lon=, farm_id=, species=)` | `POST /api/enroll` |
| `verify_add(tree_id, images)` | `POST /api/verify_add` |
| `list_trees(farm_id=)` | `GET /api/trees` |
| `enroll_fruit(images, tree_id=, name=, bbox=)` | `POST /api/fruit/enroll` |
| `add_fruit_view(fruit_id, images)` | `POST /api/fruit/add_view` |
| `enroll_animal(images, species=, farm_id=, name=, owner_did=)` | `POST /api/animal/enroll` |
| `list_animals(farm_id=, species=, limit=, offset=)` | `GET /api/animal/list` |

The fruit endpoints take **one photo per call**: enrol with the first angle, then call
`add_fruit_view()` once per further angle. Passing more than one image raises `ValueError` here
rather than letting the extra photos be dropped in silence. `bbox` is `(x, y, w, h)` or a dict
with those keys.

**Farms**

| Method | Endpoint |
|---|---|
| `create_farm(name, lat=, lon=)` | `POST /api/farm` |
| `list_farms()` | `GET /api/farms` |
| `get_farm(farm_id)` | `GET /api/farm/{farm_id}` |
| `update_farm(farm_id, **fields)` | `POST /api/farm/{farm_id}/update` |
| `delete_farm(farm_id)` | `DELETE /api/farm/{farm_id}` |

Deleting a farm does not delete its trees: they lose their `farm_id` and stay traceable on their
own. `update_farm()` accepts `name`, `kind`, `boundary_json`, `center_json`, `boundary_method`,
`boundary_acc_m`, `note`; lists and dicts are JSON encoded on the way out.

**Saying whether the answer was right**

| Method | Endpoint |
|---|---|
| `submit_verdict(query_id, verdict, correct_tree_id=)` | `POST /api/identify_verdict` |
| `submit_fruit_verdict(query_id, verdict, correct_fruit_id=)` | `POST /api/fruit/identify_verdict` |
| `submit_animal_verdict(query_id, verdict, correct_did=)` | `POST /api/animal/identify_verdict` |

`query_id` comes from the identification answer and joins the two together. `verdict` is
`correct`, `wrong` or `other`; animals also accept `unknown_ok`, meaning the individual was never
enrolled and the server was right to say it did not know.

**Evidence and history**

| Method | Endpoint |
|---|---|
| `capture_plan(entity_type, entity_id)` | `GET /api/capture/plan` — what is missing, what to photograph next |
| `provenance(tree_id)` | `GET /api/provenance/{tree_id}` |
| `timeline(entity_type, entity_id)` | `GET /api/{entity_type}/{entity_id}/timeline` |
| `add_event(entity_type, entity_id, kind, data=None)` | `POST /api/{entity_type}/{entity_id}/event` |
| `anchor_event(entity_type, entity_id, event_id)` | `POST /api/{entity_type}/{entity_id}/event/{event_id}/anchor` |
| `proof(entity_type, entity_id, event_id)` | `GET /api/{entity_type}/{entity_id}/proof/{event_id}` |

`entity_type` is `tree`, `fruit`, `farm`, `animal` or `plot`. A subject that was never enrolled
cannot have a timeline: writing the first event would otherwise be a way to claim ownership of
somebody else's tree. Anchoring costs money on chain and is the owner's decision — the server
suggests it with `suggest_anchor`, it never does it by itself.

Anything not wrapped in a method is one line away, and the wrapping adds nothing you lose by
skipping it:

```python
client.request("POST", "/api/tree/t-1/event", json_body={"kind": "harvest", "gps": [10.5, 106.5]})
```

---

## Three things to know before the first line

**Read the capabilities, do not hard-code them.** `health()` returns `features`, generated from
the server's real routing table. Read it and then decide which screens to show — the server gains
a capability and your application can use it without an update.

**"Not sure" is a result, not an error.** The system answers `uncertain` instead of guessing.
Do not retry, do not show a spinner — ask the user, or invite one more angle.

**`unknown` from a code lookup carries no reason, deliberately.** If "wrong code" answered
differently from "real but private code", someone walking the code space could count another
person's orchard. There is no difference to read.

---

## Errors

Every status code is its own class, because an application has to handle them in different ways.

| Status | Class | What to do |
|---|---|---|
| — | `NetworkError` | The request may **never have arrived**. Read endpoints: call again. Write endpoints: ask for the state first |
| 400 · 422 | `InvalidRequestError` | Missing field or a rule not met. Show `message` to the user |
| 401 | `AuthError` | Token expired. Log in again and repeat the call |
| 403 | `PermissionError_` | Not allowed. A new token does **not** help |
| 404 | `NotFoundError` | Do not print "does not exist" — see `unknown` above |
| 413 | `TooLargeError` | Compress and resend; do not retry unchanged |
| 429 | `RateLimitedError` | Wait `retry_after` seconds. This client already waits for you |
| 5xx | `ServerError` | Retry with a growing gap — read endpoints only |

```python
from orilife import Client, AuthError, RateLimitedError

try:
    out = client.identify_tree(["photo.jpg"])
except AuthError:
    client.login(user, password)
except RateLimitedError as e:
    print(f"try again in {e.retry_after}s")
```

`message` is the sentence the server already wrote for the end user. **Show that sentence.** Do
not turn a status code into a sentence of your own: the server knows the context, your application
does not.

Write endpoints are never retried automatically — a resend may create a second record. Read
endpoints are retried on 5xx and on network failures, and a 429 is always waited out for exactly
as long as the server asked.

---

## Limits

| | |
|---|---|
| One file | 20 MB |
| One batch of photos | 64 MB |
| Video | 80 MB |
| Token lifetime | 12 hours |
| Too often | `429` with a `Retry-After` header |

The cap is counted while the bytes are still arriving, so `413` comes back **before** the upload
finishes — you do not spend the whole upload to learn it failed.

---

## Running the tests

```bash
cd python && python -m pytest -q      # 67 tests, all offline
```

No network, no fixtures to download: the client tests run against a fake server built from the
standard library, and the verifier tests run against `tests/vectors.json`.

---

## What is in here, and what is deliberately not

**Here:** the API client, the independent verifier, the API contract, working examples.

**Not here:** the recognition itself. How the machine decides that two photographs show the same
individual stays on the server.

That boundary is not new to this repository — it already exists at the server's response layer:
detailed scores and every internal parameter of the comparison **never leave the API**. An
application receives `decision` and a coarse confidence level, not the internals. Two reasons, and
the second matters more than the first: exposed internals can be copied by a competitor, and worse,
they turn the system into a probe that an attacker can tune against until something slips through.

Everything **outside** that boundary is open, including the whole verification path — the one
thing you need to catch OriLife lying. Everything inside stays closed.

---

## Read next

- [CONTRACT.md](../CONTRACT.md) — the full API contract: every endpoint, every field, every error shape
- [VERIFY.md](../VERIFY.md) — independent verification, including how to redo it by hand without this package
- [SECURITY.md](../SECURITY.md) — handling tokens, and what must never be embedded in an application
- [examples/](../examples/) — working examples

---

Apache-2.0. Evidence anchored on Cardano, data stored distributed on LampNet.
