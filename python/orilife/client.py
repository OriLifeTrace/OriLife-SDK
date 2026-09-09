"""OriLife API client — no third-party packages, runs on Python 3.9 and newer.

Why not `requests` or `httpx`: this client has to run where nothing can be installed — an
embedded box in a field, an agent inside a sandbox, a serverless function with a size cap. The
standard library covers everything needed here, and a single dependency-free file can be audited
by reading it.

This file holds the TRANSPORT and nothing else: headers, retries, error typing, decoding. The
endpoint methods live in `_generated.py`, which is written by `tools/generate.py` from
`contract/methods.json` — the one place where "which path, which field name, which file field" is
recorded, for every language this SDK is published in.

Three things this client does for you that hand-written code forgets:

  • Waiting the right amount of time when rate limited. The server answers 429 with a
    `Retry-After` header; retrying immediately only extends the block. This client reads that
    header and sleeps for exactly that long.
  • Retrying only what is safe to retry. A READ endpoint that fails on a broken network can be
    called again for free; a WRITE endpoint cannot — the request may have arrived and already
    created a record. The `_IDEMPOTENT` table holds that line.
  • Never interpreting the internals. An identification response may carry extra numeric fields;
    this client hands them to your application verbatim — it does NOT name them, does NOT explain
    them, does NOT build decision rules on top of them. The decision belongs to the server; the
    application reads `decision` and `confidence`.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Sequence, Tuple

from ._generated import CONTRACT_VERSION, GeneratedMethods
from ._wire import FileArg, _multipart
from .errors import NetworkError, NotFoundError, RateLimitedError, ServerError, from_response

__all__ = ["Client", "DEFAULT_BASE_URL", "CONTRACT_VERSION"]

DEFAULT_BASE_URL = "https://api.orilife.io"
_USER_AGENT = "orilife-sdk-python/1.0"

# Endpoints that can be called again without creating another record. Everything else is retried
# only when the failure is a 429 or a 5xx — in those two cases the server has said outright that
# it did nothing.
_IDEMPOTENT = ("GET", "HEAD")


class Client(GeneratedMethods):
    """One session with an OriLife server.

        client = Client()
        client.login("my_orchard", "durian.orchard.2026")
        result = client.identify_tree(["photo.jpg"], lat=10.762, lon=106.660)

    A token lives 12 hours. Once it expires the endpoints answer 401 and this client raises
    `AuthError` — catch it and call `login()` again. Logging back in silently is deliberately NOT
    done: keeping the password in memory for the whole life of the application, just in case, is
    trading a visible error for an invisible risk.

    Every endpoint method comes from `contract/methods.json`; see `contract/METHODS.md` for the
    full map.
    """

    def __init__(self, base_url: str = DEFAULT_BASE_URL, *, token: Optional[str] = None,
                 timeout: float = 30.0, max_retries: int = 2,
                 user_agent: str = _USER_AGENT):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = float(timeout)
        self.max_retries = max(0, int(max_retries))
        self.user_agent = user_agent
        # Filled in by the first call to `supports()`; `None` means "not asked yet".
        self._declared_paths: Optional[frozenset] = None

    # ── transport ──────────────────────────────────────────────────────────────────────────

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if extra:
            headers.update(extra)
        return headers

    def request(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None,
                fields: Optional[Dict[str, Any]] = None,
                files: Optional[Sequence[Tuple[str, FileArg]]] = None,
                json_body: Optional[Any] = None, timeout: Optional[float] = None) -> Any:
        """Call one endpoint. Raises a typed error when the far end refuses; returns the decoded
        body when it does not."""
        url = self.base_url + path
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            if clean:
                url += "?" + urllib.parse.urlencode(clean)

        body: Optional[bytes] = None
        extra: Dict[str, str] = {}
        if files:
            body, ctype = _multipart(fields or {}, files)
            extra["Content-Type"] = ctype
        elif json_body is not None:
            body = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            extra["Content-Type"] = "application/json"
        elif fields:
            body = urllib.parse.urlencode({k: v for k, v in fields.items()
                                           if v is not None}).encode("utf-8")
            extra["Content-Type"] = "application/x-www-form-urlencoded"

        attempt = 0
        while True:
            try:
                return self._once(method, url, body, extra, timeout or self.timeout, path)
            except RateLimitedError as e:
                # Wait exactly as long as the server asked. This is the ONLY place where the sleep
                # comes from the other side's number instead of our own formula — the other side
                # knows its queue, we do not.
                if attempt >= self.max_retries:
                    raise
                time.sleep(min(e.retry_after, 60.0))
            except (ServerError, NetworkError):
                if attempt >= self.max_retries or method.upper() not in _IDEMPOTENT:
                    raise
                time.sleep(min(2.0 ** attempt, 8.0))
            attempt += 1

    def _once(self, method: str, url: str, body: Optional[bytes],
              extra: Dict[str, str], timeout: float, path: str) -> Any:
        req = urllib.request.Request(url, data=body, method=method.upper(),
                                     headers=self._headers(extra))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                return self._decode(raw, resp.headers)
        except urllib.error.HTTPError as e:
            raw = e.read()
            payload: Any
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:                               # noqa: BLE001 — body was not JSON
                payload = {"error": raw.decode("utf-8", "replace")[:400]}
            raise from_response(e.code, payload, path=path, headers=e.headers) from None
        except urllib.error.URLError as e:
            raise NetworkError(f"Could not reach the server: {e.reason}", path=path) from None
        except TimeoutError:
            raise NetworkError("The server did not answer in time.", path=path) from None

    @staticmethod
    def _decode(raw: bytes, headers: Any) -> Any:
        ctype = (headers.get("Content-Type") or "") if hasattr(headers, "get") else ""
        if "json" in ctype:
            return json.loads(raw.decode("utf-8"))
        return raw

    def _keep_token(self, data: Any) -> dict:
        """Hold on to the token an authentication endpoint just handed back."""
        if isinstance(data, dict) and data.get("token"):
            self.token = data["token"]
        return data if isinstance(data, dict) else {"ok": True}

    # ── the one method that is not a single HTTP call ──────────────────────────────────────

    def supports(self, path: str) -> bool:
        """Does this server declare `path` (for example `"/api/identify/auto"`)?

        Reads `GET /api` ONCE per client and remembers the answer, so calling this in a loop costs
        one request in total. A server that does not serve `/api` at all answers 404, and then
        this returns False rather than raising — "I cannot ask" and "the answer is no" lead to the
        same decision here: do not call that endpoint.

        Compare against paths exactly as the server declares them, templates included:
        `supports("/api/farm/{farm_id}")` is True, `supports("/api/farm/abc123")` is not.

        Errors other than 404 (no network, server down) are NOT swallowed: they mean the question
        was never answered, and nothing is cached, so a later call asks again.
        """
        if self._declared_paths is None:
            try:
                data = self.request("GET", "/api")
            except NotFoundError:
                self._declared_paths = frozenset()
            else:
                routes = data.get("routes") if isinstance(data, dict) else None
                self._declared_paths = frozenset(
                    str(r["path"]) for r in (routes or [])
                    if isinstance(r, dict) and r.get("path"))
        wanted = (path or "").strip().split("?", 1)[0]
        if not wanted:
            return False
        if not wanted.startswith("/"):
            wanted = "/" + wanted
        if len(wanted) > 1:
            wanted = wanted.rstrip("/")
        return wanted in self._declared_paths
