# API contract

The complete, always-current specification is `https://api.orilife.io/openapi.json`, generated
from the running code. This page carries what a specification file cannot: which endpoint to use
when, where people misread the shapes, and what the system **deliberately refuses to answer**.

Base URL: `https://api.orilife.io`

Everything below was checked against the running server implementation on 2026-08-20. Where a
value could not be confirmed in code, it is marked **unconfirmed** rather than guessed.

**Contents** — [1. Authentication](#1-authentication) · [2. Farms](#2-farms) ·
[3. Identify](#3-identify) · [4. Enrollment](#4-enrollment) · [5. Feedback](#5-feedback) ·
[6. Capture plan](#6-capture-plan) · [7. Evidence](#7-evidence) · [8. Public lane](#8-public-lane) ·
[9. Errors](#9-errors) · [10. Limits](#10-limits) ·
[11. Sharing read access](#11-sharing-read-access) ·
[12. Discovery and availability](#12-discovery-and-availability) ·
[13. What the system will not answer](#13-what-the-system-will-not-answer) ·
[14. SDK method map](#14-sdk-method-map)

---

## 1. Authentication

| Endpoint | Purpose |
|---|---|
| `POST /api/signup` | Open an account. JSON body `{username, password}` |
| `POST /api/login` | Get a token. JSON body `{username, password}` |
| `POST /api/logout` | Drop the current token |
| `POST /api/logout-all` | Drop **every** token of the account — use when you suspect a leak |
| `GET /api/me` | Who is logged in |
| `GET /api/auth/did/challenge` → `POST /api/auth/did/verify` | Sign in with a PhoenixKey identity key, no password |

The token travels in the header: `Authorization: Bearer <token>`. It lives **12 hours**; after
that, endpoints return `401`.

Account rules — the first thing almost every integration gets wrong:

- Username **3-32 characters**, lowercase letters, digits, dot and underscore only. **No hyphen.**
  `my-orchard` is rejected; `my_orchard` is accepted.
- Password at least **10 characters**, at least **two character classes**, not on the common
  password list.
- A violation returns `400` with a sentence naming the exact problem. Show that sentence.

There is **no sandbox tier**: `signup` creates a real account on the production host, and anything
you enroll is real data. `GET /api/account/data` previews everything an account owns;
`POST /api/account/delete` erases it (it requires re-typing the owner code).

**Browser apps: use Bearer, not cookies.** CORS is open to every origin but cross-origin cookies
are not sent, so the cookie path only works same-origin.

### About PhoenixKey

PhoenixKey is a separate decentralised-identity system. The DID endpoints let a holder of a
PhoenixKey identity key prove control of that key (challenge, then signature) instead of sending a
password. **If you do not already have a PhoenixKey identity, use username and password** — that is
the ordinary path and every example in this repository uses it. Obtaining a PhoenixKey identity is
outside the scope of this SDK, and the challenge/response payload shapes are **unconfirmed** here;
read them from `/openapi.json` on the server you target.

---

## 2. Farms

A farm is a real entity: a growing area with an owner, optionally a boundary. One account may own
many farms. **This is where every `farm_id` in this document comes from.** You never invent one.

Ownership is taken from your token, never from the request body, and every per-farm route is
owner-guarded: a farm that is not yours answers `403` with the same message as a farm that does not
exist.

| Endpoint | Purpose |
|---|---|
| `POST /api/farm` | Create |
| `GET /api/farms` | List every farm this account owns |
| `GET /api/farm/{farm_id}` | One farm, plus the trees and animals inside it |
| `POST /api/farm/{farm_id}/update` | Change fields (send only what changes) |
| `DELETE /api/farm/{farm_id}` | Delete the farm |

### `POST /api/farm`

Form fields:

| Field | Required | Notes |
|---|---|---|
| `name` | yes | Trimmed; empty after trimming → `400` |
| `kind` | no | Free-form label for the kind of growing area |
| `boundary_json` | no | JSON string, `[[lat,lon],...]` |
| `center_json` | no | JSON string, `[[lat,lon]]` |
| `boundary_method` | no | How the boundary was obtained: `gps_walk`, `map_draw`, `mixed`. Anything else is recorded as `unknown` |
| `boundary_acc_m` | no | Median GPS accuracy in metres, as a string. Non-numeric is discarded rather than rejected |
| `note` | no | Free text |

Returns `{"ok": true, "farm": {...}}`. The server computes area, perimeter and boundary warnings
and returns them inside `farm`; do not compute your own and send them — derived fields are
recalculated server-side on every response and client-supplied values are ignored.

Why `boundary_method` exists: a boundary **walked** on the ground and a boundary **drawn** on a map
are not the same evidence, and traceability consumers need to tell them apart.

### `GET /api/farms`

Returns `{"ok": true, "farms": [...]}`. Each farm carries `counts` with `n_trees` and `n_animals`.
Only your own farms appear.

### `GET /api/farm/{farm_id}`

Returns `{"ok": true, "farm": {...}, "trees": [...], "animals": [...]}`. Each tree carries its
public code and flags for 3D and anchoring, matching the shape from `GET /api/trees`.

If the animal subsystem is not loaded on that server, `animals` comes back as `[]` rather than
failing the whole call.

### `POST /api/farm/{farm_id}/update`

Same fields as create, all optional; **only fields you send are changed.** Sending `name` as an
empty string is an error (`400`), not a way to clear it.

One trap worth stating: if you change `boundary_json` **without** also sending `boundary_method`,
the server resets the boundary provenance to `unknown` and clears the accuracy figure. A new
boundary does not inherit the old boundary's origin story. Send the method with the boundary.

### `DELETE /api/farm/{farm_id}`

Deletes **only the farm**. Trees inside it are kept and become unassigned (`farm_id` becomes null);
they remain fully traceable. Any read-access grants scoped to that farm are revoked at the same
time — a grant does not outlive the thing it was granted on.

Animals keep their recorded `farm_id`; the animal store is independent and is not cleaned up by
this call.

---

## 3. Identify

### Per-kind endpoints

| Endpoint | File field | Notes |
|---|---|---|
| `POST /api/identify` | `files[]` | Several angles are markedly better than one photo |
| `POST /api/identify/video` | `file` | Walk once around the tree. The clip is **not** stored |
| `POST /api/fruit/identify` | `file` | `tree_id` narrows the search to one tree; omit it to search the whole holding |
| `POST /api/animal/identify` | `image` | Requires `species` and `farm_id` |
| `POST /api/animal/scan` | `image` | Requires `farm_id`; `species` optional |
| `POST /api/kind` | `file` | Asks only *what am I looking at*; does not identify |

Tree identify response:

```json
{
  "ok": true,
  "decision": "MATCH",
  "tree_id": "...",
  "name": "Tree 47",
  "query_id": "...",
  "confidence": "cao",
  "allow_enroll_new": true,
  "needs_location_update": false,
  "warnings": [],
  "candidates": [ { "tree_id": "...", "name": "...", "relation": "owner" } ]
}
```

### `decision` — the complete set

This is the field to branch on. Values are uppercase ASCII tokens and are stable.

| Value | Meaning | Returned by |
|---|---|---|
| `MATCH` | Recognised as a known individual | tree, tree video, fruit, animal |
| `UNCERTAIN` | Candidates are too close to call; the system refuses to guess | tree, tree video, fruit, animal |
| `NO_MATCH` | Not recognised as anything on file | tree, tree video, fruit, animal |
| `MOVED` | Recognised, but not where it was last seen | tree, tree video, animal |
| `EMPTY_BUCKET` | Nothing comparable on file yet | tree, tree video |
| `EMPTY_GALLERY` | Nothing comparable on file yet | fruit |
| `EMPTY_FARM` | The farm has no enrolled animals yet | animal |
| `NO_FRAMES` | No usable frame could be taken from the clip | tree video only |

Notes that save debugging time:

- `MOVED` does **not** occur on fruit endpoints. `EMPTY_BUCKET`, `EMPTY_GALLERY` and `EMPTY_FARM`
  are the same idea named per kind — they are never interchangeable, so match on all three if you
  write one shared handler.
- `NO_FRAMES` arrives with HTTP **422** and `ok: false`, not `200`. The rest of the identify shape
  (`decision`, `candidates`, `allow_enroll_new`) is still present so your parser does not break,
  and `reason` says why frame selection failed.
- Treat an unrecognised `decision` value as `UNCERTAIN`: ask the person. Do not treat it as a match.

### The other fields

- `confidence` is a **coarse band**, not a number. The server returns one of three literal strings:
  `"cao"` (high), `"vừa"` (medium), `"thấp"` (low) — Vietnamese words used as opaque tokens. Compare
  them as exact strings if you must, but do not build decision logic on them: the decision is
  already in `decision`.
- `allow_enroll_new` is a flag to **read directly**, never to infer from `decision`. It opens the
  "this is none of them, create a new one" path.
- `query_id` — keep it. Send it back through the feedback endpoints ([section 5](#5-feedback)) when
  you learn whether the answer was right. That is how the system learns from the field, and it is
  the cheapest contribution an integrator can make.
- `needs_location_update` is true when the individual is on file without usable coordinates.
- `warnings` carries capture-quality advice as strings; safe to show.
- `candidates[].relation` is `owner`, `granted` or `public`:
  - `owner` — your own individual.
  - `granted` — someone else's individual that they gave your account read access to; see
    [section 11](#11-sharing-read-access).
  - `public` — the owner has published it.
  Distance and day counts appear **only** for individuals you may read privately. They are withheld
  otherwise so that nobody can triangulate a stranger's orchard from a series of queries.

Responses may carry fields beyond this list. **Forward them verbatim and do not build decision
logic on them** — they are measurement data, their shape may change, and this SDK deliberately does
not interpret them.

### `POST /api/identify/auto` — availability first

One call for any kind: send photos, the server works out whether it is a tree, a fruit or an
animal, and identifies it. Your app **does not have to ask the user what they are photographing**.

It is **only available on servers that list it in `GET /api`**, so check before calling. On
`https://api.orilife.io` it was absent on 2026-08-20 and present on 2026-09-08 — nineteen days, and
nothing announced the change. Guard the call rather than trusting either measurement:

```python
if client.supports("/api/identify/auto"):
    out = client.identify_auto(["photo.jpg"], lat=10.762, lon=106.660)
else:
    out = client.identify_tree(["photo.jpg"], lat=10.762, lon=106.660)
```

Where it exists, the shape is:

```json
{
  "ok": true,
  "kind": "tree",
  "kind_need_confirm": false,
  "lane": "/api/identify",
  "result": { "...": "verbatim response of the endpoint that ran" },
  "message": "sentence for the end user, in Vietnamese"
}
```

- `result` is the **verbatim** response of the endpoint that ran — no fields dropped, no renaming.
  Its shape is the per-kind shape documented above.
- `kind` is `tree`, `fruit`, `animal`, or `null` when the server cannot tell. When it is `null`,
  `result` is `null` too: the system says "I do not know" instead of filing it somewhere arbitrary.
- `kind_need_confirm = true` means show `kind` as a **suggestion** the user can change, rather than
  jumping straight into that flow.
- Animals: the target endpoint still requires `species` and `farm_id`. Without them, `result` is
  `null` and `need` names the missing fields. The server **will not guess a species** — a guessed
  species would be written into an individual's permanent record with nobody able to check it.
- If the target endpoint refuses (`413`, `429`, `400`), that status and any `Retry-After` header
  come through **unchanged**; they are not wrapped into a `200`.

If you already know the kind, call the per-kind endpoint directly and skip a step.

---

## 4. Enrollment

| Endpoint | Purpose |
|---|---|
| `POST /api/enroll` | New tree: `files[]` · `name` · `lat?` · `lon?` · `farm_id?` · `species?` |
| `POST /api/verify_add` | Confirm it was the right tree, then add angles: `tree_id` · `files[]` |
| `POST /api/fruit/enroll` | New fruit: `images` · `tree_id` · `name?` · `bbox?` |
| `POST /api/fruit/add_view` | Add angles to a fruit: `fruit_id` · `images` |
| `POST /api/animal/enroll` | New animal: `images` (three or more angles) · `species` · `farm_id` · `name?` · `owner_did?` |
| `GET /api/animal/list` | Animals, filtered by `farm_id` / `species`, with `limit` / `offset` |

`POST /api/enroll` returns `{"ok": true, "tree_id": "...", "n_views_added": N, ...}`.

These are **write** endpoints. Calling again after a network drop can create a second record, so
the SDK **does not retry them automatically**. Catch `NetworkError`, ask for the current list, and
only then resend.

Profiles getting thicker over time is how the system gets stronger: one `verify_add` after each
correct identification is worth far more than many angles captured in a single session.

---

## 5. Feedback

Tell the system whether it was right. This is the only way field experience turns into future
accuracy, and it costs one call.

| Endpoint | Form fields |
|---|---|
| `POST /api/identify_verdict` | `query_id` · `verdict` · `correct_tid?` |
| `POST /api/fruit/identify_verdict` | `query_id` · `verdict` · `correct_fruit_id?` |
| `POST /api/animal/identify_verdict` | `query_id` · `verdict` · `correct_did?` |

`verdict` values:

| Value | Meaning | Accepted by |
|---|---|---|
| `correct` | The top answer was right | tree, fruit, animal |
| `wrong` | It was wrong; if you know the right one, send it in the `correct_*` field | tree, fruit, animal |
| `other` | It is a different individual (name it via `correct_*`), or an unknown one if you cannot | tree, fruit, animal |
| `unknown_ok` | The individual was never enrolled and the system correctly said it did not know | animal only |

An unrecognised `verdict` returns `400` naming the accepted set. A `correct_*` identifier that does
not belong to your account is **silently dropped** — the label is discarded, no `403` is raised,
because this is measurement data, not a resource access.

---

## 6. Capture plan

`GET /api/capture/plan` — what is missing and what to photograph next, with the same response shape
for every kind it accepts, so a single screen can serve all of them.

Query parameters: `target_type`, `target_id`, and optionally `after_reject` if you are calling right
after a rejected attempt (it turns a refusal into a task).

**`animal` is UNRESOLVED — do not build on it.** `target_type` is `tree` or `fruit` for certain. An
earlier revision of this page listed `animal` as a third value; the server team's own endpoint
contract restricts the parameter to `tree|fruit`; and `/openapi.json` types it as a plain string,
which settles nothing either way. Nobody has measured it against a live account. Until somebody
does, treat `animal` as unsupported and handle the `422` — guessing in the permissive direction
means shipping a capture screen that dies in an orchard.

Returns `{"ok": true, "target_type": ..., "target_id": ..., "after_reject": ..., ...plan}`. The plan
carries `have_kind`, which tells you how to read `have`: `"faces"` for fruit (counted per face) or
`"coverage"` (counted per photo).

Only objects belonging to the logged-in account are visible. An unaccepted `target_type` returns
`422`.

---

## 7. Evidence

| Endpoint | Purpose |
|---|---|
| `GET /api/provenance/{tree_id}` | Code, image addresses, record address, record hash, anchor status |
| `GET /api/{entity_type}/{id}/timeline` | Hash-chained event history |
| `POST /api/{entity_type}/{id}/event` | Append one event: `kind` plus optional `data` |
| `GET /api/{entity_type}/{id}/proof/{event_id}` | Merkle audit path for one event |
| `POST /api/{entity_type}/{id}/event/{event_id}/anchor` | Anchor the current chain root on Cardano (owner only) |
| `POST /api/animal/trust/verify-inclusion` | Check a record belongs to an anchored root — open to anyone |

`entity_type` is one of `tree`, `fruit`, `farm`, `animal`, `plot`.

`GET /api/provenance/{tree_id}` and `GET /api/tree_by_code/{code}` are **public-only surfaces**:
they serve an individual whose owner has published it, and return `404` otherwise — including when
you are the owner and holding a valid token. If you get `404` on your own tree, publish it first
(`POST /api/tree/set_visibility`). This is not an accident: the same code is printed on labels, and
a private individual must be indistinguishable from a non-existent one.

The proof response is `{"ok": true, "root": "...", "leaf_hash": "...", "proof": [...], "anchor": ...}`.
`proof` is an audit path of `{hash, side}` steps. `anchor` is present when the current root has
already been confirmed on chain, which is what closes the loop between a local proof and an
immutable transaction.

Proofs are issued only for events the caller is allowed to see, but the tree is always built from
the **full** chain so that the root matches the one anchored on chain. The path therefore exposes
sibling hashes and nothing else — you cannot count someone's private events from it.

How to check all of these yourself, without trusting OriLife: [VERIFY.md](VERIFY.md).

---

## 8. Public lane

No account required.

| Endpoint | Purpose |
|---|---|
| `POST /api/fruit/lookup` | Photo of one fruit → candidates within the public set |
| `POST /api/fruit/scan` → `POST /api/fruit/scan/choose` | Counter-side scanning flow |
| `GET /api/resolve/{code}` | Look up an `ORI-...` code |
| `GET /api/tree_by_code/{code}` | Provenance of one tree by its printed code |
| `GET /api/species/catalog` | Species and activity catalogue |
| `GET /api/health` | Liveness plus a `features` list generated from the real routing table |
| `GET /api` | Index of every endpoint this server serves |

`GET /api/resolve/{code}` answers in one of three states — note the status codes differ:

| HTTP | Body | Meaning |
|---|---|---|
| `200` | `{"ok": true, "state": "public", "kind": ..., "url": ..., "provenance": {...}}` | Real, and the owner has published it |
| `200` | `{"ok": true, "state": "restricted", "kind": ..., "card": {...}?}` | Real, not published; you get a minimal card at most |
| `404` | `{"ok": false, "state": "unknown", "error": "..."}` | Not resolvable |

`unknown` carries **no reason**, deliberately. If "bad code" answered differently from "real but
private", anyone probing codes could enumerate other people's holdings. There is no difference to
infer.

The public gateway is rate-limited separately and returns `429` with `retry_after` and a
`Retry-After` header.

---

## 9. Errors

One shape for every 4xx/5xx:

```json
{ "ok": false, "error": "sentence for the end user, in Vietnamese", "detail": "..." }
```

`429` additionally carries `retry_after` in the body and a `Retry-After` header.

| Status | Meaning | What your app should do |
|---|---|---|
| 400 · 422 | Missing field, wrong type, rule violation | Show `error` to the user |
| 401 | Not logged in, or the token expired | Log in again, then retry |
| 403 | Not permitted | A fresh token does **not** help |
| 404 | Not found | Do not print "does not exist" — see [section 8](#8-public-lane) |
| 413 | Over a limit | Compress; do not retry unchanged |
| 429 | Too fast | Wait exactly `Retry-After` seconds |
| 5xx | The other side broke | Retry with backoff, read endpoints only |

**`200` with `ok: false` is a real case.** It means "the job could not be done", not "the request
was malformed", and your app must read `ok` rather than the status code alone. Confirmed cases:

| Endpoint | When | Extra fields |
|---|---|---|
| `POST /api/fruit/detect` | The species is not one that bears detectable fruit, or the detector is unavailable on this server | `reason`: `species_no_fruit`, `species_detector_missing` |
| `POST /api/fruit/add_view` | The submitted view looks more like a different fruit than the one you named | `warn`, `best_other` |
| `POST /api/rename`, `POST /api/animal/rename` | The new name is empty after trimming | `error` |

Other endpoints may do the same; this list is what could be confirmed in the server code on
2026-08-20, not an exhaustive enumeration. Read `ok` everywhere.

Separately, `POST /api/identify/video` returns HTTP **422** with `ok: false` and
`decision: "NO_FRAMES"` when no usable frame can be taken from the clip.

---

## 10. Limits

| | |
|---|---|
| One file | 20 MB |
| One batch of images in a single call | 64 MB |
| Video | 80 MB |
| Token lifetime | 12 hours |

Limits are enforced **while bytes are still arriving**, so `413` comes back before the upload
completes — someone on a weak signal does not have to spend the whole file to learn it failed.

The video ceiling is configurable per deployment; 80 MB is the default and the value on the public
host as measured on 2026-08-20. Accepted container and codec for video are **unconfirmed** — the
API does not specify them.

No requests-per-minute figure is published. `Retry-After` is the only authority.

---

## 11. Sharing read access

This is where `relation: "granted"` in a candidate list comes from. An owner can give **another
account** private read access to a farm or a single tree.

| Endpoint | Purpose |
|---|---|
| `POST /api/grant` | Grant: `grantee` · `scope_type` · `scope_id` · `perms` · `ttl_days?` |
| `GET /api/grants` | List grants you issued |
| `DELETE /api/grant/{grant_id}` | Revoke |
| `GET /api/account/resolve` | Look up the account identifier to put in `grantee` |

- `scope_type` is `farm` or `tree`; anything else returns `400`.
- The server verifies you actually own the scope before granting, so a grant cannot be used to
  escalate into something you do not own — otherwise `403`.
- `perms` is a comma-separated list. The store currently accepts **only `read_private`**. Anything
  else returns `400` naming the rejected permission, rather than filtering silently.
- `ttl_days` empty means no expiry.
- Deleting a farm revokes every grant scoped to it ([section 2](#2-farms)).

---

## 12. Discovery and availability

Do not hard-code capability lists. Ask:

| | |
|---|---|
| `GET /api` | `{count, docs, openapi, routes: [{path, methods, summary}]}` — generated from the live routing table |
| `GET /api/health` | Liveness, version, and a `features` list generated the same way |
| `GET /openapi.json` | Full specification |
| `GET /.well-known/orilife.json` | Service descriptor — public endpoints, limits, which kinds have routes |
| `GET /llms.txt` | One-page map for language agents |
| `GET /robots.txt` | Crawlable surface |

The SDK wraps the first of these:

```python
client.supports("/api/identify/auto")   # reads GET /api once, then answers offline
```

**Availability moves, and nothing announces it.** `POST /api/identify/auto`, `GET
/.well-known/orilife.json` and `GET /llms.txt` all answered `404` on `https://api.orilife.io` on
2026-08-20. Measured again on 2026-09-08 they answered `405` (the route exists and takes POST),
`200` and `200`. Nineteen days, no notice — and for nineteen days this page said the opposite of
what the server did.

That is the reason a sentence like this one cannot be the thing your code trusts. Design for it:

1. Anything you build on an optional endpoint must be guarded by `supports()`, or by catching
   `NotFoundError`. Never by a date written in a document.
2. The SDK **never silently substitutes** another endpoint on `404`. Changing behaviour quietly is
   a worse failure mode than a visible error.
3. `describe()` (the service descriptor) will raise `NotFoundError` on servers that do not ship it.
   That is the correct answer, not a bug.
4. `tools/check_server_drift.py` compares `contract/methods.json` against the live
   `/openapi.json` and reports **KHỚP / LỆCH / KHÔNG ĐO ĐƯỢC**. It runs in CI. That is what
   noticing looks like when it is mechanical instead of hopeful.

---

## 13. What the system will not answer

Stated so nobody spends time looking.

**The internal workings of a comparison.** Your app receives `decision` and a coarse `confidence`
band; the parameters behind the comparison do not leave the API. Exposing them lets a competitor
copy them, and — worse — turns the system into an oracle an attacker can probe until something
slips through.

**Precise coordinates of other people's individuals.** Coordinates are coarsened on the public
lane. Distances and day counts appear only for individuals you may read privately.

**Whether a private individual exists.** Private and non-existent return the same answer.

**A guess on the user's behalf.** When it is not clear, the system says `UNCERTAIN` or `unknown`.
That is a result, not an error: do not retry, ask the person or invite one more angle.

---

## 14. SDK method map

The map is **generated**, not typed: [`contract/METHODS.md`](contract/METHODS.md), produced by
`tools/generate.py` from [`contract/methods.json`](contract/methods.json). Every method in both
languages is generated from that same table, so a signature written here by hand could disagree
with the code — and there would be nothing to catch it. There is nothing to catch it *now* either,
which is why the table lives there and this section is a pointer.

`contract/methods.json` also records, per endpoint, whether a failed call is safe to send again.
That is the one policy nobody should have to re-derive by reading the code.
