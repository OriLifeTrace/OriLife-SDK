# Verify it yourself

By the end of this page you can take an OriLife record and check it **without trusting OriLife** —
and, if you want, redo every step by hand with no SDK at all, using nothing but a JSON parser, a
hash function, and a public block explorer.

A traceability system is only as trustworthy as an outsider's ability to check it. If the only way
to know a record is genuine is to ask the server that produced it, the system has proven nothing:
it is repeating its own testimony.

---

## What can and cannot be proven

| Question | Answered by | Who you must trust |
|---|---|---|
| Has this record been altered since it was anchored? | Re-hash the record, compare with the number on chain | Nobody |
| Is this image really the image in the record? | Re-hash the image bytes, compare with `sha256` in the record | Nobody |
| Does this event belong to the anchored history? | Merkle audit path | Nobody |
| Does the record accurately describe the real tree? | — | **Cannot be settled by cryptography** |

The last row is the real boundary, and it is better said out loud than discovered later. A hash
proves data has **not changed** since it was anchored. It does not prove the data was **true** when
it was created. No system does that with mathematics; that part is carried by process and by people
who are accountable.

---

## Fastest path: use the SDK

```python
import json, urllib.request
from orilife import Client, verify

prov = Client().provenance("<tree_id>")["provenance"]
# {'code': 'ORI-...', 'record_cid': '...', 'record_hash': '...',
#  'images': [{'cid': ..., 'sha256': ...}], 'anchor': {'tx_hash': ..., 'network': ...,
#  'explorer_url': ...}}

# The store is content-addressed, so any node returns the same bytes.
record = json.load(urllib.request.urlopen(f"https://lampnet.cloud/{prov['record_cid']}"))

print(verify.summarize(record, prov["record_hash"]))
# {'code': 'ORI-...', 'algorithm': 'sha3-256', 'hash_matches': True, 'missing_fields': [], ...}
```

In JavaScript:

```js
import * as verify from '@orilife/sdk/verify';
verify.summarize(record, recordHash);
```

**Do not stop there.** `prov["record_hash"]` came from the server you are trying to check — it is
still one party's testimony. Open the anchoring transaction on a block explorer and read the number
with your own eyes. `prov["anchor"]` carries `tx_hash`, `network` and `explorer_url` for exactly
that purpose.

---

## By hand, no SDK

### Step 1 — Read the number off the chain

Every anchoring is a Cardano transaction carrying metadata under **label 1454**:

```json
{
  "t":    "OriLifeTrace",
  "code": "ORI-w3gv5j2-A7K9PQ2M",
  "cid":  "<address of the record in the store>",
  "h":    "<64 hex characters — the hash of the record>",
  "a":    "sha3-256"
}
```

Field `a` names the algorithm that produced `h`. It is there so you never have to guess, and so old
records stay checkable after the system moves to a new algorithm.

