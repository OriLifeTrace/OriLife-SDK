"""Verify an OriLife code WITHOUT trusting OriLife.

Fetch the record from content-addressed storage, hash it locally, and compare against the number
already anchored on the Cardano chain. The hash runs locally with the standard library -- it does
not ask the server "is this record correct?", because that would let the party being checked grade
itself.

Run:  python examples/verify.py ORI-w3gv5j2-A7K9PQ2M
"""
import json
import sys
import urllib.request

from orilife import Client, NotFoundError, verify

LAMPNET = "https://lampnet.cloud"


def check(code: str) -> int:
    client = Client()

    try:
        prov = client.tree_by_code(code)["provenance"]
    except NotFoundError:
        # A 404 here does NOT mean the code is wrong. A private tree and a nonexistent code get
        # the same answer, on purpose, so that someone probing codes cannot count other people's
        # orchards.
        print(f"{code}: could not resolve (code does not exist, or owner has not made it public)")
        return 2

    with urllib.request.urlopen(f"{LAMPNET}/{prov['record_cid']}") as fh:
        record = json.load(fh)

    summary = verify.summarize(record, prov["record_hash"])
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if summary["missing_fields"]:
        # A record MISSING fields looks nothing like a record that is COMPLETE but hash-mismatched:
        # this case is almost always a partial download or a wrong shard, not tampering.
        print("\nWARNING: record is missing fields -- likely an incomplete download, fetch again")
        return 3

    if not summary["hash_matches"]:
        print("\nFAIL: hash does NOT match -- the record has changed since it was anchored")
        return 1

    print("\nOK: record matches the anchored hash")
    anchor = prov.get("anchor") or {}
    if anchor.get("tx_hash"):
        # The last and most important step: the number just compared is the number the server
        # handed over. Open the block explorer and read it back by eye -- only then have you left
        # a single party's word.
        print(f"  read it back on-chain: {anchor.get('explorer_url') or anchor['tx_hash']}")
        print(f"  metadata label 1454, field \"h\" must equal {prov['record_hash']}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python verify.py ORI-...")
    sys.exit(check(sys.argv[1]))
