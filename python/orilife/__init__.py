"""OriLife toolkit — identify an individual from a photograph of that individual.

Two halves, deliberately kept apart:

    from orilife import Client       # calls the API: identify, enrol, read timelines
    from orilife import verify       # INDEPENDENT verification: no network, no dependencies

The second half is the one that matters. `Client` only asks the server and repeats its answer —
using it means trusting OriLife. `verify` recomputes hashes from the record itself, so it can
check OriLife's claims without OriLife being present. A traceability system is only as trustworthy
as an outsider's ability to check it, which is why the verification half depends on nothing beyond
the standard library.
"""
from . import verify
from .client import DEFAULT_BASE_URL, Client
from .errors import (
    AuthError,
    InvalidRequestError,
    NetworkError,
    NotFoundError,
    OriLifeError,
    RateLimitedError,
    ServerError,
    TooLargeError,
)

__version__ = "1.0.0"

__all__ = [
    "Client", "DEFAULT_BASE_URL", "verify", "__version__",
    "OriLifeError", "NetworkError", "AuthError", "NotFoundError",
    "TooLargeError", "InvalidRequestError", "RateLimitedError", "ServerError",
]
