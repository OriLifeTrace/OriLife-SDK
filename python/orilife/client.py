"""OriLife API client — no third-party packages, runs on Python 3.9 and newer.

Why not `requests` or `httpx`: this client has to run where nothing can be installed — an
embedded box in a field, an agent inside a sandbox, a serverless function with a size cap. The
standard library covers everything needed here, and a single dependency-free file can be audited
by reading it.

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
import mimetypes
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from .errors import NetworkError, NotFoundError, RateLimitedError, ServerError, from_response

__all__ = ["Client", "DEFAULT_BASE_URL"]

DEFAULT_BASE_URL = "https://api.orilife.io"
_USER_AGENT = "orilife-sdk-python/1.0"

# Endpoints that can be called again without creating another record. Everything else is retried
# only when the failure is a 429 or a 5xx — in those two cases the server has said outright that
# it did nothing.
_IDEMPOTENT = ("GET", "HEAD")

FileArg = Union[str, bytes, Tuple[str, bytes], Tuple[str, bytes, str]]


def _as_file(item: FileArg) -> Tuple[str, bytes, str]:
    """Accept a path, a blob of bytes, or a tuple; return (filename, bytes, content type)."""
    if isinstance(item, str):
        with open(item, "rb") as fh:
            data = fh.read()
        name = os.path.basename(item)
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        return name, data, ctype
    if isinstance(item, bytes):
        return "upload.jpg", item, "image/jpeg"
    if isinstance(item, tuple) and len(item) == 2:
        return item[0], item[1], (mimetypes.guess_type(item[0])[0] or "application/octet-stream")
    if isinstance(item, tuple) and len(item) == 3:
        return item
    raise TypeError("a file must be a path, bytes, (name, bytes) or (name, bytes, content type)")


def _as_file_list(images: Union[FileArg, Iterable[FileArg]]) -> List[FileArg]:
    """Normalise "one image or many" into a list.

    A single path is a `str`, and a `str` is iterable — so treating the argument as a sequence
    without this guard turns "photo.jpg" into ten one-character filenames. Fail early instead of
    uploading nonsense.
    """
    if isinstance(images, (str, bytes, tuple)):
        return [images]
    return list(images)


def _multipart(fields: Dict[str, Any], files: Sequence[Tuple[str, FileArg]]) -> Tuple[bytes, str]:
    """Build the multipart body by hand.

    Written here instead of using `email.mime` because that module inserts line breaks the way
    e-mail wants them, and one extra byte inside a binary body is a corrupted photo at the far end.
    """
    boundary = f"----orilife{uuid.uuid4().hex}"
    out = bytearray()
    for key, value in fields.items():
        if value is None:
            continue
        out += f"--{boundary}\r\n".encode()
        out += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
        out += str(value).encode("utf-8") + b"\r\n"
    for key, item in files:
        name, data, ctype = _as_file(item)
        out += f"--{boundary}\r\n".encode()
        out += (f'Content-Disposition: form-data; name="{key}"; '
                f'filename="{name}"\r\n').encode()
        out += f"Content-Type: {ctype}\r\n\r\n".encode()
        out += data + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def _bbox_fields(bbox: Any) -> Dict[str, Any]:
    """Turn a bounding box into the four form fields the server expects.

    Accepts `(x, y, w, h)` or `{"x":…, "y":…, "w":…, "h":…}`. Anything else raises, because a
    silently ignored box means the fruit is enrolled from the whole photo instead of from the
    fruit — a wrong record rather than a visible error.
    """
    if bbox is None:
        return {}
    if isinstance(bbox, dict):
        try:
            x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
        except KeyError as e:
            raise ValueError(f"bbox dict is missing key {e}; expected x, y, w, h") from None
    else:
        box = list(bbox)
        if len(box) != 4:
            raise ValueError("bbox must hold exactly four numbers: (x, y, w, h)")
        x, y, w, h = box
    return {"bbox_x": x, "bbox_y": y, "bbox_w": w, "bbox_h": h}


class Client:
    """One session with an OriLife server.

        client = Client()
        client.login("my_orchard", "durian.orchard.2026")
        result = client.identify_tree(["photo.jpg"], lat=10.762, lon=106.660)

    A token lives 12 hours. Once it expires the endpoints answer 401 and this client raises
    `AuthError` — catch it and call `login()` again. Logging back in silently is deliberately NOT
    done: keeping the password in memory for the whole life of the application, just in case, is
    trading a visible error for an invisible risk.
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

    # ── authentication ─────────────────────────────────────────────────────────────────────

    def signup(self, username: str, password: str) -> dict:
        """Open a new account on `POST /api/signup` and keep the token that comes back.

        Rules: username 3–32 characters, lowercase letters, digits, dots and underscores only —
        NO hyphens. Password at least 10 characters, at least two character classes, and not in
        the common-password list. Break a rule and the server answers 400 with a sentence saying
        exactly which one.
        """
        data = self.request("POST", "/api/signup",
                            json_body={"username": username, "password": password})
        return self._keep_token(data)

    def login(self, username: str, password: str) -> dict:
        """Trade a username and password for a token on `POST /api/login`.

        The token is stored on this client and sent as `Authorization: Bearer …` from then on.
        Wrong credentials raise `AuthError`.
        """
        data = self.request("POST", "/api/login",
                            json_body={"username": username, "password": password})
        return self._keep_token(data)

    def _keep_token(self, data: Any) -> dict:
        if isinstance(data, dict) and data.get("token"):
            self.token = data["token"]
        return data if isinstance(data, dict) else {"ok": True}

    def me(self) -> dict:
        """Who this token belongs to, from `GET /api/me`. Raises `AuthError` without a token."""
        return self.request("GET", "/api/me")

    def logout(self) -> dict:
        """End THIS session (`POST /api/logout`) and forget the token held here."""
        out = self.request("POST", "/api/logout")
        self.token = None
        return out

    def logout_all(self) -> dict:
        """End every session of this account on every device (`POST /api/logout-all`).

        Use it when a phone is lost or a token may have leaked: the server raises the account's
        token version, so all tokens issued so far stop working — including tokens this process
        never saw. The token held here is dropped as well, so the next call raises `AuthError`
        until you `login()` again. Requires a valid token; without one the server answers 401.
        """
        out = self.request("POST", "/api/logout-all")
        self.token = None
        return out

    # ── public endpoints: callable WITHOUT logging in ──────────────────────────────────────

    def health(self) -> dict:
        """Is the server alive, and what can it do today (`GET /api/health`).

        Read `features` before deciding which screens to show. That list is generated from the
        server's real routing table, so it cannot go stale — an application with a hard-coded
        capability list hides features the server has gained and keeps offering features the
        server has dropped.
        """
        return self.request("GET", "/api/health")

    def describe(self) -> dict:
        """Machine-readable service descriptor from `GET /.well-known/orilife.json`: which
        endpoints need no token, what the size caps are, which kinds of subject have a pipeline.

        Only servers that declare this path serve it; on servers that do not, it answers 404 and
        this raises `NotFoundError`. Check first:

            if client.supports("/.well-known/orilife.json"):
                info = client.describe()
        """
        return self.request("GET", "/.well-known/orilife.json")

    def endpoints(self) -> dict:
        """The server's own endpoint listing from `GET /api`.

        Returns `{"count": …, "docs": …, "openapi": …, "routes": [{"path", "methods",
        "summary"}, …]}`. `supports()` is the cheap way to ask a yes/no question about one path.
        """
        return self.request("GET", "/api")

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

    def species_catalog(self) -> dict:
        """The species this server knows about, from `GET /api/species/catalog`."""
        return self.request("GET", "/api/species/catalog")

    def resolve(self, code: str) -> dict:
        """Look up one `ORI-…` code (`GET /api/resolve/{code}`).

        Three states: `public` (visible), `restricted` (real, the owner has not opened it),
        `unknown`. `unknown` carries NO reason, and that is deliberate: if "wrong code" answered
        differently from "private code", someone walking the code space could count another
        person's orchard. Do not infer existence from a difference — there is none.
        """
        return self.request("GET", f"/api/resolve/{urllib.parse.quote(code, safe='')}")

    def tree_by_code(self, code: str) -> dict:
        """Provenance of one tree by the CODE printed on a slip (`GET /api/tree_by_code/{code}`)
        — for buyers, no account needed.

        A private tree and a tree that does not exist both answer 404. Do not print "wrong code"
        on the screen.
        """
        return self.request("GET", f"/api/tree_by_code/{urllib.parse.quote(code, safe='')}")

    def lookup_fruit(self, image: FileArg) -> dict:
        """One photo of a fruit → candidates in the public set (`POST /api/fruit/lookup`).

        No account needed, and nothing about the caller is kept.
        """
        return self.request("POST", "/api/fruit/lookup", files=[("file", image)])

    # ── identification ─────────────────────────────────────────────────────────────────────

    def identify_auto(self, images: Iterable[FileArg], *, lat: Optional[float] = None,
                      lon: Optional[float] = None, species: Optional[str] = None,
                      farm_id: Optional[str] = None) -> dict:
        """ONE endpoint for every kind (`POST /api/identify/auto`): the server works out whether
        it is looking at a tree, a fruit or an animal, then identifies the individual.

        Your application never has to ask the user what they are photographing. Returns `kind`,
        `lane` (the endpoint that ran) and `result`, which is the verbatim answer of that endpoint.

        Animals: the target endpoint still needs `species` and `farm_id`. Without them `result` is
        None and `need` lists those two fields — the server does NOT guess a species, because a
        guessed species would be written into an individual's record where nobody can check it.

        Only servers that declare this path serve it; elsewhere it answers 404 and this raises
        `NotFoundError`. There is no silent fallback to another endpoint. Check first:

            if client.supports("/api/identify/auto"):
                out = client.identify_auto(["photo.jpg"])
        """
        return self.request("POST", "/api/identify/auto",
                            fields={"lat": lat, "lon": lon,
                                    "species": species, "farm_id": farm_id},
                            files=[("files", f) for f in images])

    def identify_tree(self, images: Iterable[FileArg], *, lat: Optional[float] = None,
                      lon: Optional[float] = None, last_tree: Optional[str] = None) -> dict:
        """Recognise a tree again (`POST /api/identify`). Several photos from several angles work far
        better than a single photo.

        Coordinates are optional but worth sending: they narrow the search and make the resulting
        code more stable.
        """
        return self.request("POST", "/api/identify",
                            fields={"lat": lat, "lon": lon, "last_tree": last_tree,
                                    "source": "sdk"},
                            files=[("files", f) for f in images])

    def identify_tree_video(self, video: FileArg, *, lat: Optional[float] = None,
                            lon: Optional[float] = None) -> dict:
        """Walk once around the tree with the camera running instead of taking separate photos
        (`POST /api/identify/video`). The clip is NOT stored — it is used and dropped."""
        return self.request("POST", "/api/identify/video",
                            fields={"lat": lat, "lon": lon, "source": "sdk"},
                            files=[("file", video)], timeout=max(self.timeout, 120.0))

    def identify_fruit(self, image: FileArg, *, tree_id: Optional[str] = None) -> dict:
        """Recognise a fruit again (`POST /api/fruit/identify`). `tree_id` narrows the search to
        one tree; leave it out to search the whole orchard."""
        return self.request("POST", "/api/fruit/identify",
                            fields={"tree_id": tree_id}, files=[("file", image)])

    def identify_animal(self, image: FileArg, *, species: str, farm_id: str) -> dict:
        """Recognise an animal again (`POST /api/animal/identify`).

        Both `species` and `farm_id` are required by the server: the herd to compare against is
        chosen by them, and a wrong herd is a wrong answer.
        """
        return self.request("POST", "/api/animal/identify",
                            fields={"species": species, "farm_id": farm_id},
                            files=[("image", image)])

    def identify_kind(self, image: FileArg) -> dict:
        """Ask only WHAT IS IN THE PHOTO, without identifying the individual (`POST /api/kind`).
        Useful when you want to route the flow yourself."""
        return self.request("POST", "/api/kind", files=[("file", image)])

    def scan_animal(self, image: FileArg, *, farm_id: str,
                    species: Optional[str] = None) -> dict:
        """One button for animals (`POST /api/animal/scan`): the server works out the species
        from the farm's profile, then identifies the individual.

        `species` is optional here and is an override — send it once the user has confirmed the
        species, to skip auto-detection. `farm_id` is required. Only individuals belonging to the
        logged-in account are searched.
        """
        return self.request("POST", "/api/animal/scan",
                            fields={"farm_id": farm_id, "species": species},
                            files=[("image", image)])

    # ── enrolment ──────────────────────────────────────────────────────────────────────────

    def enroll_tree(self, images: Iterable[FileArg], *, name: str,
                    lat: Optional[float] = None, lon: Optional[float] = None,
                    farm_id: Optional[str] = None, species: Optional[str] = None) -> dict:
        """Enrol a new tree (`POST /api/enroll`).

        This is a WRITE endpoint: calling it again after the network dropped can create a second
        tree, so this client does NOT retry it. Catch `NetworkError`, ask `list_trees()` whether
        the tree arrived, and only then send it again.
        """
        return self.request("POST", "/api/enroll",
                            fields={"name": name, "lat": lat, "lon": lon,
                                    "farm_id": farm_id, "species": species},
                            files=[("files", f) for f in images])

    def verify_add(self, tree_id: str, images: Iterable[FileArg]) -> dict:
        """Confirm the tree is the right one and add more angles (`POST /api/verify_add`) — this
        is how a record grows thicker over time."""
        return self.request("POST", "/api/verify_add", fields={"tree_id": tree_id},
                            files=[("files", f) for f in images])

    def list_trees(self, *, farm_id: Optional[str] = None) -> dict:
        """Every tree of the logged-in account (`GET /api/trees`), optionally one farm only."""
        return self.request("GET", "/api/trees", params={"farm_id": farm_id})

    def enroll_fruit(self, images: Iterable[FileArg], *, tree_id: str,
                     name: Optional[str] = None, bbox: Any = None) -> dict:
        """Enrol a new fruit on the tree `tree_id` (`POST /api/fruit/enroll`).

        `bbox` marks where the fruit sits in the frame, as `(x, y, w, h)` or a dict with those
        four keys; without it the whole frame is used.

        The endpoint takes exactly ONE photo per call, so `images` must hold one item — passing
        more raises `ValueError` here rather than letting the extra photos be dropped in silence.
        Add the other angles afterwards with `add_fruit_view()`.

        A WRITE endpoint: never retried automatically. `tree_id` must belong to the logged-in
        account, otherwise the server answers 403.
        """
        items = _as_file_list(images)
        if len(items) != 1:
            raise ValueError("/api/fruit/enroll takes exactly one image per call; "
                             "add further angles with add_fruit_view()")
        fields: Dict[str, Any] = {"tree_id": tree_id, "name": name}
        fields.update(_bbox_fields(bbox))
        return self.request("POST", "/api/fruit/enroll", fields=fields,
                            files=[("file", items[0])])

    def add_fruit_view(self, fruit_id: str, images: Iterable[FileArg]) -> dict:
        """Add another angle to a fruit that is already enrolled (`POST /api/fruit/add_view`).

        Like `enroll_fruit()`, the endpoint takes exactly ONE photo per call; pass one image and
        call this again for the next angle. More than one raises `ValueError`.

        A WRITE endpoint: never retried automatically.
        """
        items = _as_file_list(images)
        if len(items) != 1:
            raise ValueError("/api/fruit/add_view takes exactly one image per call; "
                             "call it once per angle")
        return self.request("POST", "/api/fruit/add_view", fields={"fruit_id": fruit_id},
                            files=[("file", items[0])])

    def enroll_animal(self, images: Iterable[FileArg], *, species: str, farm_id: str,
                      name: Optional[str] = None, owner_did: Optional[str] = None) -> dict:
        """Enrol a new animal (`POST /api/animal/enroll`). Send at least three photos from
        different angles — one photo of one side is not an individual, it is a pose.

        `species` and `farm_id` are required. `owner_did` is optional and only ever confirms the
        account already logged in; it can never point at somebody else's account.

        A WRITE endpoint: never retried automatically. If the server answers that this individual
        looks like one already enrolled, show the user that individual before sending anything
        again — two calves of the same breed and age looking alike is normal, not a user error.
        """
        return self.request("POST", "/api/animal/enroll",
                            fields={"species": species, "farm_id": farm_id,
                                    "name": name, "owner_did": owner_did},
                            files=[("images", f) for f in _as_file_list(images)])

    def list_animals(self, *, farm_id: Optional[str] = None, species: Optional[str] = None,
                     limit: Optional[int] = None, offset: Optional[int] = None) -> dict:
        """Animals of the logged-in account (`GET /api/animal/list`), paged.

        Filter by `farm_id` or `species`; page with `limit` and `offset`. The server clamps
        `limit` to its own maximum, so asking for a huge page returns the server's page size
        rather than an error.
        """
        return self.request("GET", "/api/animal/list",
                            params={"farm_id": farm_id, "species": species,
                                    "limit": limit, "offset": offset})

    # ── farms ──────────────────────────────────────────────────────────────────────────────

    def create_farm(self, name: str, *, lat: Optional[float] = None,
                    lon: Optional[float] = None) -> dict:
        """Create a farm (`POST /api/farm`) and return `{"ok": …, "farm": {…}}`.

        The owner is taken from the token, never from the caller. `lat` and `lon` are optional and
        are sent as the farm's centre point; send both or neither, since half a coordinate is not
        a place. To draw a boundary rather than a point, use `update_farm(farm_id,
        boundary_json=[[lat, lon], …], boundary_method="gps_walk")`.

        A WRITE endpoint: never retried automatically.
        """
        center = None
        if lat is not None and lon is not None:
            center = json.dumps([lat, lon])
        return self.request("POST", "/api/farm",
                            fields={"name": name, "center_json": center})

    def list_farms(self) -> dict:
        """Farms of the logged-in account (`GET /api/farms`), each with its tree and animal
        counts. Other people's farms are never listed."""
        return self.request("GET", "/api/farms")

    def get_farm(self, farm_id: str) -> dict:
        """One farm with its trees and animals (`GET /api/farm/{farm_id}`).

        A farm that belongs to somebody else and a farm that does not exist both answer 403, so
        nobody can count another person's farms by walking identifiers.
        """
        return self.request("GET", f"/api/farm/{urllib.parse.quote(farm_id, safe='')}")

    def update_farm(self, farm_id: str, **fields: Any) -> dict:
        """Change a farm (`POST /api/farm/{farm_id}/update`). Only the fields you send change.

        Accepted: `name`, `kind`, `boundary_json`, `center_json`, `boundary_method`
        (`gps_walk` · `map_draw` · `mixed`), `boundary_acc_m`, `note`. Lists and dicts are JSON
        encoded on the way out, so `boundary_json=[[lat, lon], …]` works as written.

        Sending a new boundary without a new `boundary_method` resets the boundary's provenance to
        unknown: a new outline does not inherit the credibility of the old one.

        A WRITE endpoint: never retried automatically. Not your farm → 403.
        """
        out = {k: (json.dumps(v) if isinstance(v, (list, dict)) else v)
               for k, v in fields.items() if v is not None}
        return self.request("POST", f"/api/farm/{urllib.parse.quote(farm_id, safe='')}/update",
                            fields=out)

    def delete_farm(self, farm_id: str) -> dict:
        """Delete a farm (`DELETE /api/farm/{farm_id}`).

        The trees are NOT deleted: they lose their `farm_id` and stay traceable on their own. Any
        access grants on the farm are revoked with it. Not your farm → 403.
        """
        return self.request("DELETE", f"/api/farm/{urllib.parse.quote(farm_id, safe='')}")

    # ── telling the server it got it right, or wrong ───────────────────────────────────────

    def submit_verdict(self, query_id: str, verdict: str, *,
                       correct_tree_id: Optional[str] = None) -> dict:
        """Record whether a tree identification was right (`POST /api/identify_verdict`).

        `query_id` comes from the `identify_tree()` answer and joins the two together. `verdict`
        is `correct`, `wrong` or `other`. When it was wrong and you know which tree it really was,
        pass `correct_tree_id` (from `list_trees()`); a tree belonging to somebody else is ignored
        rather than refused, because this is a label, not an access request.

        This is how accuracy is measured. It is not the free-text feedback endpoint.
        """
        return self.request("POST", "/api/identify_verdict",
                            fields={"query_id": query_id, "verdict": verdict,
                                    "correct_tid": correct_tree_id})

    def submit_fruit_verdict(self, query_id: str, verdict: str, *,
                             correct_fruit_id: Optional[str] = None) -> dict:
        """Record whether a fruit identification was right (`POST /api/fruit/identify_verdict`).

        Same shape as `submit_verdict()`, for fruit. `query_id` comes from `identify_fruit()`;
        `verdict` is `correct`, `wrong` or `other`; `correct_fruit_id` comes from the fruit list.
        """
        return self.request("POST", "/api/fruit/identify_verdict",
                            fields={"query_id": query_id, "verdict": verdict,
                                    "correct_fruit_id": correct_fruit_id})

    def submit_animal_verdict(self, query_id: str, verdict: str, *,
                              correct_did: Optional[str] = None) -> dict:
        """Record whether an animal identification was right
        (`POST /api/animal/identify_verdict`).

        `query_id` comes from `identify_animal()` or `scan_animal()`. `verdict` is `correct`,
        `wrong`, `other`, or `unknown_ok` — the last one meaning the animal was never enrolled and
        the server correctly said it did not know. `correct_did` names the right individual.
        """
        return self.request("POST", "/api/animal/identify_verdict",
                            fields={"query_id": query_id, "verdict": verdict,
                                    "correct_did": correct_did})

    # ── what to photograph next ────────────────────────────────────────────────────────────

    def capture_plan(self, entity_type: str, entity_id: str) -> dict:
        """What is missing and what to photograph NEXT (`GET /api/capture/plan`) — one endpoint
        for trees, fruit and animals alike.

        `entity_type` is `tree`, `fruit` or `animal`; anything else answers 422. Call it when the
        capture screen opens, so the user reads "this fruit is missing its underside" instead of
        "4 photos taken", and again right after a rejection, which turns a refusal into a task.

        `have_kind` in the answer says how to read `have`: `faces` (fruit, counted by face) or
        `coverage` (trees and animals, counted by photo). Animals carry no `missing`/`thin` lists
        because the store does not record faces per photo — the empty list there is the true
        answer, not a gap. Read-only, and only for subjects of the logged-in account.
        """
        return self.request("GET", "/api/capture/plan",
                            params={"target_type": entity_type, "target_id": entity_id})

    # ── evidence ───────────────────────────────────────────────────────────────────────────

    def provenance(self, tree_id: str) -> dict:
        """Code, image addresses, record address, hashes, anchoring state
        (`GET /api/provenance/{tree_id}`) — the raw material for checking the claims yourself."""
        return self.request("GET", f"/api/provenance/{urllib.parse.quote(tree_id, safe='')}")

    def timeline(self, entity_type: str, entity_id: str) -> dict:
        """Every event recorded against one subject
        (`GET /api/{entity_type}/{entity_id}/timeline`).

        `entity_type` is `tree`, `fruit`, `farm`, `animal` or `plot`. A stranger sees the public,
        approved events; the owner sees all of them.
        """
        return self.request("GET", f"/api/{entity_type}/{urllib.parse.quote(entity_id, safe='')}/timeline")

    def proof(self, entity_type: str, entity_id: str, event_id: str) -> dict:
        """The Merkle path proving one event belongs to the root anchored on chain
        (`GET /api/{entity_type}/{entity_id}/proof/{event_id}`)."""
        return self.request(
            "GET",
            f"/api/{entity_type}/{urllib.parse.quote(entity_id, safe='')}"
            f"/proof/{urllib.parse.quote(event_id, safe='')}")

    def add_event(self, entity_type: str, entity_id: str, kind: str,
                  data: Optional[dict] = None) -> dict:
        """Append one event to a subject's timeline
        (`POST /api/{entity_type}/{entity_id}/event`).

        `entity_type` is `tree`, `fruit`, `farm`, `animal` or `plot`. `kind` is the short name of
        what happened (`observe`, `water`, `harvest`, …). `data` is free-form and is sent as the
        event payload; nothing in it is interpreted here.

        Returns `{"ok", "event_id", "leaf_hash", "visibility", "review", "suggest_anchor"}`. The
        owner's events are public and approved on arrival; an outsider's are private and pending
        the owner's approval. A subject that was never enrolled answers 403 — a timeline cannot
        exist before an owner does, otherwise writing the first event would be a way to claim
        ownership of somebody else's tree.

        `suggest_anchor` true means the server thinks it is worth calling `anchor_event()` now.
        It never anchors by itself: anchoring costs money and belongs to the owner.

        To set the envelope fields the timeline also accepts (`media`, `gps`, `quality`,
        `visibility`, `review`, `anchor_now`), call `request()` directly with your own JSON body.

        A WRITE endpoint: never retried automatically.
        """
        body = {"kind": kind, "payload": data or {}}
        return self.request("POST",
                            f"/api/{entity_type}/{urllib.parse.quote(entity_id, safe='')}/event",
                            json_body=body)

    def anchor_event(self, entity_type: str, entity_id: str, event_id: str) -> dict:
        """Anchor the subject's timeline on Cardano
        (`POST /api/{entity_type}/{entity_id}/event/{event_id}/anchor`).

        `event_id` is the event the user pressed "seal" on; the whole chain up to now is folded
        into one root and that root is what goes on chain, so one anchoring covers the entire
        history. Only the owner may do it — anyone else, and any subject without a known owner,
        gets 403. A chain transaction that fails downstream surfaces as `ServerError` (502).

        A WRITE endpoint that costs money on chain: never retried automatically.
        """
        return self.request(
            "POST",
            f"/api/{entity_type}/{urllib.parse.quote(entity_id, safe='')}"
            f"/event/{urllib.parse.quote(event_id, safe='')}/anchor")
