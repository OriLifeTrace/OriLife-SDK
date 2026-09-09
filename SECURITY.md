# Security

## Reporting a vulnerability

Send it to `security@orilife.io`. Please do not open a public issue for a vulnerability — give us
time to fix it before it becomes a recipe for somebody else.

Include what you did, what you saw, and how to reproduce it. If you need a reply in English, say so;
we will answer in English.

For ordinary integration questions (not vulnerabilities), open an issue in this repository instead.

---

## Where tokens go, and where they must not

**A token belongs to a user, not to your application.** Each user signs in with their own account
and gets their own token. Do not embed one shared account in your app and route everyone through
it: everyone would see everyone else's holdings, and when you need to revoke access you would have
no way to revoke just one person.

**Never ship a password or a token inside an application bundle.** `.apk`, `.ipa` and JavaScript
bundles can all be opened and read. Anything embedded in them is public — it just has not been
noticed yet. The same goes for committing them to a repository, including a private one.

**Tokens live 12 hours.** After that, endpoints return `401`. Catch it and sign in again. Do not
keep the password in memory for the lifetime of the app so you can silently re-authenticate — that
trades a visible error for an invisible risk.

**Store tokens in the operating system's keystore**, not in `localStorage`, if any part of your app
runs in a browser.

**If you suspect a leak, call `POST /api/logout-all`.** It drops every token on the account, not
just the one you are holding.

---

## Browsers

CORS is open to every origin, and cross-origin cookies are **not** sent. Both halves go together,
and the second is the one doing the security work: with no cookie riding along there is no ambient
authority for a hostile page to borrow, and the whole CSRF class disappears. In exchange, the token
**must** travel in the `Authorization: Bearer` header.

The cookie path only works same-origin with the server.

---

## User data

**The photographs are somebody's real orchard.** Do not write them to logs, do not forward them to a
third-party service "just for debugging", and do not keep them after you are done with them.

**Coordinates are sensitive.** They point at one person's individual trees. The public lane already
coarsens coordinates before returning them; do not restore the precision from another data source
you happen to hold and then publish the result.

**Keep personal data out of query strings.** Query strings end up in the logs of every machine along
the path. That is exactly why this SDK sends passwords in a JSON body.

**What OriLife itself retains server-side is not documented in this repository.** One thing that is:
video submitted to `POST /api/identify/video` is used to select frames and then discarded, not
stored. If your deployment needs a retention commitment in writing, ask before you build on the
assumption.

**Deleting an account is a real operation, not a support ticket.** `GET /api/account/data` previews
everything an account owns; `POST /api/account/delete` erases it and requires re-typing the owner
code. Note there is no separate sandbox tier: an account you created to try things out is a real
account holding real data, so clean it up when you are done.

---

## The verifier

`orilife.verify` and `@orilife/sdk/verify` have no network access, no dependencies and no state.
That is deliberate: a verifier must still work when you do not trust the people who wrote it. You
can read `python/orilife/verify.py` end to end in about ten minutes, which is the point.

It is checked against the vectors in `contract/vectors.json`, generated from the code running on
the server, and both implementations (Python and JavaScript) must match. Details, and the procedure
for doing every step by hand without this SDK at all: [VERIFY.md](VERIFY.md).

---

## Supply chain

The packages have **no runtime dependencies** — Python uses only the standard library, JavaScript
only what the runtime already provides. That is a security property, not an aesthetic one: there is
no transitive dependency tree to be compromised on your behalf, and the whole surface fits in a code
review.

If you vendor the verifier rather than installing it, pin the file and re-run the vector tests after
each update. A verifier you have not tested since you copied it is not a verifier.
