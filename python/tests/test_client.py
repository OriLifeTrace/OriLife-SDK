"""The API client has to behave correctly in the places people usually get wrong by hand.

Four of them, and all four only show up when the network is bad or the server is busy — that is,
exactly when nobody is watching the logs:

  • 429 with `Retry-After`: wait as long as the server asked, not as long as you feel like.
  • A WRITE endpoint that fails halfway: do NOT resend it, the request may have arrived and
    already created a record.
  • Errors must be TYPED, because an application handles 401 differently from 413 differently from
    429 — one string pushes the sorting work onto whoever writes the application.
  • The sentence shown to a person comes from `error`/`message`, not from `detail` (the shape
    produced by the parameter-validation layer, usually a structure rather than a sentence).

The second half of this file locks the WIRE FORMAT of every endpoint the client exposes: which
path is called, which fields travel, under which names. A wrong field name fails silently on a
server that ignores unknown fields, so "it did not raise" proves nothing on its own.

A fake server is built from the standard library — no traffic leaves the machine, and it runs in a
sandbox.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from orilife import Client, errors  # noqa: E402

SEEN: list = []
SCRIPT: list = []


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):        # stay quiet, do not pollute the test output
        pass

    def _serve(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        SEEN.append({"method": self.command, "path": self.path,
                     "headers": dict(self.headers), "body": body})
        status, payload, extra = SCRIPT.pop(0) if SCRIPT else (200, {"ok": True}, {})
        raw = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    do_GET = do_POST = do_DELETE = _serve


@pytest.fixture()
def server():
    SEEN.clear()
    SCRIPT.clear()
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _path(index: int = 0) -> str:
    """The path of one recorded request, query string stripped off."""
    return SEEN[index]["path"].split("?", 1)[0]


def _query(index: int = 0) -> dict:
    """The query string of one recorded request, as a flat dict."""
    raw = SEEN[index]["path"].split("?", 1)
    if len(raw) == 1:
        return {}
    return {k: v[0] for k, v in urllib.parse.parse_qs(raw[1]).items()}


def _form(index: int = 0) -> dict:
    """The url-encoded body of one recorded request, as a flat dict."""
    return {k: v[0] for k, v in
            urllib.parse.parse_qs(SEEN[index]["body"].decode("utf-8")).items()}


def _logged_in(server_url: str) -> Client:
    return Client(server_url, token="t", max_retries=0)


# ── behaviour under a bad network ──────────────────────────────────────────────────────────

def test_token_travels_as_a_bearer_header(server):
    SCRIPT.append((200, {"ok": True, "token": "abc123"}, {}))
    SCRIPT.append((200, {"ok": True, "username": "my_orchard"}, {}))
    c = Client(server)
    c.login("my_orchard", "durian.orchard.2026")
    assert c.token == "abc123"
    c.me()
    assert SEEN[1]["headers"]["Authorization"] == "Bearer abc123"


def test_login_body_is_json_not_a_query_string(server):
    """A password in the query string is a password in the logs of every machine on the way."""
    SCRIPT.append((200, {"ok": True, "token": "t"}, {}))
    Client(server).login("somebody", "long.enough.password")
    assert "?" not in SEEN[0]["path"]
    assert SEEN[0]["headers"]["Content-Type"] == "application/json"
    assert json.loads(SEEN[0]["body"])["password"] == "long.enough.password"


def test_images_go_up_as_multipart_with_their_bytes_intact(server):
    SCRIPT.append((200, {"ok": True, "kind": "tree", "result": {}}, {}))
    c = Client(server, token="t")
    c.identify_auto([("tree.jpg", b"\xff\xd8\x00binary\xff\xd9")], lat=10.5)
    body = SEEN[0]["body"]
    assert b"multipart" in SEEN[0]["headers"]["Content-Type"].encode()
    assert b'name="files"; filename="tree.jpg"' in body
    assert b"\xff\xd8\x00binary\xff\xd9" in body, "the photo bytes changed on the way"
    assert b'name="lat"' in body and b"10.5" in body


def test_empty_form_fields_are_left_out_not_sent_as_the_word_none(server):
    """Sending the string 'None' into a coordinate field builds junk data at the far end."""
    SCRIPT.append((200, {"ok": True}, {}))
    Client(server, token="t").identify_auto([("a.jpg", b"x")])
    assert b"None" not in SEEN[0]["body"]
    assert b'name="lat"' not in SEEN[0]["body"]


def test_a_rate_limit_is_waited_out_for_exactly_as_long_as_asked(server):
    SCRIPT.append((429, {"ok": False, "error": "The server is busy"}, {"Retry-After": "1"}))
    SCRIPT.append((200, {"ok": True}, {}))
    t0 = time.monotonic()
    out = Client(server, token="t").health()
    waited = time.monotonic() - t0
    assert out["ok"] is True
    assert waited >= 1.0, f"waited only {waited:.2f}s — the Retry-After header was not read"


def test_a_rate_limit_that_never_clears_surfaces_as_a_typed_error(server):
    for _ in range(5):
        SCRIPT.append((429, {"ok": False, "error": "The server is busy"},
                       {"Retry-After": "0.01"}))
    with pytest.raises(errors.RateLimitedError) as e:
        Client(server, token="t", max_retries=1).health()
    assert e.value.retry_after == 0.01


def test_a_read_that_fails_on_the_server_is_retried(server):
    SCRIPT.append((500, {"ok": False, "error": "broken"}, {}))
    SCRIPT.append((200, {"ok": True}, {}))
    assert Client(server, token="t").health()["ok"] is True
    assert len(SEEN) == 2


def test_a_write_that_fails_is_never_retried_by_itself(server):
    """Resending a failed WRITE endpoint can create a second record. The caller must decide."""
    SCRIPT.append((500, {"ok": False, "error": "broken"}, {}))
    SCRIPT.append((200, {"ok": True}, {}))
    with pytest.raises(errors.ServerError):
        Client(server, token="t").enroll_tree([("a.jpg", b"x")], name="tree 1")
    assert len(SEEN) == 1, "a WRITE endpoint was resent on its own"


@pytest.mark.parametrize("status,kind", [
    (400, errors.InvalidRequestError),
    (401, errors.AuthError),
    (403, errors.PermissionError_),
    (404, errors.NotFoundError),
    (413, errors.TooLargeError),
    (422, errors.InvalidRequestError),
    (500, errors.ServerError),
])
def test_each_status_becomes_its_own_kind_of_error(server, status, kind):
    SCRIPT.append((status, {"ok": False, "error": "a sentence for the user"}, {}))
    with pytest.raises(kind) as e:
        Client(server, token="t", max_retries=0).resolve("ORI-0000000-AAAAAAAA")
    assert e.value.message == "a sentence for the user"
    assert e.value.status == status


def test_the_message_shown_to_a_person_never_comes_from_the_validation_shape(server):
    """`detail` is the shape of the validation layer — showing it puts a technical string in
    front of a farmer."""
    SCRIPT.append((422, {"detail": [{"loc": ["body", "files"], "msg": "field required"}]}, {}))
    with pytest.raises(errors.InvalidRequestError) as e:
        Client(server, token="t", max_retries=0).lookup_fruit(("a.jpg", b"x"))
    assert "loc" not in e.value.message
    assert e.value.payload["detail"], "the original body must be kept for whoever debugs this"


def test_an_unreachable_server_is_a_network_error_not_a_server_error(server):
    """Two different cases: in one the request NEVER arrived, in the other it did."""
    with pytest.raises(errors.NetworkError):
        Client("http://127.0.0.1:1", timeout=1.0, max_retries=0).health()


def test_unknown_response_fields_are_handed_through_untouched(server):
    """This client does not interpret matching internals. An unknown field goes straight to the
    application, uncut."""
    SCRIPT.append((200, {"ok": True, "decision": "MATCH", "confidence": "high",
                         "a_new_field_from_the_server": 42}, {}))
    out = Client(server, token="t").identify_tree([("a.jpg", b"x")])
    assert out["a_new_field_from_the_server"] == 42


# ── farms ──────────────────────────────────────────────────────────────────────────────────

def test_create_farm_posts_the_name_and_nothing_it_was_not_given(server):
    SCRIPT.append((200, {"ok": True, "farm": {"farm_id": "f1"}}, {}))
    _logged_in(server).create_farm("Hillside plot")
    assert SEEN[0]["method"] == "POST"
    assert _path() == "/api/farm"
    assert _form() == {"name": "Hillside plot"}


def test_create_farm_sends_coordinates_as_one_centre_point(server):
    """Half a coordinate is not a place: both or neither."""
    SCRIPT.append((200, {"ok": True, "farm": {}}, {}))
    _logged_in(server).create_farm("Riverside", lat=10.5, lon=106.5)
    assert json.loads(_form()["center_json"]) == [10.5, 106.5]

    SEEN.clear()
    SCRIPT.append((200, {"ok": True, "farm": {}}, {}))
    _logged_in(server).create_farm("Riverside", lat=10.5)
    assert "center_json" not in _form()


def test_list_farms_reads_the_collection(server):
    SCRIPT.append((200, {"ok": True, "farms": []}, {}))
    _logged_in(server).list_farms()
    assert SEEN[0]["method"] == "GET"
    assert _path() == "/api/farms"


def test_get_farm_puts_the_identifier_in_the_path_and_escapes_it(server):
    SCRIPT.append((200, {"ok": True, "farm": {}}, {}))
    _logged_in(server).get_farm("farm/with space")
    assert SEEN[0]["method"] == "GET"
    assert _path() == "/api/farm/farm%2Fwith%20space"


def test_update_farm_sends_only_the_fields_it_was_given(server):
    SCRIPT.append((200, {"ok": True, "farm": {}}, {}))
    _logged_in(server).update_farm("f1", name="New name", note=None)
    assert SEEN[0]["method"] == "POST"
    assert _path() == "/api/farm/f1/update"
    assert _form() == {"name": "New name"}, "a field nobody set must not travel"


def test_update_farm_json_encodes_a_boundary_instead_of_stringifying_a_list(server):
    """str([[10.5, 106.5]]) is not JSON — single quotes, and the server would drop it."""
    SCRIPT.append((200, {"ok": True, "farm": {}}, {}))
    _logged_in(server).update_farm("f1", boundary_json=[[10.5, 106.5], [10.6, 106.6]],
                                   boundary_method="gps_walk")
    sent = _form()
    assert json.loads(sent["boundary_json"]) == [[10.5, 106.5], [10.6, 106.6]]
    assert sent["boundary_method"] == "gps_walk"


def test_delete_farm_uses_the_delete_method(server):
    SCRIPT.append((200, {"ok": True}, {}))
    _logged_in(server).delete_farm("f1")
    assert SEEN[0]["method"] == "DELETE"
    assert _path() == "/api/farm/f1"


# ── fruit ──────────────────────────────────────────────────────────────────────────────────

def test_enroll_fruit_sends_the_tree_the_name_and_the_box(server):
    SCRIPT.append((200, {"ok": True, "fruit_id": "fr1"}, {}))
    _logged_in(server).enroll_fruit([("fruit.jpg", b"bytes")], tree_id="t-1",
                                    name="fruit 9", bbox=(12, 34, 100, 200))
    body = SEEN[0]["body"]
    assert SEEN[0]["method"] == "POST"
    assert _path() == "/api/fruit/enroll"
    assert b'name="file"; filename="fruit.jpg"' in body
    for field, value in (("tree_id", b"t-1"), ("name", b"fruit 9"), ("bbox_x", b"12"),
                         ("bbox_y", b"34"), ("bbox_w", b"100"), ("bbox_h", b"200")):
        assert f'name="{field}"'.encode() in body, f"{field} did not travel"
        assert value in body


def test_enroll_fruit_accepts_a_box_as_a_dict_too(server):
    SCRIPT.append((200, {"ok": True}, {}))
    _logged_in(server).enroll_fruit([("f.jpg", b"x")], tree_id="t-1",
                                    bbox={"x": 1, "y": 2, "w": 3, "h": 4})
    assert b'name="bbox_h"' in SEEN[0]["body"]


def test_a_malformed_box_is_refused_before_anything_is_uploaded(server):
    """A silently dropped box enrols the whole photo instead of the fruit — a wrong record
    rather than a visible error."""
    with pytest.raises(ValueError):
        _logged_in(server).enroll_fruit([("f.jpg", b"x")], tree_id="t-1", bbox=(1, 2, 3))
    assert SEEN == []


def test_enroll_fruit_refuses_a_second_photo_instead_of_dropping_it(server):
    """The endpoint takes one photo per call. Sending two would upload both and keep one."""
    with pytest.raises(ValueError):
        _logged_in(server).enroll_fruit([("a.jpg", b"x"), ("b.jpg", b"y")], tree_id="t-1")
    assert SEEN == []


def test_add_fruit_view_sends_one_angle_against_the_fruit_identifier(server):
    SCRIPT.append((200, {"ok": True}, {}))
    _logged_in(server).add_fruit_view("fr-1", [("side.jpg", b"z")])
    body = SEEN[0]["body"]
    assert SEEN[0]["method"] == "POST"
    assert _path() == "/api/fruit/add_view"
    assert b'name="fruit_id"' in body and b"fr-1" in body
    assert b'name="file"; filename="side.jpg"' in body


def test_a_single_path_is_not_read_as_a_list_of_letters(server):
    """"a.jpg" is iterable; without a guard it becomes five one-character filenames."""
    SCRIPT.append((200, {"ok": True}, {}))
    _logged_in(server).add_fruit_view("fr-1", ("side.jpg", b"z"))
    assert b'filename="side.jpg"' in SEEN[0]["body"]


# ── animals ────────────────────────────────────────────────────────────────────────────────

def test_enroll_animal_sends_every_photo_under_the_plural_field_name(server):
    SCRIPT.append((200, {"ok": True, "did": "did:phoenix:x"}, {}))
    _logged_in(server).enroll_animal([("a.jpg", b"1"), ("b.jpg", b"2"), ("c.jpg", b"3")],
                                     species="bo", farm_id="f-1", name="Cow 7",
                                     owner_did="did:phoenix:me")
    body = SEEN[0]["body"]
    assert SEEN[0]["method"] == "POST"
    assert _path() == "/api/animal/enroll"
    assert body.count(b'name="images"; filename=') == 3
    for field, value in (("species", b"bo"), ("farm_id", b"f-1"), ("name", b"Cow 7"),
                         ("owner_did", b"did:phoenix:me")):
        assert f'name="{field}"'.encode() in body and value in body


def test_scan_animal_sends_one_image_and_the_farm(server):
    SCRIPT.append((200, {"ok": True, "decision": "MATCH"}, {}))
    _logged_in(server).scan_animal(("cow.jpg", b"x"), farm_id="f-1")
    body = SEEN[0]["body"]
    assert _path() == "/api/animal/scan"
    assert b'name="image"; filename="cow.jpg"' in body
    assert b'name="farm_id"' in body and b"f-1" in body
    assert b'name="species"' not in body, "species is an override, not a default"


def test_scan_animal_passes_a_confirmed_species_through(server):
    SCRIPT.append((200, {"ok": True}, {}))
    _logged_in(server).scan_animal(("cow.jpg", b"x"), farm_id="f-1", species="bo")
    assert b'name="species"' in SEEN[0]["body"]


def test_list_animals_puts_its_filters_in_the_query_string(server):
    SCRIPT.append((200, {"ok": True, "animals": []}, {}))
    _logged_in(server).list_animals(farm_id="f-1", species="bo", limit=50, offset=100)
    assert SEEN[0]["method"] == "GET"
    assert _path() == "/api/animal/list"
    assert _query() == {"farm_id": "f-1", "species": "bo", "limit": "50", "offset": "100"}


def test_list_animals_without_filters_sends_no_empty_parameters(server):
    SCRIPT.append((200, {"ok": True, "animals": []}, {}))
    _logged_in(server).list_animals()
    assert _query() == {}


# ── verdicts: telling the server it got it right, or wrong ─────────────────────────────────

def test_a_tree_verdict_carries_the_query_it_belongs_to(server):
    SCRIPT.append((200, {"ok": True}, {}))
    _logged_in(server).submit_verdict("q-1", "wrong", correct_tree_id="t-9")
    assert SEEN[0]["method"] == "POST"
    assert _path() == "/api/identify_verdict"
    assert _form() == {"query_id": "q-1", "verdict": "wrong", "correct_tid": "t-9"}


def test_a_tree_verdict_without_a_correction_sends_only_two_fields(server):
    SCRIPT.append((200, {"ok": True}, {}))
    _logged_in(server).submit_verdict("q-1", "correct")
    assert _form() == {"query_id": "q-1", "verdict": "correct"}


def test_a_fruit_verdict_goes_to_the_fruit_endpoint(server):
    SCRIPT.append((200, {"ok": True}, {}))
    _logged_in(server).submit_fruit_verdict("q-2", "other", correct_fruit_id="fr-9")
    assert _path() == "/api/fruit/identify_verdict"
    assert _form() == {"query_id": "q-2", "verdict": "other", "correct_fruit_id": "fr-9"}


def test_an_animal_verdict_names_the_individual_by_its_identifier(server):
    SCRIPT.append((200, {"ok": True}, {}))
    _logged_in(server).submit_animal_verdict("q-3", "unknown_ok", correct_did="did:phoenix:c7")
    assert _path() == "/api/animal/identify_verdict"
    assert _form() == {"query_id": "q-3", "verdict": "unknown_ok",
                       "correct_did": "did:phoenix:c7"}


# ── what to photograph next ────────────────────────────────────────────────────────────────

def test_capture_plan_asks_by_kind_and_identifier(server):
    SCRIPT.append((200, {"ok": True, "have_kind": "faces", "missing": []}, {}))
    _logged_in(server).capture_plan("fruit", "fr-1")
    assert SEEN[0]["method"] == "GET"
    assert _path() == "/api/capture/plan"
    assert _query() == {"target_type": "fruit", "target_id": "fr-1"}


# ── timeline ───────────────────────────────────────────────────────────────────────────────

def test_an_event_is_posted_as_json_under_the_subject(server):
    SCRIPT.append((200, {"ok": True, "event_id": "e-1", "leaf_hash": "aa"}, {}))
    _logged_in(server).add_event("tree", "t-1", "water", {"litres": 20})
    assert SEEN[0]["method"] == "POST"
    assert _path() == "/api/tree/t-1/event"
    assert SEEN[0]["headers"]["Content-Type"] == "application/json"
    assert json.loads(SEEN[0]["body"]) == {"kind": "water", "payload": {"litres": 20}}


def test_an_event_without_data_still_carries_its_kind(server):
    SCRIPT.append((200, {"ok": True, "event_id": "e-2"}, {}))
    _logged_in(server).add_event("animal", "did:phoenix:c7", "observe")
    assert _path() == "/api/animal/did%3Aphoenix%3Ac7/event"
    assert json.loads(SEEN[0]["body"]) == {"kind": "observe", "payload": {}}


def test_anchoring_names_the_event_the_user_sealed(server):
    SCRIPT.append((200, {"ok": True, "anchor": {"tx": "abc"}}, {}))
    _logged_in(server).anchor_event("tree", "t-1", "e-1")
    assert SEEN[0]["method"] == "POST"
    assert _path() == "/api/tree/t-1/event/e-1/anchor"


# ── sessions ───────────────────────────────────────────────────────────────────────────────

def test_logging_out_everywhere_also_drops_the_token_held_here(server):
    """Keeping a token that the server has just revoked only produces a confusing 401 later."""
    SCRIPT.append((200, {"ok": True}, {}))
    c = _logged_in(server)
    c.logout_all()
    assert SEEN[0]["method"] == "POST"
    assert _path() == "/api/logout-all"
    assert c.token is None


# ── asking what this server can do ─────────────────────────────────────────────────────────

_LISTING = {"count": 2, "docs": "/docs", "openapi": "/openapi.json",
            "routes": [{"path": "/api/identify", "methods": ["POST"], "summary": ""},
                       {"path": "/api/farm/{farm_id}", "methods": ["GET"], "summary": ""}]}


def test_supports_reads_the_listing_and_answers_yes_or_no(server):
    SCRIPT.append((200, _LISTING, {}))
    c = _logged_in(server)
    assert c.supports("/api/identify") is True
    assert c.supports("/api/identify/auto") is False
    assert _path() == "/api"


def test_supports_asks_the_server_once_no_matter_how_often_it_is_called(server):
    SCRIPT.append((200, _LISTING, {}))
    c = _logged_in(server)
    for _ in range(5):
        c.supports("/api/identify")
    assert len(SEEN) == 1, "the endpoint listing was fetched more than once"


def test_supports_compares_against_the_declared_path_template(server):
    SCRIPT.append((200, _LISTING, {}))
    c = _logged_in(server)
    assert c.supports("/api/farm/{farm_id}") is True
    assert c.supports("/api/farm/f-1") is False


def test_supports_tolerates_a_missing_slash_a_trailing_slash_and_a_query(server):
    SCRIPT.append((200, _LISTING, {}))
    c = _logged_in(server)
    assert c.supports("api/identify") is True
    assert c.supports("/api/identify/") is True
    assert c.supports("/api/identify?lat=1") is True
    assert c.supports("") is False


def test_a_server_without_a_listing_answers_no_instead_of_raising(server):
    """An old server has no `/api` at all. "I cannot ask" and "the answer is no" lead to the same
    decision here: do not call that endpoint."""
    SCRIPT.append((404, {"detail": "Not Found"}, {}))
    c = _logged_in(server)
    assert c.supports("/api/identify/auto") is False
    assert len(SEEN) == 1, "a 404 answer must be remembered too, not asked again"


def test_a_missing_endpoint_raises_instead_of_quietly_using_another_one(server):
    """`/api/identify/auto` is not live on every server. Falling back to a different endpoint
    would change what the answer means without saying so."""
    SCRIPT.append((404, {"error": "Not Found"}, {}))
    with pytest.raises(errors.NotFoundError):
        _logged_in(server).identify_auto([("a.jpg", b"x")])
    assert len(SEEN) == 1
