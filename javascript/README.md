# @orilife/sdk

Identify **individuals** — not "this is a durian tree" but "this is **tree 47** in this orchard".
From photographs alone. No tags, no QR codes, nothing attached to the object.

This package is what you need to write an application that talks to OriLife, and it is also what
anyone else needs to **verify** what OriLife says without having to trust OriLife.

```
Base URL   https://api.orilife.io
Docs       https://api.orilife.io/docs   ·   https://api.orilife.io/openapi.json
Endpoints  https://api.orilife.io/api    ·   the index this SDK reads for supports()
```

Runs on browsers, Node 18+, Deno, Bun and Cloudflare Workers. No dependencies.

---

## Thirty seconds

```bash
npm install @orilife/sdk
```

```js
import { Client } from '@orilife/sdk';

const client = new Client();
await client.login('my_orchard', 'durian.orchard.2026');

const out = await client.identifyTree([file], { lat: 10.762, lon: 106.660 });
console.log(out.decision);
```

Without any SDK at all — the API is plain HTTP:

```bash
curl -X POST https://api.orilife.io/api/identify \
  -H "Authorization: Bearer $TOKEN" \
  -F 'files=@photo.jpg' -F 'lat=10.762' -F 'lon=106.660'
```

### One endpoint for every kind, where the server has it

`POST /api/identify/auto` takes a photo, works out whether it is a tree, a fruit or an animal, and
identifies it in the same call — so your app never has to ask the user what they are photographing.
Pushing that decision onto a person because the machine will not make it is exactly the shape
OriLife exists to break.

It is not on every server yet, so ask before you call it. This SDK never falls back to another
endpoint on its own: changing behaviour in silence is a worse failure than an error.

```js
if (await client.supports('/api/identify/auto')) {
  const out = await client.identifyAuto([file], { lat: 10.762, lon: 106.660 });
  console.log(out.kind, out.result.decision);
}
```

`supports()` reads the endpoint index at `GET /api` once, then answers from memory.

---

## Two halves, and the second one is the one that matters

```js
import { Client } from '@orilife/sdk';          // call the API — you are TRUSTING OriLife
import * as verify from '@orilife/sdk/verify';  // verification — you trust NOBODY
```

`Client` asks the server and repeats the answer. If the only way to know a record is real were to
ask the very server that created it, the system would prove nothing — it would just be repeating
its own claim.

`verify` is the way out of that loop. It recomputes the hash from the record itself and compares it
with the number anchored on Cardano. No network, no dependencies, no need for OriLife to be around:

```js
import * as verify from '@orilife/sdk/verify';

const record = await (await fetch('record.json')).json();   // from wherever you got it
const onchain = '3f0a…';                                     // read off a block explorer

verify.verifyRecord(record, onchain);   // true means nobody has touched this record
```

The same arithmetic runs in Python, and both are checked against the **same** vector set generated
by the code running in production. Two independent implementations agreeing is stronger evidence
than one implementation checking itself.

---

## What can be identified

| Kind | Enrol | Identify again | State |
|---|---|---|---|
| Tree | `enrollTree()` | `identifyTree()` · `identifyTreeVideo()` | In use in the field |
| Fruit | `enrollFruit()` · `addFruitView()` | `identifyFruit()` · `lookupFruit()` | In use in the field |
| Animal | `enrollAnimal()` | `identifyAnimal()` · `scanAnimal()` | Working; still needs `species` and `farmId` |
| Flowers, processed goods | — | — | **No lane yet** |

Do not copy this table into your app. `GET /api/health` returns `features`, generated from the
server's real routing table; a hand-copied list of capabilities is right for exactly one day.

---

## Two doors

**The public door — no account.** For buyer-facing apps: someone photographs a fruit on display, or
reads a code off a slip, and traces where it came from.

```js
const anon = new Client();
await anon.lookupFruit(file);                    // one fruit photo → public candidates
await anon.resolve('ORI-w3gv5j2-A7K9PQ2M');      // look up one code
await anon.treeByCode('ORI-w3gv5j2-A7K9PQ2M');   // provenance from the printed code
await anon.speciesCatalog();
await anon.health();
```

**The owner door — needs a token.** Enrol, identify, keep a care log, anchor evidence. Each account
only matches **within its own orchard** — that is privacy and accuracy at once, since two trees of
the same species in two provinces never get the chance to be confused.

Account rules, worth reading before the first call: usernames are 3–32 characters, **lowercase
letters, digits, dots and underscores** — no hyphens. Passwords are at least 10 characters, use at
least two character classes, and must not be a common password. Tokens live 12 hours.

```js
await client.signup('my_orchard', 'durian.orchard.2026');

const { farm } = await client.createFarm('Bay orchard', { lat: 10.762, lon: 106.660 });
await client.enrollTree(files, { name: 'tree 47', farmId: farm.farm_id });
await client.listTrees({ farmId: farm.farm_id });
```

---

## The full surface

**Session** — `signup` · `login` · `me` · `logout` · `logoutAll`

**Public** — `health` · `describe` · `endpoints` · `supports` · `speciesCatalog` · `resolve` ·
`treeByCode` · `lookupFruit`

**Identify** — `identifyAuto` · `identifyTree` · `identifyTreeVideo` · `identifyFruit` ·
`identifyAnimal` · `scanAnimal` · `identifyKind`

**Enrol** — `enrollTree` · `verifyAdd` · `listTrees` · `enrollFruit` · `addFruitView` ·
`enrollAnimal` · `listAnimals`

