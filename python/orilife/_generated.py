"""SINH TỰ ĐỘNG từ contract/methods.json — ĐỪNG SỬA TAY.

Sửa hợp đồng rồi chạy `python3 tools/generate.py`. Sửa thẳng tệp này thì lần sinh sau mất hết,
và CI (`tools/generate.py --check`) đỏ ngay ở commit đó.
"""
from __future__ import annotations

from typing import Any

from ._wire import (_as_file_list, _bbox_fields, _center_json, _encode_containers,
                    _one_file, _quote)

__all__ = ["GeneratedMethods", "CONTRACT_VERSION"]

CONTRACT_VERSION = "1.0.0"


class GeneratedMethods:
    """Mọi cửa API, sinh từ hợp đồng. `Client` kế thừa lớp này và cấp `request()`."""

    request: Any
    timeout: float
    token: Any

    def signup(self, username, password) -> dict:
        """Open a new account and keep the token that comes back.

        Rules: username 3-32 characters, lowercase letters, digits, dots and underscores only -
        NO hyphens. Password at least 10 characters, at least two character classes, and not in
        the common-password list. Break a rule and the server answers 400 with a sentence saying
        exactly which one. Show that sentence.
        """
        # POST /api/signup
        return self._keep_token(self.request("POST", "/api/signup",
            json_body={"username": username, "password": password}))

    def login(self, username, password) -> dict:
        """Get a token. It lives 12 hours; after that every endpoint answers 401 and this client
        raises AuthError. Catch it and call login() again.

        Logging back in silently is deliberately NOT done: keeping the password in memory for the
        whole life of the application, just in case, trades a visible error for an invisible risk.
        """
        # POST /api/login
        return self._keep_token(self.request("POST", "/api/login",
            json_body={"username": username, "password": password}))

    def me(self) -> dict:
        """Who this token belongs to. Raises AuthError without a token.
        """
        # GET /api/me
        return self.request("GET", "/api/me")

    def logout(self) -> dict:
        """End THIS session and forget the token held here.
        """
        # POST /api/logout
        _out = self.request("POST", "/api/logout")
        self.token = None
        return _out

    def logout_all(self) -> dict:
        """End every session of this account on every device.

        Use it when a phone is lost or a token may have leaked: the server raises the account's
        token version, so every token issued so far stops working - including tokens this process
        never saw. The token held here is dropped too, so the next call raises AuthError until you
        log in again. Requires a valid token; without one the server answers 401.
        """
        # POST /api/logout-all
        _out = self.request("POST", "/api/logout-all")
        self.token = None
        return _out

    def health(self) -> dict:
        """Is the server alive, and what can it do today.

        Read `features` before deciding which screens to show. That list is generated from the
        server's real routing table, so it cannot go stale - an application with a hard-coded
        capability list hides features the server has gained and keeps offering ones it has dropped.
        """
        # GET /api/health
        return self.request("GET", "/api/health")

    def describe(self) -> dict:
        """Machine-readable service descriptor: which endpoints need no token, what the size caps are,
        which kinds of subject have a pipeline.

        Only servers that declare this path serve it; elsewhere it answers 404 and this raises
        NotFoundError. That is the correct answer, not a bug. Guard it with supports().
        """
        # GET /.well-known/orilife.json
        return self.request("GET", "/.well-known/orilife.json")

    def endpoints(self) -> dict:
        """The server's own endpoint listing.

        Returns {"count", "docs", "openapi", "routes": [{"path", "methods", "summary"}, ...]}.
        supports() is the cheap way to ask a yes/no question about one path.
        """
        # GET /api
        return self.request("GET", "/api")

    def species_catalog(self) -> dict:
        """The species this server knows about.
        """
        # GET /api/species/catalog
        return self.request("GET", "/api/species/catalog")

    def resolve(self, code) -> dict:
        """Look up one `ORI-...` code.

        Three states: `public` (visible), `restricted` (real, the owner has not opened it),
        `unknown`. `unknown` carries NO reason, and that is deliberate: if "wrong code" answered
        differently from "private code", someone walking the code space could count another
        person's orchard. Do not infer existence from a difference - there is none.
        """
        # GET /api/resolve/{code}
        return self.request("GET", f"/api/resolve/{_quote(code)}")

    def tree_by_code(self, code) -> dict:
        """Provenance of one tree by the CODE printed on a slip - for buyers, no account needed.

        A private tree and a tree that does not exist both answer 404. Do not print "wrong code".
        """
        # GET /api/tree_by_code/{code}
        return self.request("GET", f"/api/tree_by_code/{_quote(code)}")

    def lookup_fruit(self, image) -> dict:
        """One photo of a fruit -> candidates in the public set.
        No account needed, and nothing about the caller is kept.
        """
        # POST /api/fruit/lookup
        return self.request("POST", "/api/fruit/lookup",
            files=[("file", image)])

    def identify_auto(self, images, *, lat=None, lon=None, species=None, farm_id=None) -> dict:
        """ONE endpoint for every kind: the server works out whether it is looking at a tree, a fruit
        or an animal, then identifies the individual. Your application never has to ask the user
        what they are photographing.

        Returns `kind`, `lane` (the endpoint that ran) and `result`, the verbatim answer of that
        endpoint. Animals: the target endpoint still needs `species` and `farm_id`; without them
        `result` is null and `need` lists those two fields. The server does NOT guess a species,
        because a guessed species would be written into a record where nobody can check it.

        Only servers that declare this path serve it. There is no silent fallback to another
        endpoint. Guard it with supports("/api/identify/auto").
        """
        # POST /api/identify/auto
        return self.request("POST", "/api/identify/auto",
            fields={"lat": lat, "lon": lon, "species": species, "farm_id": farm_id},
            files=[("files", _f) for _f in _as_file_list(images)])

    def identify_tree(self, images, *, lat=None, lon=None, last_tree=None) -> dict:
        """Recognise a tree again. Several photos from several angles work far better than one photo.

        Coordinates are optional but worth sending: they narrow the search and make the resulting
        code more stable.

        Read `decision` to branch, never the numbers beside it. `MATCH`, `UNCERTAIN`, `NO_MATCH`,
        `MOVED`, `EMPTY_BUCKET`. Treat an unrecognised value as `UNCERTAIN` and ask the person.
        """
        # POST /api/identify
        return self.request("POST", "/api/identify",
            fields={"lat": lat, "lon": lon, "last_tree": last_tree, "source": "sdk"},
            files=[("files", _f) for _f in _as_file_list(images)])

    def identify_tree_video(self, video, *, lat=None, lon=None) -> dict:
        """Walk once around the tree with the camera running instead of taking separate photos.
        The clip is NOT stored - it is used and dropped.

        `NO_FRAMES` arrives with HTTP 422 and ok:false, not 200: no usable frame could be taken.
        """
        # POST /api/identify/video
        return self.request("POST", "/api/identify/video",
            fields={"lat": lat, "lon": lon, "source": "sdk"},
            files=[("file", video)],
            timeout=max(self.timeout, 120.0))

    def identify_fruit(self, image, *, tree_id=None) -> dict:
        """Recognise a fruit again. `tree_id` narrows the search to one tree; leave it out to search
        the whole holding. The empty-gallery answer here is `EMPTY_GALLERY`, not `EMPTY_BUCKET`.
        """
        # POST /api/fruit/identify
        return self.request("POST", "/api/fruit/identify",
            fields={"tree_id": tree_id},
            files=[("file", image)])

    def identify_animal(self, image, *, species, farm_id) -> dict:
        """Recognise an animal again.

        Both `species` and `farm_id` are required by the server: the herd to compare against is
        chosen by them, and a wrong herd is a wrong answer. The empty answer is `EMPTY_FARM`.
        """
        # POST /api/animal/identify
        return self.request("POST", "/api/animal/identify",
            fields={"species": species, "farm_id": farm_id},
            files=[("image", image)])

    def identify_kind(self, image) -> dict:
        """Ask only WHAT IS IN THE PHOTO, without identifying the individual.
        Useful when you want to route the flow yourself.
        """
        # POST /api/kind
        return self.request("POST", "/api/kind",
            files=[("file", image)])

    def scan_animal(self, image, *, farm_id, species=None) -> dict:
        """One button for animals: the server works out the species from the farm's profile, then
        identifies the individual.

        `species` is an override - send it once the user has confirmed the species, to skip the
        automatic step. `farm_id` is required. Only individuals of the logged-in account are
        searched.
        """
        # POST /api/animal/scan
        return self.request("POST", "/api/animal/scan",
            fields={"farm_id": farm_id, "species": species},
            files=[("image", image)])

    def enroll_tree(self, images, *, name, lat=None, lon=None, farm_id=None, species=None) -> dict:
        """Enrol a new tree.

        A WRITE endpoint: calling it again after the network dropped can create a second tree, so
        this client does NOT retry it. Catch NetworkError, ask list_trees() whether the tree
        arrived, and only then send it again.
        """
        # POST /api/enroll
        return self.request("POST", "/api/enroll",
            fields={"name": name, "lat": lat, "lon": lon, "farm_id": farm_id, "species": species},
            files=[("files", _f) for _f in _as_file_list(images)])

    def verify_add(self, tree_id, images) -> dict:
        """Add more angles to a tree that is already enrolled.

        `added:false` still arrives as HTTP 200 - read the `added` flag, not the status code. The
        photos are not lost when it is false; they are held aside.
        """
        # POST /api/verify_add
        return self.request("POST", "/api/verify_add",
            fields={"tree_id": tree_id},
            files=[("files", _f) for _f in _as_file_list(images)])

    def list_trees(self, *, farm_id=None) -> dict:
        """Trees of the logged-in account, optionally narrowed to one farm.
        """
        # GET /api/trees
        return self.request("GET", "/api/trees",
            params={"farm_id": farm_id})

    def enroll_fruit(self, images, *, tree_id, name=None, bbox=None) -> dict:
        """Enrol a new fruit on the tree `tree_id`.

        `bbox` marks where the fruit sits in the frame, as (x, y, w, h) or a mapping with those
        four keys; without it the whole frame is used. A malformed box raises here rather than
        silently enrolling the fruit from the whole photo - a wrong record instead of a visible
        error.

        The endpoint takes exactly ONE photo per call. Passing more raises here rather than letting
        the extra photos be dropped in silence. Add the other angles with add_fruit_view().
        """
        # POST /api/fruit/enroll
        _fields = {"tree_id": tree_id, "name": name}
        _fields.update(_bbox_fields(bbox))
        return self.request("POST", "/api/fruit/enroll",
            fields=_fields,
            files=[("file", _one_file(images, "/api/fruit/enroll takes exactly one image per call; add further angles with add_fruit_view()"))])

    def add_fruit_view(self, fruit_id, images) -> dict:
        """Add another angle to a fruit that is already enrolled. One photo per call.

        Angles gathered over the weeks are what make a fruit recognisable later - one more view
        next week is worth more than ten views this morning.
        """
        # POST /api/fruit/add_view
        return self.request("POST", "/api/fruit/add_view",
            fields={"fruit_id": fruit_id},
            files=[("file", _one_file(images, "/api/fruit/add_view takes exactly one image per call; call it once per angle"))])

    def enroll_animal(self, images, *, species, farm_id, name=None, owner_did=None) -> dict:
        """Enrol one animal. Note the file field is `images`, not `files`.

        `species` and `farm_id` are required: unlike a tree, the herd an animal belongs to is not
        something the photograph can tell you.
        """
        # POST /api/animal/enroll
        return self.request("POST", "/api/animal/enroll",
            fields={"species": species, "farm_id": farm_id, "name": name, "owner_did": owner_did},
            files=[("images", _f) for _f in _as_file_list(images)])

    def list_animals(self, *, farm_id=None, species=None, limit=None, offset=None) -> dict:
        """Animals of the logged-in account, paged.

        The server clamps `limit` to its own maximum, so asking for a huge page returns the
        server's page size rather than an error.
        """
        # GET /api/animal/list
        return self.request("GET", "/api/animal/list",
            params={"farm_id": farm_id, "species": species, "limit": limit, "offset": offset})

    def create_farm(self, name, *, lat=None, lon=None) -> dict:
        """Create a farm. The owner is taken from the token, never from the caller.

        `lat` and `lon` are sent as the farm's centre point: give both or neither, since half a
        coordinate is not a place. To draw a boundary rather than a point, use update_farm() with
        `boundary_json` and `boundary_method`.
        """
        # POST /api/farm
        return self.request("POST", "/api/farm",
            fields={"name": name, "center_json": _center_json(lat, lon)})

    def list_farms(self) -> dict:
        """Farms of the logged-in account, each with its tree and animal counts.
        Other people's farms are never listed.
        """
        # GET /api/farms
        return self.request("GET", "/api/farms")

    def get_farm(self, farm_id) -> dict:
        """One farm with its trees and animals.

        A farm that belongs to somebody else and a farm that does not exist both answer 403, so
        nobody can count another person's farms by walking identifiers.
        """
        # GET /api/farm/{farm_id}
        return self.request("GET", f"/api/farm/{_quote(farm_id)}")

    def update_farm(self, farm_id, **fields) -> dict:
        """Change a farm. Only the fields you send change.

        Accepted: `name`, `kind`, `boundary_json`, `center_json`, `boundary_method` (`gps_walk`,
        `map_draw`, `mixed`), `boundary_acc_m`, `note`. Field names go through under the server's
        own spelling - a renaming layer here would be one more thing to keep in step.

        Lists and mappings are JSON-encoded on the way out, so boundary_json=[[lat, lon], ...]
        works as written.

        Sending a new boundary WITHOUT a new `boundary_method` resets the boundary's provenance to
        unknown: a new outline does not inherit the credibility of the old one.
        """
        # POST /api/farm/{farm_id}/update
        _fields = _encode_containers(fields)
        return self.request("POST", f"/api/farm/{_quote(farm_id)}/update",
            fields=_fields)

    def delete_farm(self, farm_id) -> dict:
        """Delete a farm.

        The trees are NOT deleted: they lose their `farm_id` and stay traceable on their own. Any
        read-access grants scoped to that farm are revoked with it - a grant does not outlive the
        thing it was granted on.
        """
        # DELETE /api/farm/{farm_id}
        return self.request("DELETE", f"/api/farm/{_quote(farm_id)}")

    def submit_verdict(self, query_id, verdict, *, correct_tree_id=None) -> dict:
        """Record whether a tree identification was right.

        `query_id` comes from identify_tree() and joins the two together. `verdict` is `correct`,
        `wrong` or `other`. When it was wrong and you know which tree it really was, pass
        `correct_tree_id`; a tree belonging to somebody else is ignored rather than refused,
        because this is a label, not an access request.

        This is the call an integration is tempted to skip, and the one that pays: a "no" with the
        right answer attached is how the gallery learns which individuals look alike.
        """
        # POST /api/identify_verdict
        return self.request("POST", "/api/identify_verdict",
            fields={"query_id": query_id, "verdict": verdict, "correct_tid": correct_tree_id})

    def submit_fruit_verdict(self, query_id, verdict, *, correct_fruit_id=None) -> dict:
        """Same shape as submit_verdict(), for fruit. `query_id` comes from identify_fruit().
        """
        # POST /api/fruit/identify_verdict
        return self.request("POST", "/api/fruit/identify_verdict",
            fields={"query_id": query_id, "verdict": verdict, "correct_fruit_id": correct_fruit_id})

    def submit_animal_verdict(self, query_id, verdict, *, correct_did=None) -> dict:
        """Same shape again, for animals.

        `verdict` may also be `unknown_ok`: the animal was never enrolled and the server was right
        to say it did not know.
        """
        # POST /api/animal/identify_verdict
        return self.request("POST", "/api/animal/identify_verdict",
            fields={"query_id": query_id, "verdict": verdict, "correct_did": correct_did})

    def capture_plan(self, entity_type, entity_id) -> dict:
        """What is missing and what to photograph NEXT.

        `entity_type` is `tree` or `fruit`. Anything else answers 422 - so handle that, do not
        assume. **Whether `animal` is accepted is UNRESOLVED**: the server's own endpoint contract
        restricts `target_type` to `tree|fruit`, an earlier revision of this SDK documented
        `animal` as working, and `/openapi.json` types the parameter as a plain string and settles
        nothing. Until somebody measures it against a live account, treat `animal` as unsupported
        and catch the 422. Guessing in the permissive direction here means shipping a capture
        screen that dies in an orchard.

        Worth calling twice: when the capture screen opens, so the user reads "this fruit is
        missing its underside" instead of "4 photos taken", and again right after a rejection,
        which turns a refusal into a task. The server takes an `after_reject` query parameter for
        that second call which this method does not yet pass; use request() if you need it.

        `have_kind` says how to read `have`: `faces` (fruit, counted by face) or `coverage`
        (counted by photo).
        """
        # GET /api/capture/plan
        return self.request("GET", "/api/capture/plan",
            params={"target_type": entity_type, "target_id": entity_id})

    def provenance(self, tree_id) -> dict:
        """Code, image addresses, record address, hashes, anchoring state - the raw material for
        checking the claims yourself with the verify half of this package.
        """
        # GET /api/provenance/{tree_id}
        return self.request("GET", f"/api/provenance/{_quote(tree_id)}")

    def timeline(self, entity_type, entity_id) -> dict:
        """Every event recorded against one subject.

        `entity_type` is `tree`, `fruit`, `farm`, `animal` or `plot`. A stranger sees the public,
        approved events; the owner sees all of them.
        """
        # GET /api/{entity_type}/{entity_id}/timeline
        return self.request("GET", f"/api/{entity_type}/{_quote(entity_id)}/timeline")

    def proof(self, entity_type, entity_id, event_id) -> dict:
        """The Merkle path proving one event belongs to the root anchored on chain.
        """
        # GET /api/{entity_type}/{entity_id}/proof/{event_id}
        return self.request("GET", f"/api/{entity_type}/{_quote(entity_id)}/proof/{_quote(event_id)}")

    def add_event(self, entity_type, entity_id, kind, data=None) -> dict:
        """Append one event to a subject's timeline.

        `kind` is the short name of what happened (`observe`, `water`, `harvest`, ...). `data` is
        free-form and is sent as the event payload; nothing in it is interpreted here.

        The owner's events arrive public and approved; an outsider's arrive private and pending the
        owner's approval. A subject that was never enrolled answers 403 - a timeline cannot exist
        before an owner does, otherwise writing the first event would be a way to claim somebody
        else's tree.

        `suggest_anchor` true means the server thinks it is worth anchoring now. It never anchors
        by itself: anchoring costs money and belongs to the owner. To set the envelope fields the
        timeline also accepts (`media`, `gps`, `quality`, `visibility`, `review`, `anchor_now`),
        call request() directly with your own JSON body.
        """
        # POST /api/{entity_type}/{entity_id}/event
        return self.request("POST", f"/api/{entity_type}/{_quote(entity_id)}/event",
            json_body={"kind": kind, "payload": data or {}})

    def anchor_event(self, entity_type, entity_id, event_id) -> dict:
        """Anchor the subject's timeline on Cardano.

        `event_id` is the event the user pressed "seal" on; the whole chain up to now is folded
        into one root and that root is what goes on chain, so one anchoring covers the entire
        history. Only the owner may do it - anyone else, and any subject without a known owner,
        gets 403. A chain transaction that fails downstream surfaces as ServerError (502).

        A WRITE endpoint that costs money on chain: never retried automatically.
        """
        # POST /api/{entity_type}/{entity_id}/event/{event_id}/anchor
        return self.request("POST", f"/api/{entity_type}/{_quote(entity_id)}/event/{_quote(event_id)}/anchor")
