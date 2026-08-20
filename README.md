# OriLife SDK

OriLife identifies **individuals** from photographs — not "this is a durian tree" but "this is
**tree 47** in this orchard". No tags, no QR codes, nothing attached to the object.

Two things live in this repository:

- **Client SDKs** (Python, JavaScript) for talking to the OriLife API.
- **An independent verifier** that lets anyone check what OriLife claims *without trusting
  OriLife* — it recomputes hashes from the record itself and compares them with what was anchored
  on the Cardano blockchain. No network, no dependencies.

```
Base URL      https://api.orilife.io
Endpoint list https://api.orilife.io/api          (also: /docs, /openapi.json)
```

Interface text returned by the API (`message`, `error`) is written in Vietnamese, for Vietnamese
farmers. Field names, decision values and status codes are English/ASCII and stable. See
[Errors](#errors).

---

## Thirty seconds

**Python** — no third-party dependencies, Python 3.9+:

```bash
pip install orilife
```

```python
from orilife import Client

client = Client()
client.signup("my_orchard", "orchard.durian.2026")   # creates a real account, see Account rules

# 1. Teach it one tree. Several angles beat one photo.
tree = client.enroll_tree(["tree-front.jpg", "tree-side.jpg"],
                          name="Tree 47", lat=10.762, lon=106.660)

# 2. Come back later, photograph the same tree, ask who it is.
out = client.identify_tree(["tree-again.jpg"], lat=10.762, lon=106.660)
print(out["decision"], out.get("tree_id"), out.get("name"))
# MATCH <tree id> Tree 47
```

**JavaScript** — browsers, Node 18+, Deno, Bun, Cloudflare Workers:

```bash
npm install @orilife/sdk
```

```js
import { Client } from '@orilife/sdk';

const client = new Client();
await client.login('my_orchard', 'orchard.durian.2026');

const out = await client.identifyTree([file], { lat: 10.762, lon: 106.660 });
console.log(out.decision, out.tree_id);
```

**No SDK at all** — it is plain HTTP:

```bash
curl -X POST https://api.orilife.io/api/identify \
  -H "Authorization: Bearer $TOKEN" \
  -F 'files=@tree-again.jpg' -F 'lat=10.762' -F 'lon=106.660'
```

---

## What you just got back

Every identify endpoint answers with a `decision` — a short, stable, uppercase token. Read that
one field and branch on it.

| `decision` | Meaning | What your app should do |
|---|---|---|
| `MATCH` | Recognised as a known individual | Show `tree_id` / `name` |
| `UNCERTAIN` | Candidates are too close to call | Ask the person, or invite one more angle. **Do not retry the same photo** |
| `MOVED` | Recognised, but it is not where it used to be | Confirm with the owner, then update the location |
| `NO_MATCH` | Not recognised as anything on file | Offer to enroll it as new — but read `allow_enroll_new` first |
| `EMPTY_BUCKET` | Nothing to compare against yet (trees) | Enroll first |

Fruit and animal endpoints use the same tokens with one difference each (`EMPTY_GALLERY`,
`EMPTY_FARM`). Video adds `NO_FRAMES`. The complete table, with the exact endpoint each token can
come from, is in [CONTRACT.md](CONTRACT.md#3-identify).

Alongside it comes `confidence`, a **coarse band** meant for wording on screen, not for logic.
Never build decision rules on it — the decision is already in `decision`.

"Uncertain" is a **result, not an error**. A system that guesses when it does not know is worse
than one that says so.

---

## Where `farm_id` comes from

Most examples pass a `farm_id`. A farm is a real entity you create — it is not a string you make
up, and it is not optional plumbing: it is how animals are scoped, how trees are grouped, and how
you share read access with another account.

```python
farm = client.create_farm("Home orchard", lat=10.762, lon=106.660)
farm_id = farm["farm"]["farm_id"]

client.enroll_tree(["a.jpg", "b.jpg"], name="Tree 47", farm_id=farm_id)
client.list_farms()                       # every farm this account owns, with counts
```

Trees can live without a farm; **animals cannot** — `enroll_animal` and `scan_animal` both require
`farm_id`. Five endpoints cover the whole lifecycle (create, list, read, update, delete); they are
documented in [CONTRACT.md](CONTRACT.md#2-farms).

---

## Two ways in

**Public lane — no account.** For buyer-facing apps: a customer photographs a fruit on display, or
types the code from a receipt, and gets the origin story.

```python
Client().lookup_fruit("fruit.jpg")             # photo of one fruit -> public candidates
Client().resolve("ORI-w3gv5j2-A7K9PQ2M")       # look up a code
Client().species_catalog()                     # species list
Client().health()                              # what this server can do today
```

**Owner lane — needs a token.** Enroll, re-identify, log care events, build 3D, anchor evidence.
Each account only matches **within its own holdings**. That is privacy and accuracy at once: two
trees of the same species in two provinces never get the chance to be confused.

---

## Account rules

Read these before your first call — they are where nearly every integration trips.

- Username: **3-32 characters**, lowercase letters, digits, dot and underscore only. **No hyphen.**
  `my-orchard` is rejected; `my_orchard` is accepted.
- Password: at least **10 characters**, at least **two character classes**, and not on the common
  password list.
- Tokens live **12 hours**. After that endpoints return `401`; catch it and log in again.
- Violations return `400` with a sentence saying exactly what is wrong. Show that sentence.

**There is no sandbox.** `signup()` creates a real account on `https://api.orilife.io`, and data
you enroll is real data. Use a throwaway username while you are exploring, and delete it when you
are done (`GET /api/account/data` previews what would be deleted, `POST /api/account/delete`
performs it).

---

## What OriLife can identify

| Kind | Enroll | Re-identify | Status |
|---|---|---|---|
| Tree | `POST /api/enroll` | `POST /api/identify` | In field use |
| Fruit | `POST /api/fruit/enroll` | `POST /api/fruit/identify` | In field use |
| Animal | `POST /api/animal/enroll` | `POST /api/animal/identify` | Works; requires `species` and `farm_id` |
| Flowers, processed goods | — | — | **No route yet** |

Do not hard-code this table. Ask the server instead: `GET /api/health` returns a `features` list
generated from the server's real routing table, and `GET /api` lists every endpoint it actually
serves. A hand-copied capability list is correct for about one day.

---

## Ask before you call: `supports()`

Some endpoints exist only on servers that ship them. The SDK reads `GET /api` once, remembers it,
and answers offline afterwards:

```python
if client.supports("/api/identify/auto"):
    out = client.identify_auto(["photo.jpg"], lat=10.762, lon=106.660)
else:
    out = client.identify_tree(["photo.jpg"], lat=10.762, lon=106.660)
```

```js
if (await client.supports('/api/identify/auto')) { /* ... */ }
```

Three endpoints were **not live on `https://api.orilife.io` when this document was written
(measured 2026-08-20, all returned 404)**:

| Endpoint | What it would give you |
|---|---|
| `POST /api/identify/auto` | One call for any kind: the server works out tree/fruit/animal, then identifies |
| `GET /.well-known/orilife.json` | Machine-readable service descriptor |
| `GET /llms.txt` | One-page map for language agents |

They are documented here because servers that do ship them behave exactly as described. The SDK
**never silently falls back** to a different endpoint on 404 — quietly changing behaviour is a
worse failure than an error you can see.

---

## Errors

Each status code is a distinct error class, because your app has to handle them in genuinely
different ways.

| Status | Class | What your app should do |
|---|---|---|
| — | `NetworkError` | The request **may not have arrived**. Read endpoints: call again. Write endpoints: ask for current state first |
| 400 · 422 | `InvalidRequestError` | Missing field or rule violation. Show `message` to the user |
| 401 | `AuthError` | Token expired. Log in again, then retry |
| 403 | `PermissionError` | Not allowed. A fresh token does **not** help |
| 404 | `NotFoundError` | Do not print "does not exist" — see the note below |
| 413 | `TooLargeError` | Compress and resend; do not retry unchanged |
| 429 | `RateLimitedError` | Wait exactly `retry_after` seconds. The SDK does this for you |
| 5xx | `ServerError` | Retry with backoff — read endpoints only |

Two things to know about the bodies:

**Human-facing text is Vietnamese.** `message` and `error` are sentences the server already wrote
for the end user. If your users read Vietnamese, show them verbatim: the server knows the context,
your app does not. If they do not, branch on the status code and the machine-readable fields
(`decision`, `reason`, `state`) and write your own copy — never machine-translate the sentence and
present it as OriLife's words.

**Some endpoints return `200` with `ok: false`.** That means "the job could not be done", not "the
request was malformed". Always read `ok`; never trust the status code alone. Confirmed cases and
the reason codes they carry are listed in [CONTRACT.md](CONTRACT.md#9-errors).

**`404` and "private" are the same answer, on purpose.** If "wrong code" answered differently from
"real but private", anyone could enumerate other people's orchards by probing. There is no
difference to infer, so do not try to infer one.

---

## Limits

| | |
|---|---|
| One file | 20 MB |
| One batch of images | 64 MB |
| Video | 80 MB |
| Token lifetime | 12 hours |
| Calling too fast | `429` with a `Retry-After` header |

Limits are counted **while bytes are still uploading**, so `413` comes back before the upload
finishes — a farmer on a weak signal does not have to burn the whole file to learn it failed.

There is no published requests-per-minute figure. Respect `Retry-After` and treat it as the only
authority.

---

## Browsers, bots and agents

CORS is open to every origin, and cross-origin cookies are **not** sent. Both halves matter, and
the second one is the one that keeps you safe: with no cookie riding along, there is no ambient
authority for a hostile page to borrow, and the entire CSRF class disappears. In exchange, the
token **must** travel in the `Authorization: Bearer` header.

| For machines | |
|---|---|
| `GET /api` | Every endpoint this server serves, with methods and one-line summaries |
| `GET /openapi.json` | Full specification; client generators accept it |
| `GET /.well-known/orilife.json` | Service descriptor — only on servers that ship it |
| `GET /llms.txt` | One-page map for language agents — only on servers that ship it |

---

## What is in this repository, and what is deliberately not

**Here:** API clients (Python, JavaScript), the independent verifier, the API contract, runnable
examples.

**Not here:** the recognition engine. How the server decides that two photographs show the same
individual stays on the server.

That boundary is not new paperwork invented for this repository — it already exists at the API
response boundary itself: the internal workings of the comparison do not leave the server. Your
app receives `decision` and a coarse `confidence` band. Two reasons, and the second matters more
than the first: exposed internals can be copied by a competitor, and, worse, they turn the system
into an oracle an attacker can probe until something slips through.

Put differently: everything **outside** that boundary is open, including the entire verification
path — which is the only part you need in order to catch OriLife lying. Everything **inside**
stays closed.

---

## Verifying without trusting OriLife

```python
from orilife import Client   # calling the API  — you are TRUSTING OriLife
from orilife import verify   # verification     — you trust no one
```

`Client` asks the server and copies down the answer. If the only way to know a record is genuine
is to ask the server that produced it, the system has proven nothing — it is repeating its own
testimony.

`verify` is the way out of that loop. It recomputes the hash from the record itself and compares
it with the number anchored on Cardano. No network, no dependencies, no OriLife required:

```python
import json
from orilife import verify

record  = json.load(open("record.json"))   # downloaded from anywhere
onchain = "3f0a..."                        # read off a block explorer

verify.verify_record(record, onchain)      # True means nobody has touched this record
```

The same arithmetic, in a browser:

```js
import * as verify from '@orilife/sdk/verify';
verify.verifyRecord(record, onchain);
```

Two independent implementations agree on one set of test vectors generated by the code running on
the server. Full walkthrough, including how to redo every step by hand with no SDK at all:
[VERIFY.md](VERIFY.md).

---

## Run the tests

```bash
cd python && python -m pytest tests/ -q      # runs offline
cd javascript && node --test test/           # no install step
```

Both suites check against the **same** vector file (`python/tests/vectors.json`). Two independent
implementations matching one set of vectors is far stronger evidence than one implementation
grading its own homework: a bug has to appear identically in both languages to get through.

---

## Not answered here yet

Stated plainly so you do not go looking:

- **Pricing.** Not published in this repository.
- **Rate limit figures.** Not published; only `Retry-After` is authoritative.
- **Latency expectations.** Not published.
- **How long OriLife retains uploaded images and coordinates server-side.** Not documented here.
  What *is* documented: video clips submitted to `POST /api/identify/video` are used and discarded,
  not stored.
- **Accepted video container and codec.** Not specified by the API.
- **API terms of service.** `LICENSE` (Apache-2.0) covers the SDK source in this repository. It is
  not a grant of rights to the hosted service.
- **Where to get integration help.** For security issues, `security@orilife.io`
  ([SECURITY.md](SECURITY.md)). For everything else, open an issue in this repository.

---

## Read next

- [CONTRACT.md](CONTRACT.md) — the full API contract: every endpoint, every field, every error shape
- [VERIFY.md](VERIFY.md) — independent verification, including the by-hand procedure
- [SECURITY.md](SECURITY.md) — token handling, and what must never be shipped inside an app
- [examples/](examples/) — runnable examples: `identify.py`, `verify.py`, `agent.py`, `browser.html`

---

Apache-2.0. Evidence is anchored on Cardano; records and images are stored on LampNet, a
content-addressed distributed store (see [VERIFY.md](VERIFY.md), "By hand, no SDK").