**Orchards** — `createFarm` · `listFarms` · `getFarm` · `updateFarm` · `deleteFarm`

**Telling the system it was wrong** — `submitVerdict` · `submitFruitVerdict` · `submitAnimalVerdict`

**Capture guidance** — `capturePlan`

**Evidence** — `provenance` · `timeline` · `proof` · `addEvent` · `anchorEvent`

Two of these deserve a paragraph rather than a slot in a list.

**`capturePlan(entityType, entityId)`** says what is still missing and what to photograph next.
Call it when the capture screen opens, and again right after a rejected attempt: it turns "not good
enough" into something the person holding the phone can actually do.

**`submitVerdict(queryId, verdict, { correctTreeId })`** is the call every integration is tempted to
skip, and the one that pays. A "no" with the right answer attached is how the gallery learns which
individuals look alike; a silent "no" teaches nothing.

```js
const out = await client.identifyTree(files, { lat, lon });
// … the user says it is actually tree 47 …
await client.submitVerdict(out.query_id, 'wrong', { correctTreeId: 't-47' });
```

---

## Three things to know before the first line of code

**Read the capabilities, do not hard-code them.** `health()` returns `features`; `supports(path)`
answers for one endpoint. An app that asks works the day the server gains a capability, with no
release of its own.

**"Not sure" is a result, not an error.** The system answers `uncertain` instead of guessing. Do not
retry, do not spin a wheel — ask the person, or invite one more angle.

**`unknown` from `resolve()` comes with no reason, on purpose.** If "wrong code" answered differently
from "real but private", anyone scanning codes could count someone else's orchard. There is no
difference to read.

---

## Errors

Each status code is its own class, because an app has to handle them in genuinely different ways.

| Code | Class | What the app should do |
|---|---|---|
| — | `NetworkError` | The request may **never have arrived**. Read endpoints: call again. Write endpoints: ask for the current state first |
| 400 · 422 | `InvalidRequestError` | Missing field or rule not met. Show `message` to the user |
| 401 | `AuthError` | Token expired. Sign in again and retry |
| 403 | `PermissionError` | Not allowed. A new token does **not** help |
| 404 | `NotFoundError` | Do not write "does not exist" on screen — see `unknown` above |
| 413 | `TooLargeError` | Compress and resend; do not retry unchanged |
| 429 | `RateLimitedError` | Wait `retryAfter` seconds. This package already waits for you |
| 5xx | `ServerError` | Retry with widening gaps — but only read endpoints |

The `message` is the sentence the server already wrote for the end user (Vietnamese today, since
that is who is standing in the orchard). **Show that sentence**; do not translate status codes into
wording of your own — the server knows the context, your app does not.

Write endpoints are never resent automatically: a request that failed midway may already have
created the record.

---

## Limits

| | |
|---|---|
| One file | 20 MB |
| One batch of images | 64 MB |
| Video | 80 MB |
| Token lifetime | 12 hours |
| Too fast | `429` with a `Retry-After` header |

The cap is counted while the bytes are still going up, so `413` comes back **before** the upload
finishes — you do not spend the whole bandwidth to find out it failed.

---

## Browsers, bots and agents

CORS is open to every origin with cookies **off** for cross-origin calls. Any web page can call the
API, and no page can borrow a user's session: the token has to ride in an `Authorization: Bearer`
header, and the whole class of CSRF bugs disappears with the cookie.

Two descriptors exist for machines — `GET /.well-known/orilife.json` (what the service offers) and
`GET /llms.txt` (a one-page map for language agents). Neither is on every server: ask
`supports('/.well-known/orilife.json')` before you rely on them. `GET /openapi.json` is always
there.

Working example in a page, no build step: [examples/browser.html][examples].

---

## What is in this repository, and what deliberately is not

**Here:** the API clients (Python, JavaScript), the independent verifier, the API contract, runnable
examples.

**Not here:** the recognition itself. How the machine decides that two photographs show the same
individual stays on the server.

That boundary was not invented for this repository — it already exists at the server's response
layer: the details behind a match do **not** leave the API. Your app receives a `decision` and a
coarse confidence, not the internals. Two reasons, and the second matters more than the first: the
internals would let a competitor copy the work, and they would let a forger turn the system into a
tester to poke at until something gets through.

Everything **outside** that boundary is open, including the entire verification path — the one
thing you need in order to catch OriLife lying. Everything **inside** stays closed.

---

## Running the tests

```bash
cd javascript && node --test          # nothing to install
```

The verification tests check against the same vector set as the Python build
(`contract/vectors.json`), generated by the code running on the server.

---

## Read on

- [CONTRACT.md][contract] — the full API contract: every endpoint, every field, every error shape
- [VERIFY.md][verifydoc] — independent verification, including how to redo it by hand without this SDK
- [SECURITY.md][security] — holding tokens, and what must never be embedded in an app
- [examples/][examples] — runnable examples

---

Apache-2.0. Evidence anchored on Cardano, data stored distributed on LampNet.

[contract]: https://github.com/OriLifeTrace/OriLife-SDK/blob/main/CONTRACT.md
[verifydoc]: https://github.com/OriLifeTrace/OriLife-SDK/blob/main/VERIFY.md
[security]: https://github.com/OriLifeTrace/OriLife-SDK/blob/main/SECURITY.md
[examples]: https://github.com/OriLifeTrace/OriLife-SDK/tree/main/examples