An individual's **event history** is anchored separately, under **label 1455**:
`{"t": "OriLifeMerkle", "root": "<64 hex>", "n": <number of events>}` — one transaction standing
for a whole chain of events. You will use `root` in [step 5](#step-5--check-an-event-belongs-to-the-anchored-history).

Open the transaction on any Cardano explorer (`cexplorer.io`, `cardanoscan.io`) and read the
metadata. Which network to open is in `provenance.anchor.network`, and
`provenance.anchor.explorer_url` is a direct link.

One caveat worth knowing: `provenance.anchor.submitted_at` is the moment the transaction was
**submitted**, not the moment it landed in a block. The authoritative timestamp is the block's, on
the explorer.

### Step 2 — Fetch the record

`GET /api/provenance/{tree_id}` returns `record_cid`, the address of the record inside the store.
Fetch it:

```
https://lampnet.cloud/<record_cid>
```

**What that store is:** LampNet is a distributed, content-addressed store. "Content-addressed" means
an item's address is derived from its own bytes, so a wrong or altered file cannot sit at the right
address. That is why you do not have to trust any particular node: fetch from whichever one you
like, and check the bytes against the record yourself. Images live in the same place, addressed by
`images[i].cid`.

This endpoint only serves individuals whose owner has published them — **including when the caller
is the owner**. A private individual and a non-existent one both return **404**, deliberately, so
that probing codes cannot be used to count somebody else's holdings. If you are verifying your own
tree and get a `404`, publish it first.

### Step 3 — Recompute the hash

Serialise the record under exactly these three rules, then hash it with the algorithm named in `a`:

1. **Keys sorted** by Unicode code point, at every level.
2. **No extra whitespace** — separators are exactly `,` and `:`.
3. **Non-ASCII characters kept as they are.** Record values are often written in Vietnamese; a
   value such as `"name": "cây 47"` must stay literal in the bytes you hash, not be escaped into
   `"cây 47"`.

In plain Python, nothing to install:

```python
import hashlib, json

canonical = json.dumps(record, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False).encode("utf-8")
print(hashlib.sha3_256(canonical).hexdigest())      # must equal field "h" on chain
```

The same in Node, no dependencies:

```js
import { createHash } from 'node:crypto';

const canonical = JSON.stringify(sortKeysDeep(record));   // sorted keys, no spaces
console.log(createHash('sha3-256').update(canonical, 'utf8').digest('hex'));
```

Older records (before 2026-08) have no `hash_alg` field and use `blake2b` with a **32-byte** output:

```python
hashlib.blake2b(canonical, digest_size=32).hexdigest()
```

> Truncating BLAKE2b-512 to 32 bytes does **not** produce this value. BLAKE2b mixes the output
> length into its initialisation vector, so those are two different hash functions. This is where an
> implementation built on `openssl blake2b512` goes wrong — and it goes wrong in the alarming
> direction, reporting "tampered" for a perfectly intact record.

### Step 4 — Check the images

Every image entry in the record carries a `sha256` field. Download the bytes, hash them, compare:

```python
hashlib.sha256(open("downloaded.jpg", "rb").read()).hexdigest()
```

Note the deliberate gap: the SDK does **not** try to rebuild the storage address from the bytes.
Content addresses have several format versions, and guessing the wrong version reports "invalid"
for a perfectly good file. A false alarm inside a verifier is worse than no verifier at all,
because it teaches people to ignore warnings. Compare against `sha256`, which is unambiguous.

### Step 5 — Check an event belongs to the anchored history

`GET /api/{entity_type}/{id}/proof/{event_id}` returns:

```json
{
  "ok": true,
  "root": "<64 hex>",
  "leaf_hash": "<64 hex>",
  "proof": [ {"hash": "<64 hex>", "side": "left"}, {"hash": "...", "side": "right"} ],
  "anchor": { "tx_hash": "...", "network": "..." }
}
```

The tree follows **RFC 6962**:

- leaf = `SHA-256(0x00 || canonical_json(leaf_record))`
- internal node = `SHA-256(0x01 || left || right)`
- the leaf record is exactly `{"event_id": ..., "leaf_hash": ...}`, canonicalised by the same three
  rules as step 3
- the tree is **not** padded to a power of two: the left branch takes the largest power of two
  strictly smaller than the number of leaves. (This only matters if you rebuild the whole tree; to
  check one audit path you just fold the steps.)

Fold the path and compare with the root:

```python
import hashlib, json

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")

def leaf(rec):        return hashlib.sha256(b"\x00" + canonical(rec)).digest()
def node(left, right): return hashlib.sha256(b"\x01" + left + right).digest()

resp  = ...                      # the JSON above
event = ...                      # the same event, from GET .../timeline

cur = leaf({"event_id": event["event_id"], "leaf_hash": event["leaf_hash"]})
for step in resp["proof"]:
    sibling = bytes.fromhex(step["hash"])
    cur = node(sibling, cur) if step["side"] == "left" else node(cur, sibling)

print(cur.hex() == resp["root"])          # True: the event is in that tree
```

Then compare `resp["root"]` with the `root` in the **label 1455** metadata of the anchoring
transaction (step 1). Matching both closes the loop: the event is in a tree whose root was written
to a public blockchain at a time nobody controls.

> **Never feed a bare 64-hex string in as if it were a leaf.** Internal nodes are also 64 hex
> characters, and a hex string does not say whether it was built with the `0x00` prefix or the
> `0x01` one. A verifier that accepts a hex string as a leaf lets an attacker pass an internal node
> off as a "valid leaf" and prove membership for something that was never an event. Always start
> from the record and always apply the `0x00` prefix — which is what the snippet above does.

**Optional, one level deeper:** `leaf_hash` itself is `blake2b` with a 32-byte output over the
canonical event body with `leaf_hash` removed and `prev_hash` kept. Recomputing it lets you verify
the event content too, not just its membership. One caveat: that canonicalisation also normalises
numbers (floats round-tripped through their shortest representation), so an event carrying floating
point values needs the same normalisation before you will match. Events chain by `prev_hash`, so
altering an event in the middle of a history breaks every hash after it.

---

## When a check fails

Failure is a diagnosis, not a verdict. Read it in this order:

| Symptom | Most likely cause |
|---|---|
| Record is **missing fields** and the hash differs | A truncated download or the wrong object — refetch before concluding anything |
| Record is **complete** and the hash differs | The genuinely alarming case. Recheck your serialisation (steps 1-3 of the canonical rules) once, then treat it as a discrepancy worth raising |
| Hash differs only for **old** records | You are hashing with `sha3-256` where the record calls for `blake2b` with a 32-byte output |
| Hash differs by a **whole different value** every run | Your JSON library is reordering keys, adding a space after `:`, or escaping non-ASCII characters |
| The audit path does not fold to the root | You started from a hex string instead of the record, or you swapped the meaning of `side` |

`summarize()` separates the first two cases for you through its `missing_fields` field. Any tool
that merges them will produce false alarms, and false alarms in a verifier are worse than no
verifier — they teach people to ignore warnings.

---

## Three ways to get this wrong

**Changing the declared algorithm does not help an attacker.** The `hash_alg` field lives **inside**
the hashed content. Editing it to force a weaker hash also changes the content, so the hash stops
matching. That is precisely why the field belongs in the record rather than beside it.

**An unknown algorithm must be rejected, never defaulted.** The verifier here returns false when it
meets an algorithm name outside its allow-list. Falling back to a default would open the very door
that self-declared algorithms were introduced to close.

**A missing field is not a modified field.** Handle them separately; see the table above.

---

## Entity codes

The code printed on a label has the form `ORI-<geohash7>-<8 characters>`:

- **geohash7** — a grid cell of roughly 150 m. Enough to say "which area", **not** enough to point
  at one trunk. That is intentional: a public code must not walk a stranger to somebody's orchard.
- **8 characters** — Crockford base32 of `blake2b(entity identifier, 8 bytes)`. The Crockford
  alphabet drops `I`, `L`, `O` and `U` so that a human reading a code aloud cannot confuse them
  with `1` and `0`.
- With no coordinates, the middle segment is seven zeros. The code still works; it just carries no
  area hint.

```python
from orilife import verify
verify.entity_code("<entity_id>", [10.762622, 106.660172])
```

```js
import * as verify from '@orilife/sdk/verify';
verify.entityCode(entityId, [10.762622, 106.660172]);
```

Codes are for **cross-checking**: take the code printed on a label, call this with the identifier
the server returns, and the two strings must match. A mismatch means one of the two ends changed.

The code function uses **blake2b**, while record hashing uses whatever the record declares. That
difference is deliberate. Codes are already printed on paper and already embedded in the metadata of
every past anchoring transaction, so they can never change; the record hash, by contrast, needs an
upgrade path. Anyone who "harmonises" the two onto a single hash function invalidates every code
already out in the world.

---

## Test vectors

`contract/vectors.json` is generated from the code running on the OriLife server: entity codes,
a full record with its hash, and a legacy-era record with its legacy hash. Both the Python and the
JavaScript implementations are checked against it.

Two independent implementations agreeing on one set of vectors is far stronger evidence than one
implementation grading its own homework: a bug has to appear identically in both languages to get
through.

```bash
cd python && python -m pytest tests/test_verify.py -q
cd javascript && node --test 'test/verify.test.mjs'
```

Both run **offline**. If they needed the network they would not be independent verification.

See also `examples/verify.py` for the whole flow end to end, starting from a printed code.
