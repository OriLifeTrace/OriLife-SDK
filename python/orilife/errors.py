"""TYPED errors — so an application can tell apart three things that one error string blends.

Those three are: the user's fault (blurred photo, weak password), the application's fault (expired
token, wrong endpoint), and the far end's fault (server busy, network down). An application must
handle them in three completely different ways — show a hint, log in again, or wait and retry — so
folding them into one generic `Exception` pushes the sorting work onto whoever writes the
application, and everyone guesses differently.

Every error here carries `message`: the sentence the server already wrote for the end user to
read. Show that sentence as it is. Do not translate a status code into a sentence of your own —
the server knows the context, the application does not.
"""
from __future__ import annotations

from typing import Any, Optional

__all__ = [
    "OriLifeError", "NetworkError", "AuthError", "PermissionError_",
    "NotFoundError", "TooLargeError", "InvalidRequestError", "RateLimitedError",
    "ServerError", "from_response",
]


class OriLifeError(Exception):
    """Root of every error this package raises. Catch this and you catch them all."""

    def __init__(self, message: str, *, status: Optional[int] = None,
                 payload: Any = None, path: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.payload = payload
        self.path = path

    def __str__(self) -> str:                     # noqa: D105 — a line for people, not for code
        head = f"[{self.status}] " if self.status else ""
        return f"{head}{self.message}"


class NetworkError(OriLifeError):
    """Could not talk to the server at all: no network, timed out, name did not resolve.

    Not the same thing as `ServerError`. Here the request may NEVER have arrived, so retrying a
    WRITE endpoint (enrolling a tree, appending an event) can create a second record. Retrying a
    READ endpoint is free.
    """


class AuthError(OriLifeError):
    """401 — not logged in, or the token has expired. Get a new token and call again."""


class PermissionError_(OriLifeError):
    """403 — logged in, but not allowed to touch this. A new token will NOT help."""


class NotFoundError(OriLifeError):
    """404 — there is no such thing.

    Be careful what you infer: several endpoints deliberately answer 404 for both "does not exist"
    and "belongs to somebody else", so that a stranger walking identifiers cannot count another
    person's orchard. Do not print "this tree does not exist" on the screen.
    """


class TooLargeError(OriLifeError):
    """413 — over the size cap. Compress the photo and send it again; do not retry it unchanged."""


class InvalidRequestError(OriLifeError):
    """400 or 422 — missing field, wrong type, or a rule not met (weak password, bad username)."""


class RateLimitedError(OriLifeError):
    """429 — calling too often.

    `retry_after` is the number of seconds the server asked for. WAIT exactly that long before
    calling again; retrying immediately is the very thing a 429 exists to stop, and doing it only
    extends the block.
    """

    def __init__(self, message: str, *, retry_after: float = 1.0, **kw):
        super().__init__(message, **kw)
        self.retry_after = retry_after


class ServerError(OriLifeError):
    """5xx — the request did arrive and the far end broke. Safe to retry, with a growing gap."""


_BY_STATUS = {
    400: InvalidRequestError,
    401: AuthError,
    403: PermissionError_,
    404: NotFoundError,
    413: TooLargeError,
    422: InvalidRequestError,
    429: RateLimitedError,
}


def _message_of(payload: Any, fallback: str) -> str:
    """The sentence for the user, in the same order of preference the server uses.

    The server puts the readable sentence in `error` or `message`; `detail` is the shape produced
    by the parameter-validation layer, so it is usually a structure rather than a sentence. Taking
    `detail` as the line to display is the fastest way to drop a technical string in front of a
    farmer.
    """
    if isinstance(payload, dict):
        for key in ("error", "message"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        detail = payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
    return fallback


def from_response(status: int, payload: Any, *, path: str = "", headers: Any = None):
    """Build the right error class from a response. Returns the exception; the caller raises it."""
    message = _message_of(payload, f"The server answered with status {status}.")
    cls = _BY_STATUS.get(status) or (ServerError if status >= 500 else OriLifeError)
    if cls is RateLimitedError:
        after = None
        if headers is not None:
            raw = headers.get("Retry-After") if hasattr(headers, "get") else None
            try:
                after = float(raw) if raw is not None else None
            except (TypeError, ValueError):
                after = None
        if after is None and isinstance(payload, dict):
            try:
                after = float(payload.get("retry_after"))
            except (TypeError, ValueError):
                after = None
        return RateLimitedError(message, retry_after=(after if after and after > 0 else 1.0),
                                status=status, payload=payload, path=path)
    return cls(message, status=status, payload=payload, path=path)
