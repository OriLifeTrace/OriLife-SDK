"""An agent teaches itself about the service, then verifies a batch of codes -- with nobody
pointing the way first.

This is the path a bot or a language-model agent takes: find out what the server has declared
before calling anything, then only call what it declared.

Run:  python examples/agent.py ORI-w3gv5j2-A7K9PQ2M ORI-...
"""
import json
import sys
import urllib.request

from orilife import Client, NotFoundError, RateLimitedError, verify


def announce(client: Client) -> None:
    """Print what the server says about itself, whichever manifest it actually serves.

    Two machine-readable manifests exist in the spec: `/.well-known/orilife.json` (structured
    service description) and `/llms.txt` (plain-text summary meant for language models). Neither
    is deployed on every server -- probe both, say so plainly when one is missing instead of
    crashing, and fall back to `GET /api`, which every OriLife server serves and which lists
    every route it has actually declared.
    """
    try:
        desc = client.describe()
        public = {(e["method"], e["path"]) for e in desc["public_endpoints"]}
        print(f"{desc['name']} {desc['version']} -- {len(public)} routes callable without a key")
        return
    except NotFoundError:
        print("this server does not publish /.well-known/orilife.json yet")

    try:
        client.request("GET", "/llms.txt")
        print("this server publishes /llms.txt -- read it directly for a plain-text summary")
        return
    except NotFoundError:
        print("this server does not publish /llms.txt either")

    routes = client.endpoints()
    print(f"falling back to GET /api: {routes['count']} declared routes, docs at {routes['docs']}")


def main(codes):
    client = Client()

    # Step one for any agent: ask "what is this place and what am I allowed to do". Don't guess by
    # poking routes until one answers -- poking blindly is the fastest way to get rate-limited.
    announce(client)

    if not client.supports("/api/resolve/{code}"):
        # The route table is the source of truth. It does not declare this route, so do not call
        # it blindly.
        print("this server does not expose code lookup -- stopping")
        return

    for code in codes:
        try:
            out = client.resolve(code)
        except RateLimitedError as e:
            print(f"{code}: rate-limited, wait {e.retry_after:g}s")
            continue
        except NotFoundError:
            print(f"{code}: could not resolve")
            continue

        state = out.get("state") or out.get("status")
        if state != "public":
            # `unknown` carries NO reason, on purpose: there is nothing else to infer it from, and
            # trying to infer it anyway is probing someone else's orchard.
            print(f"{code}: {state} -- nothing more to say, and that's by design")
            continue

        prov = (out.get("provenance") or {})
        if not prov.get("record_cid"):
            print(f"{code}: public but no anchored record yet")
            continue

        with urllib.request.urlopen(f"https://lampnet.cloud/{prov['record_cid']}") as fh:
            record = json.load(fh)

        s = verify.summarize(record, prov.get("record_hash"))
        mark = "OK" if s["hash_matches"] else "FAIL"
        print(f"{code}: {mark} {s['n_images']} images, enrolled {s['enrolled_at']}, "
              f"hashed with {s['algorithm']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python agent.py ORI-... [ORI-...]")
    main(sys.argv[1:])
