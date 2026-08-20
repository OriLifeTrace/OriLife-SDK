"""Full field flow: open an account, identify a tree, handle the three possible outcomes,
add another view to the record.

Run:  python examples/identify.py photo1.jpg photo2.jpg
"""
import sys

from orilife import AuthError, Client, NetworkError, RateLimitedError

USERNAME = "my_orchard"            # 3-32 chars, lowercase/digits/dot/underscore -- NO hyphen
PASSWORD = "durian.season.2026"    # >=10 chars, >=2 character classes, not a common password


def log_in() -> Client:
    client = Client()
    try:
        client.login(USERNAME, PASSWORD)
    except AuthError:
        client.signup(USERNAME, PASSWORD)
    return client


def main(paths):
    client = log_in()

    # Read capabilities BEFORE showing any screen. This list is generated from the server's real
    # route table, so it never goes stale -- hard-coding it on the app side means the server can
    # add a capability the app still hides, or drop one the app still advertises.
    health = client.health()
    print(f"server {health['version']}, can do: {', '.join(health.get('features', []))}")

    try:
        # `identify_tree` is the live re-identification route. The combined `/api/identify/auto`
        # endpoint (guess kind, then identify) is not yet deployed -- see examples/agent.py for
        # how to probe a route before calling it.
        out = client.identify_tree(paths, lat=10.762622, lon=106.660172)
    except RateLimitedError as e:
        print(f"server is busy, wait {e.retry_after:g}s then retry")
        return
    except NetworkError as e:
        print(f"could not reach server: {e.message}")
        return

    decision = out.get("decision")

    if decision == "MATCH":
        print(f"match: {out['name']} (confidence {out['confidence']})")
        # Add another view RIGHT after a correct match -- one more angle now is worth more than
        # many angles in a single session, because it records the tree at a different moment.
        client.verify_add(out["tree_id"], paths)

    elif decision in ("UNCERTAIN", "MOVED"):
        # "Not sure" is an OUTCOME, not an error. Don't retry, don't show a spinner.
        print("not sure which tree. Candidates:")
        for c in out.get("candidates", [])[:5]:
            print(f"  - {c['name']}")
        if out.get("allow_enroll_new"):
            print("  - or: none of these")

    else:
        print("never seen this tree before")
        if out.get("allow_enroll_new"):
            new = client.enroll_tree(paths, name="new tree", lat=10.762622, lon=106.660172)
            print(f"enrolled, code {new.get('code')}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python identify.py <image> [image...]")
    main(sys.argv[1:])
