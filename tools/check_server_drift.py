#!/usr/bin/env python3
"""Compare `contract/methods.json` with the specification of the running server.

    python3 tools/check_server_drift.py                       # measure api.orilife.io
    python3 tools/check_server_drift.py --base-url https://…  # measure another server

Returns THREE states, not two:

    MATCH          exit code 0 — every method in the contract is in the server's `/openapi.json`
    DRIFT          exit code 1 — the contract declares an endpoint the server does not serve
    UNMEASURABLE   exit code 2 — the specification could not be fetched (no network, silent
                   server, broken JSON)

The third state must be LOUDER than the second, and must never fall silent into green. A
measurement that reports "fine" exactly when it measured nothing makes its green meaningless: it
does not say "fine", it says "I do not know" in the voice of "fine".

Why this measurement is needed. A hand-written `CONTRACT.md` drifted away from the server for
nineteen days: the version written on 2026-08-20 claimed `/api/identify/auto`,
`/.well-known/orilife.json` and `/llms.txt` all answered 404; measured again on 2026-09-08 they
answered 405 (the endpoint exists, it only takes POST), 200 and 200. Nothing reported it during
those nineteen days — the copy died in silence, and readers TRUSTED it.

This is DIFFERENT from `tools/generate.py --check`. That one asks "does the generated code match
the contract" (runs offline, always answers). This one asks "does the contract match the server"
(needs the network, sometimes cannot answer). Two different questions, two different gates; do
not merge them.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRACT = os.path.join(ROOT, "contract", "methods.json")

MATCH, DRIFT, UNMEASURABLE = 0, 1, 2


def fetch_spec(base_url: str, timeout: float):
    """Return (specification, failure reason). Exactly one of the two is not None."""
    url = base_url.rstrip("/") + "/openapi.json"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                   "User-Agent": "orilife-sdk-drift-check"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, f"the server answered {e.code} at {url}"
    except urllib.error.URLError as e:
        return None, f"could not reach {url}: {e.reason}"
    except (ValueError, TimeoutError) as e:
        return None, f"the specification at {url} could not be read: {e}"


def main(argv) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=None,
                        help="defaults to the value in contract/methods.json")
    parser.add_argument("--timeout", type=float, default=20.0)
    opts = parser.parse_args(argv)

    with open(CONTRACT, encoding="utf-8") as fh:
        contract = json.load(fh)
    base_url = opts.base_url or contract["base_url"]
    methods = [m for m in contract["methods"] if m.get("generated", True)]

    spec, why = fetch_spec(base_url, opts.timeout)
    if spec is None:
        print("UNMEASURABLE — %s" % why, file=sys.stderr)
        print("This gate did NOT run this time. Do not read it as 'nothing drifted'.", file=sys.stderr)
        return UNMEASURABLE

    paths = spec.get("paths")
    if not isinstance(paths, dict) or not paths:
        print("UNMEASURABLE — the downloaded specification has no `paths` section", file=sys.stderr)
        print("This gate did NOT run this time.", file=sys.stderr)
        return UNMEASURABLE

    missing = []
    wrong_verb = []
    for method in methods:
        declared = paths.get(method["path"])
        if declared is None:
            missing.append((method["name"], method["verb"], method["path"]))
        elif method["verb"].lower() not in {k.lower() for k in declared}:
            wrong_verb.append((method["name"], method["verb"], method["path"],
                               sorted(k.upper() for k in declared)))

    title = spec.get("info", {}).get("title", "?")
    version = spec.get("info", {}).get("version", "?")
    print("measured %s — %s v%s, OpenAPI %s"
          % (base_url, title, version, spec.get("openapi", "?")))

    if missing or wrong_verb:
        print("DRIFT — the contract declares endpoints this server does not serve:", file=sys.stderr)
        for name, verb, path in missing:
            print("  %-24s %s %s   <- not in /openapi.json" % (name, verb, path),
                  file=sys.stderr)
        for name, verb, path, have in wrong_verb:
            print("  %-24s %s %s   <- the server only accepts %s" % (name, verb, path, ", ".join(have)),
                  file=sys.stderr)
        print("Fix contract/methods.json and run tools/generate.py, OR find out from the server"
              " side why an endpoint that was handed over has disappeared.", file=sys.stderr)
        return DRIFT

    wrapped = {m["path"] for m in methods}
    print("MATCH — every method in the contract is in the server specification")
    print("        %d SDK methods on %d paths; the server declares %d paths."
          % (len(methods), len(wrapped), len(paths)))
    print("        The difference is NOT an error: the SDK deliberately wraps what an integration")
    print("        needs; call anything else directly with request().")
    return MATCH


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
