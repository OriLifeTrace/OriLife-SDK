/**
 * GENERATED from contract/methods.json — DO NOT EDIT BY HAND.
 *
 * Edit the contract, then run `python3 tools/generate.py`. Edits made directly to this
 * file are lost at the next generation, and CI (`tools/generate.py --check`) goes red on
 * that very commit.
 */
import {
  asFileList, bboxFields, centerJson, csvField, dropEmpty, encodeContainers, jsonObject, oneFile,
  requireArgs,
} from './wire.js';

export const CONTRACT_VERSION = "1.1.0";

/** Every API endpoint, generated from the contract. `Client` inherits this class and provides `request()`. */
export class GeneratedMethods {
  /**
   * Open a new account and keep the token that comes back.
   *
   * Rules: username 3-32 characters, lowercase letters, digits, dots and underscores only -
   * NO hyphens. Password at least 10 characters, at least two character classes, and not in
   * the common-password list. Break a rule and the server answers 400 with a sentence saying
   * exactly which one. Show that sentence.
   *
   * POST /api/signup
   */
  async signup(username, password) {
    requireArgs("signup", { username: username, password: password });
    return this._keep(await this.request("POST", "/api/signup", {
      json: { "username": username, "password": password },
    }));
  }

  /**
   * Get a token. It lives 12 hours; after that every endpoint answers 401 and this client
   * raises AuthError. Catch it and call login() again.
   *
   * Logging back in silently is deliberately NOT done: keeping the password in memory for the
   * whole life of the application, just in case, trades a visible error for an invisible risk.
   *
   * POST /api/login
   */
  async login(username, password) {
    requireArgs("login", { username: username, password: password });
    return this._keep(await this.request("POST", "/api/login", {
      json: { "username": username, "password": password },
    }));
  }

  /**
   * Who this token belongs to. Raises AuthError without a token.
   *
   * GET /api/me
   */
  me() {
    return this.request("GET", "/api/me");
  }

  /**
   * End THIS session and forget the token held here.
   *
   * POST /api/logout
   */
  async logout() {
    const out = await this.request("POST", "/api/logout");
    this.token = null;
    return out;
  }

  /**
   * End every session of this account on every device.
   *
   * Use it when a phone is lost or a token may have leaked: the server raises the account's
   * token version, so every token issued so far stops working - including tokens this process
   * never saw. The token held here is dropped too, so the next call raises AuthError until you
   * log in again. Requires a valid token; without one the server answers 401.
   *
   * POST /api/logout-all
   */
  async logoutAll() {
    const out = await this.request("POST", "/api/logout-all");
    this.token = null;
    return out;
  }

  /**
   * Is the server alive, and what can it do today.
   *
   * Read `features` before deciding which screens to show. That list is generated from the
   * server's real routing table, so it cannot go stale - an application with a hard-coded
   * capability list hides features the server has gained and keeps offering ones it has dropped.
   *
   * GET /api/health
   */
  health() {
    return this.request("GET", "/api/health");
  }

  /**
   * Machine-readable service descriptor: which endpoints need no token, what the size caps are,
   * which kinds of subject have a pipeline.
   *
   * Only servers that declare this path serve it; elsewhere it answers 404 and this raises
   * NotFoundError. That is the correct answer, not a bug. Guard it with supports().
   *
   * GET /.well-known/orilife.json
   */
  describe() {
    return this.request("GET", "/.well-known/orilife.json");
  }

  /**
   * The server's own endpoint listing.
   *
   * Returns {"count", "docs", "openapi", "routes": [{"path", "methods", "summary"}, ...]}.
   * supports() is the cheap way to ask a yes/no question about one path.
   *
   * GET /api
   */
  endpoints() {
    return this.request("GET", "/api");
  }

  /**
   * The species this server knows about.
   *
   * GET /api/species/catalog
   */
  speciesCatalog() {
    return this.request("GET", "/api/species/catalog");
  }

  /**
   * Look up one `ORI-...` code.
   *
   * Three states: `public` (visible), `restricted` (real, the owner has not opened it),
   * `unknown`. `unknown` carries NO reason, and that is deliberate: if "wrong code" answered
   * differently from "private code", someone walking the code space could count another
   * person's orchard. Do not infer existence from a difference - there is none.
   *
   * GET /api/resolve/{code}
   */
  resolve(code) {
    requireArgs("resolve", { code: code });
    return this.request("GET", `/api/resolve/${encodeURIComponent(code)}`);
  }

  /**
   * Provenance of one tree by the CODE printed on a slip - for buyers, no account needed.
   *
   * A private tree and a tree that does not exist both answer 404. Do not print "wrong code".
   *
   * GET /api/tree_by_code/{code}
   */
  treeByCode(code) {
    requireArgs("treeByCode", { code: code });
    return this.request("GET", `/api/tree_by_code/${encodeURIComponent(code)}`);
  }

  /**
   * One photo of a fruit -> candidates in the public set.
   * No account needed, and nothing about the caller is kept.
   *
   * POST /api/fruit/lookup
   */
  lookupFruit(image) {
    requireArgs("lookupFruit", { image: image });
    return this.request("POST", "/api/fruit/lookup", {
      files: [["file", image]],
    });
  }

  /**
   * ONE endpoint for every kind: the server works out whether it is looking at a tree, a fruit
   * or an animal, then identifies the individual. Your application never has to ask the user
   * what they are photographing.
   *
   * Returns `kind`, `lane` (the endpoint that ran) and `result`, the verbatim answer of that
   * endpoint. Animals: the target endpoint still needs `species` and `farm_id`; without them
   * `result` is null and `need` lists those two fields. The server does NOT guess a species,
   * because a guessed species would be written into a record where nobody can check it.
   *
   * Only servers that declare this path serve it. There is no silent fallback to another
   * endpoint. Guard it with supports("/api/identify/auto").
   *
   * POST /api/identify/auto
   */
  identifyAuto(images, { lat, lon, species, farmId } = {}) {
    requireArgs("identifyAuto", { images: images });
    return this.request("POST", "/api/identify/auto", {
      fields: { "lat": lat, "lon": lon, "species": species, "farm_id": farmId },
      files: asFileList(images).map((f) => ["files", f]),
    });
  }

  /**
   * Recognise a tree again. Several photos from several angles work far better than one photo.
   *
   * Coordinates are optional but worth sending: they narrow the search and make the resulting
   * code more stable.
   *
   * Read `decision` to branch, never the numbers beside it. `MATCH`, `UNCERTAIN`, `NO_MATCH`,
   * `MOVED`, `EMPTY_BUCKET`. Treat an unrecognised value as `UNCERTAIN` and ask the person.
   *
   * POST /api/identify
   */
  identifyTree(images, { lat, lon, lastTree } = {}) {
    requireArgs("identifyTree", { images: images });
    return this.request("POST", "/api/identify", {
      fields: { "lat": lat, "lon": lon, "last_tree": lastTree, "source": "sdk" },
      files: asFileList(images).map((f) => ["files", f]),
    });
  }

  /**
   * Walk once around the tree with the camera running instead of taking separate photos.
   * The clip is NOT stored - it is used and dropped.
   *
   * `NO_FRAMES` arrives with HTTP 422 and ok:false, not 200: no usable frame could be taken.
   *
   * POST /api/identify/video
   */
  identifyTreeVideo(video, { lat, lon } = {}) {
    requireArgs("identifyTreeVideo", { video: video });
    return this.request("POST", "/api/identify/video", {
      fields: { "lat": lat, "lon": lon, "source": "sdk" },
      files: [["file", video]],
      timeout: Math.max(this.timeout, 120000),
    });
  }

  /**
   * Recognise a fruit again. `tree_id` narrows the search to one tree; leave it out to search
   * the whole holding. The empty-gallery answer here is `EMPTY_GALLERY`, not `EMPTY_BUCKET`.
   *
   * POST /api/fruit/identify
   */
  identifyFruit(image, { treeId } = {}) {
    requireArgs("identifyFruit", { image: image });
    return this.request("POST", "/api/fruit/identify", {
      fields: { "tree_id": treeId },
      files: [["file", image]],
    });
  }

  /**
   * Recognise an animal again.
   *
   * Both `species` and `farm_id` are required by the server: the herd to compare against is
   * chosen by them, and a wrong herd is a wrong answer. The empty answer is `EMPTY_FARM`.
   *
   * POST /api/animal/identify
   */
  identifyAnimal(image, { species, farmId }) {
    requireArgs("identifyAnimal", { image: image, species: species, farmId: farmId });
    return this.request("POST", "/api/animal/identify", {
      fields: { "species": species, "farm_id": farmId },
      files: [["image", image]],
    });
  }

  /**
   * Ask only WHAT IS IN THE PHOTO, without identifying the individual.
   * Useful when you want to route the flow yourself.
   *
   * POST /api/kind
   */
  identifyKind(image) {
    requireArgs("identifyKind", { image: image });
    return this.request("POST", "/api/kind", {
      files: [["file", image]],
    });
  }

  /**
   * One button for animals: the server works out the species from the farm's profile, then
   * identifies the individual.
   *
   * `species` is an override - send it once the user has confirmed the species, to skip the
   * automatic step. `farm_id` is required. Only individuals of the logged-in account are
   * searched.
   *
   * POST /api/animal/scan
   */
  scanAnimal(image, { farmId, species }) {
    requireArgs("scanAnimal", { image: image, farmId: farmId });
    return this.request("POST", "/api/animal/scan", {
      fields: { "farm_id": farmId, "species": species },
      files: [["image", image]],
    });
  }

  /**
   * Enrol a new tree.
   *
   * A WRITE endpoint: calling it again after the network dropped can create a second tree, so
   * this client does NOT retry it. Catch NetworkError, ask list_trees() whether the tree
   * arrived, and only then send it again.
   *
   * POST /api/enroll
   */
  enrollTree(images, { name, lat, lon, farmId, species }) {
    requireArgs("enrollTree", { images: images, name: name });
    return this.request("POST", "/api/enroll", {
      fields: { "name": name, "lat": lat, "lon": lon, "farm_id": farmId, "species": species },
      files: asFileList(images).map((f) => ["files", f]),
    });
  }

  /**
   * Add more angles to a tree that is already enrolled.
   *
   * `added:false` still arrives as HTTP 200 - read the `added` flag, not the status code. The
   * photos are not lost when it is false; they are held aside.
   *
   * POST /api/verify_add
   */
  verifyAdd(treeId, images) {
    requireArgs("verifyAdd", { treeId: treeId, images: images });
    return this.request("POST", "/api/verify_add", {
      fields: { "tree_id": treeId },
      files: asFileList(images).map((f) => ["files", f]),
    });
  }

  /**
   * Trees of the logged-in account, optionally narrowed to one farm.
   *
   * GET /api/trees
   */
  listTrees({ farmId } = {}) {
    return this.request("GET", "/api/trees", {
      params: { "farm_id": farmId },
    });
  }

  /**
   * Enrol a new fruit on the tree `tree_id`.
   *
   * `bbox` marks where the fruit sits in the frame, as (x, y, w, h) or a mapping with those
   * four keys; without it the whole frame is used. A malformed box raises here rather than
   * silently enrolling the fruit from the whole photo - a wrong record instead of a visible
   * error.
   *
   * The endpoint takes exactly ONE photo per call. Passing more raises here rather than letting
   * the extra photos be dropped in silence. Add the other angles with add_fruit_view().
   *
   * POST /api/fruit/enroll
   */
  enrollFruit(images, { treeId, name, bbox }) {
    requireArgs("enrollFruit", { images: images, treeId: treeId });
    return this.request("POST", "/api/fruit/enroll", {
      fields: { "tree_id": treeId, "name": name, ...bboxFields(bbox) },
      files: [["file", oneFile(images, "/api/fruit/enroll takes exactly one image per call; add further angles with add_fruit_view()")]],
    });
  }

  /**
   * Add another angle to a fruit that is already enrolled. One photo per call.
   *
   * Angles gathered over the weeks are what make a fruit recognisable later - one more view
   * next week is worth more than ten views this morning.
   *
   * POST /api/fruit/add_view
   */
  addFruitView(fruitId, images) {
    requireArgs("addFruitView", { fruitId: fruitId, images: images });
    return this.request("POST", "/api/fruit/add_view", {
      fields: { "fruit_id": fruitId },
      files: [["file", oneFile(images, "/api/fruit/add_view takes exactly one image per call; call it once per angle")]],
    });
  }

  /**
   * Enrol one animal. Note the file field is `images`, not `files`.
   *
   * `species` and `farm_id` are required: unlike a tree, the herd an animal belongs to is not
   * something the photograph can tell you.
   *
   * POST /api/animal/enroll
   */
  enrollAnimal(images, { species, farmId, name, ownerDid }) {
    requireArgs("enrollAnimal", { images: images, species: species, farmId: farmId });
    return this.request("POST", "/api/animal/enroll", {
      fields: { "species": species, "farm_id": farmId, "name": name, "owner_did": ownerDid },
      files: asFileList(images).map((f) => ["images", f]),
    });
  }

  /**
   * Animals of the logged-in account, paged.
   *
   * The server clamps `limit` to its own maximum, so asking for a huge page returns the
   * server's page size rather than an error.
   *
   * GET /api/animal/list
   */
  listAnimals({ farmId, species, limit, offset } = {}) {
    return this.request("GET", "/api/animal/list", {
      params: { "farm_id": farmId, "species": species, "limit": limit, "offset": offset },
    });
  }

  /**
   * Create a farm. The owner is taken from the token, never from the caller.
   *
   * `lat` and `lon` are sent as the farm's centre point: give both or neither, since half a
   * coordinate is not a place. To draw a boundary rather than a point, use update_farm() with
   * `boundary_json` and `boundary_method`.
   *
   * POST /api/farm
   */
  createFarm(name, { lat, lon } = {}) {
    requireArgs("createFarm", { name: name });
    return this.request("POST", "/api/farm", {
      fields: { "name": name, "center_json": centerJson(lat, lon) },
    });
  }

  /**
   * Farms of the logged-in account, each with its tree and animal counts.
   * Other people's farms are never listed.
   *
   * GET /api/farms
   */
  listFarms() {
    return this.request("GET", "/api/farms");
  }

  /**
   * One farm with its trees and animals.
   *
   * A farm that belongs to somebody else and a farm that does not exist both answer 403, so
   * nobody can count another person's farms by walking identifiers.
   *
   * GET /api/farm/{farm_id}
   */
  getFarm(farmId) {
    requireArgs("getFarm", { farmId: farmId });
    return this.request("GET", `/api/farm/${encodeURIComponent(farmId)}`);
  }

  /**
   * Change a farm. Only the fields you send change.
   *
   * Accepted: `name`, `kind`, `boundary_json`, `center_json`, `boundary_method` (`gps_walk`,
   * `map_draw`, `mixed`), `boundary_acc_m`, `note`. Field names go through under the server's
   * own spelling - a renaming layer here would be one more thing to keep in step.
   *
   * Lists and mappings are JSON-encoded on the way out, so boundary_json=[[lat, lon], ...]
   * works as written.
   *
   * Sending a new boundary WITHOUT a new `boundary_method` resets the boundary's provenance to
   * unknown: a new outline does not inherit the credibility of the old one.
   *
   * POST /api/farm/{farm_id}/update
   */
  updateFarm(farmId, fields = {}) {
    requireArgs("updateFarm", { farmId: farmId });
    return this.request("POST", `/api/farm/${encodeURIComponent(farmId)}/update`, {
      fields: encodeContainers(fields),
    });
  }

  /**
   * Delete a farm.
   *
   * The trees are NOT deleted: they lose their `farm_id` and stay traceable on their own. Any
   * read-access grants scoped to that farm are revoked with it - a grant does not outlive the
   * thing it was granted on.
   *
   * DELETE /api/farm/{farm_id}
   */
  deleteFarm(farmId) {
    requireArgs("deleteFarm", { farmId: farmId });
    return this.request("DELETE", `/api/farm/${encodeURIComponent(farmId)}`);
  }

  /**
   * Record whether a tree identification was right.
   *
   * `query_id` comes from identify_tree() and joins the two together. `verdict` is `correct`,
   * `wrong` or `other`. When it was wrong and you know which tree it really was, pass
   * `correct_tree_id`; a tree belonging to somebody else is ignored rather than refused,
   * because this is a label, not an access request.
   *
   * This is the call an integration is tempted to skip, and the one that pays: a "no" with the
   * right answer attached is how the gallery learns which individuals look alike.
   *
   * POST /api/identify_verdict
   */
  submitVerdict(queryId, verdict, { correctTreeId } = {}) {
    requireArgs("submitVerdict", { queryId: queryId, verdict: verdict });
    return this.request("POST", "/api/identify_verdict", {
      fields: { "query_id": queryId, "verdict": verdict, "correct_tid": correctTreeId },
    });
  }

  /**
   * Same shape as submit_verdict(), for fruit. `query_id` comes from identify_fruit().
   *
   * POST /api/fruit/identify_verdict
   */
  submitFruitVerdict(queryId, verdict, { correctFruitId } = {}) {
    requireArgs("submitFruitVerdict", { queryId: queryId, verdict: verdict });
    return this.request("POST", "/api/fruit/identify_verdict", {
      fields: { "query_id": queryId, "verdict": verdict, "correct_fruit_id": correctFruitId },
    });
  }

  /**
   * Same shape again, for animals.
   *
   * `verdict` may also be `unknown_ok`: the animal was never enrolled and the server was right
   * to say it did not know.
   *
   * POST /api/animal/identify_verdict
   */
  submitAnimalVerdict(queryId, verdict, { correctDid } = {}) {
    requireArgs("submitAnimalVerdict", { queryId: queryId, verdict: verdict });
    return this.request("POST", "/api/animal/identify_verdict", {
      fields: { "query_id": queryId, "verdict": verdict, "correct_did": correctDid },
    });
  }

  /**
   * What is missing and what to photograph NEXT.
   *
   * `entity_type` is `tree` or `fruit`. Anything else answers 422 - so handle that, do not
   * assume. **Whether `animal` is accepted is UNRESOLVED**: the server's own endpoint contract
   * restricts `target_type` to `tree|fruit`, an earlier revision of this SDK documented
   * `animal` as working, and `/openapi.json` types the parameter as a plain string and settles
   * nothing. Until somebody measures it against a live account, treat `animal` as unsupported
   * and catch the 422. Guessing in the permissive direction here means shipping a capture
   * screen that dies in an orchard.
   *
   * Worth calling twice: when the capture screen opens, so the user reads "this fruit is
   * missing its underside" instead of "4 photos taken", and again right after a rejection,
   * which turns a refusal into a task. The server takes an `after_reject` query parameter for
   * that second call which this method does not yet pass; use request() if you need it.
   *
   * `have_kind` says how to read `have`: `faces` (fruit, counted by face) or `coverage`
   * (counted by photo).
   *
   * GET /api/capture/plan
   */
  capturePlan(entityType, entityId) {
    requireArgs("capturePlan", { entityType: entityType, entityId: entityId });
    return this.request("GET", "/api/capture/plan", {
      params: { "target_type": entityType, "target_id": entityId },
    });
  }

  /**
   * Code, image addresses, record address, hashes, anchoring state - the raw material for
   * checking the claims yourself with the verify half of this package.
   *
   * GET /api/provenance/{tree_id}
   */
  provenance(treeId) {
    requireArgs("provenance", { treeId: treeId });
    return this.request("GET", `/api/provenance/${encodeURIComponent(treeId)}`);
  }

  /**
   * Every event recorded against one subject.
   *
   * `entity_type` is `tree`, `fruit`, `farm`, `animal` or `plot`. A stranger sees the public,
   * approved events; the owner sees all of them.
   *
   * GET /api/{entity_type}/{entity_id}/timeline
   */
  timeline(entityType, entityId) {
    requireArgs("timeline", { entityType: entityType, entityId: entityId });
    return this.request("GET", `/api/${entityType}/${encodeURIComponent(entityId)}/timeline`);
  }

  /**
   * The Merkle path proving one event belongs to the root anchored on chain.
   *
   * GET /api/{entity_type}/{entity_id}/proof/{event_id}
   */
  proof(entityType, entityId, eventId) {
    requireArgs("proof", { entityType: entityType, entityId: entityId, eventId: eventId });
    return this.request("GET", `/api/${entityType}/${encodeURIComponent(entityId)}/proof/${encodeURIComponent(eventId)}`);
  }

  /**
   * Append one event to a subject's timeline.
   *
   * `kind` is the short name of what happened (`observe`, `water`, `harvest`, ...). `data` is
   * free-form and is sent as the event payload; nothing in it is interpreted here.
   *
   * The owner's events arrive public and approved; an outsider's arrive private and pending the
   * owner's approval. A subject that was never enrolled answers 403 - a timeline cannot exist
   * before an owner does, otherwise writing the first event would be a way to claim somebody
   * else's tree.
   *
   * `suggest_anchor` true means the server thinks it is worth anchoring now. It never anchors
   * by itself: anchoring costs money and belongs to the owner. To set the envelope fields the
   * timeline also accepts (`media`, `gps`, `quality`, `visibility`, `review`, `anchor_now`),
   * call request() directly with your own JSON body.
   *
   * POST /api/{entity_type}/{entity_id}/event
   */
  addEvent(entityType, entityId, kind, data = null) {
    requireArgs("addEvent", { entityType: entityType, entityId: entityId, kind: kind });
    return this.request("POST", `/api/${entityType}/${encodeURIComponent(entityId)}/event`, {
      json: { "kind": kind, "payload": data || {} },
    });
  }

  /**
   * Anchor the subject's timeline on Cardano.
   *
   * `event_id` is the event the user pressed "seal" on; the whole chain up to now is folded
   * into one root and that root is what goes on chain, so one anchoring covers the entire
   * history. Only the owner may do it - anyone else, and any subject without a known owner,
   * gets 403. A chain transaction that fails downstream surfaces as ServerError (502).
   *
   * A WRITE endpoint that costs money on chain: never retried automatically.
   *
   * POST /api/{entity_type}/{entity_id}/event/{event_id}/anchor
   */
  anchorEvent(entityType, entityId, eventId) {
    requireArgs("anchorEvent", { entityType: entityType, entityId: entityId, eventId: eventId });
    return this.request("POST", `/api/${entityType}/${encodeURIComponent(entityId)}/event/${encodeURIComponent(eventId)}/anchor`);
  }

  /**
   * Step 1 of signing in with a PhoenixKey DID: get a one-time challenge. No token needed.
   *
   * Returns {ok, challenge, ttl}. The challenge lives `ttl` seconds and is consumed by the
   * first verification attempt, right or wrong. Sign the challenge string itself - UTF-8, no
   * prefix, no newline - with the account's P-256 key (ECDSA with SHA-256), then pass the
   * DER-encoded signature, base64, to login_with_did(). Too many requests answer 429.
   *
   * GET /api/auth/did/challenge
   */
  didChallenge() {
    return this.request("GET", "/api/auth/did/challenge");
  }

  /**
   * Step 2: exchange the signed challenge for a token, and keep the token.
   *
   * `signature` is the DER-encoded ECDSA P-256 signature over the challenge, base64. The
   * server takes the DID's public key from PhoenixKey and verifies against THAT key; the
   * optional `pubkey_hex` (uncompressed point, 130 hex characters) must equal it when sent.
   *
   * Returns {ok, token, owner, username}; `owner` is the DID. The token is the same kind
   * login() returns and lives 12 hours. A 401 means the challenge was used, expired or the
   * signature did not verify: ask did_challenge() for a new one. A 503 means PhoenixKey could
   * not be reached - retry later instead of sending the user back to the sign-in screen.
   *
   * POST /api/auth/did/verify
   */
  async loginWithDid(did, challenge, signature, { pubkeyHex } = {}) {
    requireArgs("loginWithDid", { did: did, challenge: challenge, signature: signature });
    return this._keep(await this.request("POST", "/api/auth/did/verify", {
      json: dropEmpty({ "did": did, "challenge": challenge, "signature": signature, "pubkey_hex": pubkeyHex }),
    }));
  }

  /**
   * Everything the server holds for this account, counted, before deleting it.
   *
   * Returns {owner, counts, unreadable, unreadable_vi, not_erasable}. Iterate over the keys
   * actually present in `counts` rather than hard-coding a list. `not_erasable` names what
   * deletion cannot remove (fingerprints already anchored on chain, bytes already on the
   * distributed store); show its text as it is.
   *
   * When any store cannot be read the answer is 503 (ServerError) with the inventory in the
   * error body - never 200 with partial counts that would read as "nothing to lose".
   *
   * GET /api/account/data
   */
  accountData() {
    return this.request("GET", "/api/account/data");
  }

  /**
   * Delete this account and its data. IRREVERSIBLE.
   *
   * `confirm` must be the account's own `owner` value (from me() or account_data()), not a
   * fixed word; anything else answers 400. The account is taken from the token.
   *
   * Returns {ok, planned, deleted, remaining, unreadable, unreadable_vi, not_erasable}.
   * `ok:false` still arrives as HTTP 200: what was deleted is really gone, and `remaining`
   * says what is left. Read `ok`, not the status code.
   *
   * POST /api/account/delete
   */
  deleteAccount(confirm) {
    requireArgs("deleteAccount", { confirm: confirm });
    return this.request("POST", "/api/account/delete", {
      fields: { "confirm": confirm },
    });
  }

  /**
   * Find another account's owner reference by its EXACT username - for example to grant it
   * access. No partial matching, no listing. Returns {ok, owner, username}; an unknown name
   * raises NotFoundError. For a PhoenixKey account the owner is the DID itself.
   *
   * GET /api/account/resolve
   */
  resolveAccount(username) {
    requireArgs("resolveAccount", { username: username });
    return this.request("GET", "/api/account/resolve", {
      params: { "username": username },
    });
  }

  /**
   * Let another account read one of your private farms or trees.
   *
   * `grantee` is that account's owner reference (resolve_account()) or its DID. `scope_type`
   * is `farm` or `tree` and `scope_id` its identifier; only the owner of that farm or tree may
   * grant (403 otherwise). `perms` is a list or a comma-separated string; today the server
   * accepts only `read_private`, and any other permission is refused with 400 naming it.
   * `ttl_days` makes the grant expire; without it the grant does not expire.
   *
   * Send one `client_event_id` per press of the button and reuse it on every retry of that
   * press: a duplicate grant would stay alive after the owner revokes the one they can see.
   * Reusing a key for different content answers 409.
   *
   * POST /api/grant
   */
  createGrant(grantee, scopeType, scopeId, perms, { ttlDays, clientEventId } = {}) {
    requireArgs("createGrant", { grantee: grantee, scopeType: scopeType, scopeId: scopeId, perms: perms });
    return this.request("POST", "/api/grant", {
      fields: { "grantee": grantee, "scope_type": scopeType, "scope_id": scopeId, "perms": csvField(perms), "ttl_days": ttlDays, "client_event_id": clientEventId },
    });
  }

  /**
   * Grants where this account is the grantor or the grantee, newest first. Each carries
   * `live` (active and not expired) and readable labels for the two accounts and the scope.
   *
   * GET /api/grants
   */
  listGrants() {
    return this.request("GET", "/api/grants");
  }

  /**
   * Revoke a grant; it stops working from the next request. Only the grantor can revoke -
   * for anyone else, as for an unknown identifier, the answer is 404.
   *
   * DELETE /api/grant/{grant_id}
   */
  revokeGrant(grantId) {
    requireArgs("revokeGrant", { grantId: grantId });
    return this.request("DELETE", `/api/grant/${encodeURIComponent(grantId)}`);
  }

  /**
   * Recognise a crop-protection, fertiliser or veterinary product from the text on its label,
   * from photos of the pack (up to 5, 10 MB each), or both.
   *
   * `scope` narrows the catalogue to one line of production, for example `sau_rieng`,
   * `ca_phe`, `bo` or `thu_canh`. Returns {ok, candidates[], banned_check} plus `banned[]`,
   * `reason`, `ambiguous` and `message` when they apply.
   *
   * Three fields answer three different questions. `banned` non-empty means a banned or
   * restricted active ingredient was read on the label - dangerous whatever `candidates`
   * holds; a `severity` of `restricted` is NOT a ban. An empty `banned` means clean ONLY when
   * `banned_check` equals `ok`; compare for equality, any other value means "not checked".
   * `reason` explains an empty candidate list, and `ambiguous` true means the top candidates
   * disagree on the withdrawal period, so the user must choose. Show `message` as it is.
   *
   * POST /api/care/match
   */
  matchCareProduct({ text, scope, images } = {}) {
    return this.request("POST", "/api/care/match", {
      fields: { "text": text, "scope": scope },
      files: asFileList(images).map((f) => ["files", f]),
    });
  }

  /**
   * Record one application of a product on a tree, an animal or a whole farm.
   *
   * `target_type` is `tree`, `animal` or `farm`, and `target_id` must be a real subject owned
   * by this account: unknown answers 404, somebody else's 403. `product_id` comes from
   * match_care_product() or list_care_products(). Photos of the pack go under `images`.
   *
   * Returns {ok, care_event_id, withdrawal_until, phi_known}. `withdrawal_until` is the number
   * on the label, not a verdict, and when `phi_known` is false it says nothing about safety:
   * ask withdrawal_status() for the verdict. Send one `client_event_id` per press of the
   * button and reuse it on retries, or one spraying can be recorded twice.
   *
   * POST /api/care/log
   */
  logCare(targetType, targetId, productId, { appliedAt, dose, purpose, farmId, recognitionMethod, clientEventId, images } = {}) {
    requireArgs("logCare", { targetType: targetType, targetId: targetId, productId: productId });
    return this.request("POST", "/api/care/log", {
      fields: { "target_type": targetType, "target_id": targetId, "product_id": productId, "applied_at": appliedAt, "dose": dose, "purpose": purpose, "farm_id": farmId, "recognition_method": recognitionMethod, "client_event_id": clientEventId },
      files: asFileList(images).map((f) => ["files", f]),
    });
  }

  /**
   * The care log of one tree, animal or farm. Every entry carries `phi_known`; an entry
   * with `phi_known` false must not be shown as "safe from date X".
   *
   * GET /api/care/events
   */
  listCareEvents(targetType, targetId) {
    requireArgs("listCareEvents", { targetType: targetType, targetId: targetId });
    return this.request("GET", "/api/care/events", {
      params: { "target_type": targetType, "target_id": targetId },
    });
  }

  /**
   * The product catalogue, for offline caching and manual choice, optionally filtered by
   * `scope` and `category`.
   *
   * GET /api/care/products
   */
  listCareProducts({ scope, category } = {}) {
    return this.request("GET", "/api/care/products", {
      params: { "scope": scope, "category": category },
    });
  }

  /**
   * May this tree, animal or farm be harvested or sold, or is a withdrawal period running?
   *
   * `safe` has THREE states. `true`: the period is over. `false`: still blocked, see
   * `blocked_until` and `days_left`. `null`: UNKNOWN - no reliable period is known for what
   * was applied; block, and show `advice`. Allow only when `safe` is exactly true: reading
   * "not false" as "allowed" turns "unknown" into "sell".
   *
   * `days_left_is_lower_bound` true means show the number as "at least". For animals the
   * `eggmilk` block and `eggmilk_safe` answer the same question for eggs and milk, separately
   * from slaughter; when they are absent they do not apply - absent is not safe. Show
   * `advice[]` rather than translating `flags[]` yourself.
   *
   * GET /api/care/withdrawal
   */
  withdrawalStatus(targetType, targetId) {
    requireArgs("withdrawalStatus", { targetType: targetType, targetId: targetId });
    return this.request("GET", "/api/care/withdrawal", {
      params: { "target_type": targetType, "target_id": targetId },
    });
  }

  /**
   * The catalogue of banned and restricted active ingredients, worldwide, for offline lookup.
   *
   * With `q` the server runs the same detection match_care_product() runs on label text,
   * without recording anything. Returns {ok, count, actives[], severities[], market,
   * sources}. The answer is 503 when the catalogue cannot be loaded - an empty list here
   * would read as "nothing is banned anywhere".
   *
   * GET /api/care/banned
   */
  listBannedSubstances({ q, scope, severity } = {}) {
    return this.request("GET", "/api/care/banned", {
      params: { "q": q, "scope": scope, "severity": severity },
    });
  }

  /**
   * Delete one care record of this account (404 when unknown).
   *
   * Deleting the record does not wash the residue away: a withdrawal period that came from
   * it keeps blocking in withdrawal_status().
   *
   * POST /api/care/delete
   */
  deleteCareEvent(careEventId) {
    requireArgs("deleteCareEvent", { careEventId: careEventId });
    return this.request("POST", "/api/care/delete", {
      fields: { "care_event_id": careEventId },
    });
  }

  /**
   * Interpret laboratory residue measurements of one lot against a market's limits.
   * Read-only: nothing is measured, stored or anchored.
   *
   * `market` is `CN`, `EU` or `Codex`. `measurements` is a list of mappings: `analyte`
   * (required), `grade` (`screening` by default, or `accredited`), `matrix`, `value`, `unit`
   * (`mg/kg` by default), `lod`, `loq`, `uncertainty`, `measured_at`. Set `phi_gate_open` to
   * true while a withdrawal period is still running (see withdrawal_status()); `cd_soil`
   * (mg/kg) and `soil_ph` add a regional risk hint. Options left out are not sent.
   *
   * Returns {ok, verdict, per_analyte, alert, cd_zone_risk_tier}, where `verdict` is
   * `EXPORT_CERTIFIED`, `PASS_INTERNAL`, `HOLD`, `FAIL` or `UNKNOWN`.
   *
   * POST /api/residue/interpret
   */
  interpretResidue(market, measurements, { phiGateOpen, cdSoil, soilPh } = {}) {
    requireArgs("interpretResidue", { market: market, measurements: measurements });
    return this.request("POST", "/api/residue/interpret", {
      json: dropEmpty({ "market": market, "measurements": measurements, "phi_gate_open": phiGateOpen, "cd_soil": cdSoil, "soil_ph": soilPh }),
    });
  }

  /**
   * Rename one of your trees.
   *
   * A name that is empty after cleaning answers HTTP 200 with `ok:false`, and the old name is
   * kept. Read `ok`, not the status code.
   *
   * POST /api/rename
   */
  renameTree(treeId, name) {
    requireArgs("renameTree", { treeId: treeId, name: name });
    return this.request("POST", "/api/rename", {
      fields: { "tree_id": treeId, "name": name },
    });
  }

  /**
   * Delete one of your trees.
   *
   * POST /api/delete
   */
  deleteTree(treeId) {
    requireArgs("deleteTree", { treeId: treeId });
    return this.request("POST", "/api/delete", {
      fields: { "tree_id": treeId },
    });
  }

  /**
   * Give one of your trees its coordinates. Both `lat` and `lon` are required.
   *
   * Call it when an identification answers `needs_location_update: true`. A tree without
   * coordinates is matched against a stricter threshold; adding the location removes the
   * cause, while asking for more photos does not.
   *
   * POST /api/update_location
   */
  updateTreeLocation(treeId, lat, lon) {
    requireArgs("updateTreeLocation", { treeId: treeId, lat: lat, lon: lon });
    return this.request("POST", "/api/update_location", {
      fields: { "tree_id": treeId, "lat": lat, "lon": lon },
    });
  }

  /**
   * Make a tree private or public, without uploading photos again.
   *
   * `visibility` is `private`, `public_readonly` or `public_contributable`. `expose_location`
   * says how much of the location a public page shows: `none`, `geohash_coarse` or `exact`.
   * `public_card` (`1` or `0`) decides whether a stranger holding the code of a PRIVATE tree
   * sees a minimal card. Leaving it out keeps the current setting, which is NOT the same as
   * sending `0`.
   *
   * Turning trees public is rate-limited per account; the refusal is a 429 whose message
   * says how long to wait.
   *
   * POST /api/tree/set_visibility
   */
  setTreeVisibility(treeId, visibility, { exposeLocation, publicCard } = {}) {
    requireArgs("setTreeVisibility", { treeId: treeId, visibility: visibility });
    return this.request("POST", "/api/tree/set_visibility", {
      fields: { "tree_id": treeId, "visibility": visibility, "expose_location": exposeLocation, "public_card": publicCard },
    });
  }

  /**
   * Move one of your trees to another of your farms, or detach it from any farm by leaving
   * `farm_id` out. A tree that is not yours answers 403; a farm that is not yours answers 404.
   *
   * POST /api/tree/set_farm
   */
  setTreeFarm(treeId, { farmId } = {}) {
    requireArgs("setTreeFarm", { treeId: treeId });
    return this.request("POST", "/api/tree/set_farm", {
      fields: { "tree_id": treeId, "farm_id": farmId },
    });
  }

  /**
   * Place a tree on its farm map by hand, in METRES from the farm origin - the units
   * farm_map() returns (`x` east, `z` south). The server converts back to geographic
   * coordinates before storing.
   *
   * 409 means there is nowhere to place it yet: the tree has no farm, or the farm has no
   * origin (no boundary and no tree with coordinates). Fix that and send the same request
   * again. A hand placement is not part of the tree's anchored record.
   *
   * POST /api/tree/set_position
   */
  setTreePosition(treeId, x, z) {
    requireArgs("setTreePosition", { treeId: treeId, x: x, z: z });
    return this.request("POST", "/api/tree/set_position", {
      fields: { "tree_id": treeId, "x": x, "z": z },
    });
  }

  /**
   * Remove a hand placement, so the tree falls back to its measured position.
   *
   * Clearing has to be said explicitly (this sends `clear=1`): an empty `x` or `z` is never
   * read as "clear", because a transport that drops empty fields would otherwise erase
   * placements in silence.
   *
   * POST /api/tree/set_position
   */
  clearTreePosition(treeId) {
    requireArgs("clearTreePosition", { treeId: treeId });
    return this.request("POST", "/api/tree/set_position", {
      fields: { "tree_id": treeId, "clear": "1" },
    });
  }

  /**
   * Set or change the species of one of your trees; leave `species` out to reset it to
   * unknown. This is where a species confirmed with confirm_species() is kept - identify_tree()
   * does not take one.
   *
   * POST /api/tree/set_species
   */
  setTreeSpecies(treeId, { species } = {}) {
    requireArgs("setTreeSpecies", { treeId: treeId });
    return this.request("POST", "/api/tree/set_species", {
      fields: { "tree_id": treeId, "species": species },
    });
  }

  /**
   * Attach a marker label to one side of your tree. `side` is `left`, `right`, `front` or
   * `back`; an empty label or another side answers 400. Returns {ok, markers[]}.
   *
   * POST /api/tree/marker
   */
  addTreeMarker(treeId, label, side) {
    requireArgs("addTreeMarker", { treeId: treeId, label: label, side: side });
    return this.request("POST", "/api/tree/marker", {
      fields: { "tree_id": treeId, "label": label, "side": side },
    });
  }

  /**
   * The stored angles of one of your trees: {tree_id, n, views[]}.
   *
   * Each view's `url` points under `/gimg/`; fetching that image needs the same Authorization
   * header, and without it the answer is 404, not 403.
   *
   * GET /api/tree_views
   */
  treeViews(treeId) {
    requireArgs("treeViews", { treeId: treeId });
    return this.request("GET", "/api/tree_views", {
      params: { "tree_id": treeId },
    });
  }

  /**
   * Remove stored angles of your tree by their index in tree_views(). `indices` is a list of
   * integers or a comma-separated string; it travels as one string such as `0,2,5`. Returns
   * {ok, removed}.
   *
   * POST /api/remove_views
   */
  removeTreeViews(treeId, indices) {
    requireArgs("removeTreeViews", { treeId: treeId, indices: indices });
    return this.request("POST", "/api/remove_views", {
      fields: { "tree_id": treeId, "indices": csvField(indices) },
    });
  }

  /**
   * How far your tree's appearance has drifted since its angles were stored, per channel,
   * and how many days since the last update. Needs at least two stored angles (400 otherwise).
   *
   * GET /api/tree_drift/{tree_id}
   */
  treeDrift(treeId) {
    requireArgs("treeDrift", { treeId: treeId });
    return this.request("GET", `/api/tree_drift/${encodeURIComponent(treeId)}`);
  }

  /**
   * Which sides of your tree are still uncovered, to walk round and fill the gaps.
   *
   * Returns {ok, has_poses, n_poses, quality, gaps[], guidance[]}. A tree without camera poses
   * yet answers a clean empty result (`has_poses:false`), not an error. `guidance` is text to
   * show as it is. A gap whose `reason` is `dropped_input` points at no sector - do not draw
   * it on a coverage ring.
   *
   * GET /api/capture_guidance/{tree_id}
   */
  captureGuidance(treeId) {
    requireArgs("captureGuidance", { treeId: treeId });
    return this.request("GET", `/api/capture_guidance/${encodeURIComponent(treeId)}`);
  }

  /**
   * The SHAPE of your tree over time, from its successive 3D reconstructions. Owner only.
   *
   * Shape, not size: a reconstruction has no absolute scale, so never print "the tree grew
   * 12%". `change_since_first` and `change_since_previous` are null with fewer than two
   * reconstructions - null means not enough data, never "unchanged". Otherwise read
   * `changed_status` (`uncalibrated`, `changed`, `unchanged`) rather than the legacy `changed`
   * boolean, and while `calibration_needed` is true show no statement about growth at all.
   *
   * GET /api/tree/{tree_id}/growth
   */
  treeGrowth(treeId) {
    requireArgs("treeGrowth", { treeId: treeId });
    return this.request("GET", `/api/tree/${encodeURIComponent(treeId)}/growth`);
  }

  /**
   * Point cloud, fruits and skeleton of your tree, centred in one coordinate frame, ready to
   * draw natively. Owner only.
   *
   * A tree not reconstructed yet answers 200 with empty lists; read `meta.status`. The five
   * options travel as query parameters: `max_points` (default 20000), `max_fruits` (300),
   * `max_segments` (5000), `colors` (`0` leaves colours out, about a third lighter) and
   * `format` (`bin` for base64 Float32, about three times lighter). Out-of-range values fall
   * back to the default instead of raising. A busy server answers 429.
   *
   * GET /api/tree/{tree_id}/model3d
   */
  treeModel3d(treeId, { maxPoints, maxFruits, maxSegments, colors, format } = {}) {
    requireArgs("treeModel3d", { treeId: treeId });
    return this.request("GET", `/api/tree/${encodeURIComponent(treeId)}/model3d`, {
      params: { "max_points": maxPoints, "max_fruits": maxFruits, "max_segments": maxSegments, "colors": colors, "format": format },
    });
  }

  /**
   * The same 3D model looked up by the tree's public code, for visitors: no token is needed
   * for a public tree. Same five options as tree_model3d(); `meta` is narrower.
   *
   * GET /api/tree_by_code/{code}/model3d
   */
  publicTreeModel3d(code, { maxPoints, maxFruits, maxSegments, colors, format } = {}) {
    requireArgs("publicTreeModel3d", { code: code });
    return this.request("GET", `/api/tree_by_code/${encodeURIComponent(code)}/model3d`, {
      params: { "max_points": maxPoints, "max_fruits": maxFruits, "max_segments": maxSegments, "colors": colors, "format": format },
    });
  }

  /**
   * The growth profile the owner declared: `variety`, `variety_other`, `age_years`,
   * `health_status`, `last_harvest_date`, `notes`. Each is null (not declared) or
   * {value, source, updated_at}. Read it back instead of trusting a copy kept on the device.
   *
   * GET /api/tree/{tree_id}/profile
   */
  getTreeProfile(treeId) {
    requireArgs("getTreeProfile", { treeId: treeId });
    return this.request("GET", `/api/tree/${encodeURIComponent(treeId)}/profile`);
  }

  /**
   * Declare the growth profile of your tree. The mapping you pass IS the JSON body.
   *
   * Each field has THREE states, set by the presence of its key: key absent keeps the stored
   * value, key set to None (null) deletes it, a value overwrites it. An empty string is
   * refused with 400 - send None to delete. Build the mapping from what the user changed: a
   * form that drops empty inputs turns "delete" into "keep", and nothing reports it.
   *
   * Keys: `variety`, `variety_other`, `age_years` (0-500), `health_status`,
   * `last_harvest_date` (`YYYY-MM-DD`), `notes` (up to 2000 characters). One malformed field
   * rejects the whole request and nothing is written.
   *
   * POST /api/tree/{tree_id}/profile
   */
  updateTreeProfile(treeId, profile) {
    requireArgs("updateTreeProfile", { treeId: treeId, profile: profile });
    return this.request("POST", `/api/tree/${encodeURIComponent(treeId)}/profile`, {
      json: jsonObject(profile, "updateTreeProfile"),
    });
  }

  /**
   * Add angles to one of your EXISTING trees from a walk-around video (up to 80 MB). This
   * does not identify anything.
   *
   * Returns {ok, n_kept, n_parked, n_rejected, stored, retained, durability, offsite_copies,
   * video_cid, message, ...}. `ok` means the original bytes were retained: `ok:true` with
   * `stored:false` is normal - the clip is on the server's disk, waiting to be pushed to
   * storage. `ok:false` arrives as HTTP 200. `stored:true` next to `durability:
   * "under_replicated"` is a valid pair, and `durability: "unknown"` means nobody measured
   * it yet, not that it is fine.
   *
   * POST /api/tree/{tree_id}/video
   */
  addTreeVideo(treeId, video, { lat, lon, note } = {}) {
    requireArgs("addTreeVideo", { treeId: treeId, video: video });
    return this.request("POST", `/api/tree/${encodeURIComponent(treeId)}/video`, {
      fields: { "lat": lat, "lon": lon, "note": note, "source": "sdk" },
      files: [["file", video]],
      timeout: Math.max(this.timeout, 120000),
    });
  }

  /**
   * Attach a video of your tree's fruit to the tree's timeline (up to 80 MB).
   *
   * Returns {ok, video_cid, stored, retained, n_frames, n_fruits_max, fruit_count_method,
   * fruit_count_species_ok, detections[], message, ...}. When `fruit_count_species_ok` is
   * false the counts are null and `detections` is empty: the species has no fruit counter.
   * `ok:true` with `n_frames: 0` means the clip was kept but no usable frame came out -
   * suggest filming more slowly. Pass `fruit_id` to add angles to one fruit from the clip;
   * the outcome is in `fruit_views`.
   *
   * `client_event_id` has a special rule here: only an upload that answered `stored:true` is
   * remembered, so retrying with the same key after `stored:false` really uploads again.
   *
   * POST /api/tree/{tree_id}/fruit_video
   */
  addFruitVideo(treeId, video, { lat, lon, note, fruitId, clientEventId } = {}) {
    requireArgs("addFruitVideo", { treeId: treeId, video: video });
    return this.request("POST", `/api/tree/${encodeURIComponent(treeId)}/fruit_video`, {
      fields: { "lat": lat, "lon": lon, "note": note, "fruit_id": fruitId, "client_event_id": clientEventId, "source": "sdk" },
      files: [["file", video]],
      timeout: Math.max(this.timeout, 120000),
    });
  }

  /**
   * The map of one of your farms in metres from a stated origin, with the SOURCE of each
   * tree's position (`posSource`). `x` points east, `z` points south. A farm that does not
   * exist and a farm that is not yours both answer 404.
   *
   * GET /api/farm/{farm_id}/map
   */
  farmMap(farmId) {
    requireArgs("farmMap", { farmId: farmId });
    return this.request("GET", `/api/farm/${encodeURIComponent(farmId)}/map`);
  }

  /**
   * The older account-wide layout: every tree of the account on one plane, whatever farm it
   * is in. farm_map() is per farm and keeps a stable origin.
   *
   * GET /api/farm/layout
   */
  farmLayout() {
    return this.request("GET", "/api/farm/layout");
  }

  /**
   * The layout of one tree and its fruits. A fruit's `pos` and `pos_source` locate it on a
   * photo of the tree, not in metres on the ground.
   *
   * GET /api/tree/{tree_id}/layout
   */
  treeLayout(treeId) {
    requireArgs("treeLayout", { treeId: treeId });
    return this.request("GET", `/api/tree/${encodeURIComponent(treeId)}/layout`);
  }

  /**
   * Find the fruits in one photo. Returns {ok, n_detected, detections[]}.
   *
   * A tree whose species bears no fruit answers HTTP 200 with `ok:false` and
   * `reason: "species_no_fruit"` - route to the product flow; it is not an error.
   *
   * POST /api/fruit/detect
   */
  detectFruit(image, { treeId } = {}) {
    requireArgs("detectFruit", { image: image });
    return this.request("POST", "/api/fruit/detect", {
      fields: { "tree_id": treeId },
      files: [["file", image]],
    });
  }

  /**
   * The fruits already recorded on tree `tree_id` that this photo could show, without
   * scores. Returns {ok, n, candidates[], message}, at most 200 candidates. `bbox` marks the
   * fruit in the frame, as for enroll_fruit().
   *
   * POST /api/fruit/candidates
   */
  fruitCandidates(image, { treeId, bbox }) {
    requireArgs("fruitCandidates", { image: image, treeId: treeId });
    return this.request("POST", "/api/fruit/candidates", {
      fields: { "tree_id": treeId, ...bboxFields(bbox) },
      files: [["file", image]],
    });
  }

  /**
   * Fruits of the logged-in account, optionally only those of one tree.
   *
   * GET /api/fruit/list
   */
  listFruits({ treeId } = {}) {
    return this.request("GET", "/api/fruit/list", {
      params: { "tree_id": treeId },
    });
  }

  /**
   * One fruit's details. An unknown fruit raises NotFoundError.
   *
   * GET /api/fruit/{fruit_id}
   */
  getFruit(fruitId) {
    requireArgs("getFruit", { fruitId: fruitId });
    return this.request("GET", `/api/fruit/${encodeURIComponent(fruitId)}`);
  }

  /**
   * The stored angles of one fruit. Each `url` points under `/gimg/` and needs the
   * Authorization header.
   *
   * GET /api/fruit/{fruit_id}/views
   */
  fruitViews(fruitId) {
    requireArgs("fruitViews", { fruitId: fruitId });
    return this.request("GET", `/api/fruit/${encodeURIComponent(fruitId)}/views`);
  }

  /**
   * Mark a fruit `on_tree`, `harvested` or `lost`. Returns {ok, status}.
   *
   * The verb is PATCH but the value still travels as a FORM field - a JSON body answers 422.
   * An unknown fruit answers 404, any other status 400.
   *
   * PATCH /api/fruit/{fruit_id}/status
   */
  setFruitStatus(fruitId, status) {
    requireArgs("setFruitStatus", { fruitId: fruitId, status: status });
    return this.request("PATCH", `/api/fruit/${encodeURIComponent(fruitId)}/status`, {
      fields: { "status": status },
    });
  }

  /**
   * Delete a fruit. Returns {ok, fruit_id}; an unknown fruit answers 404.
   *
   * DELETE /api/fruit/{fruit_id}
   */
  deleteFruit(fruitId) {
    requireArgs("deleteFruit", { fruitId: fruitId });
    return this.request("DELETE", `/api/fruit/${encodeURIComponent(fruitId)}`);
  }

  /**
   * The geometry of one of your fruits: an ellipsoid in real centimetres when it could be
   * measured (`shape`), and where it sits on the parent tree's model (`anchor`).
   *
   * `points` is always empty - a fruit has no point cloud of its own. `semi_axes_cm` are
   * SEMI-axes, not diameters. Call it with the `ORI-FRUIT-...` identifier, never with the
   * `anchor_label` of a reconstruction (400).
   *
   * GET /api/fruit/{fruit_id}/model3d
   */
  fruitModel3d(fruitId) {
    requireArgs("fruitModel3d", { fruitId: fruitId });
    return this.request("GET", `/api/fruit/${encodeURIComponent(fruitId)}/model3d`);
  }

  /**
   * Rename one of your animals. A name that is empty after cleaning answers HTTP 200 with
   * `ok:false`, and the old name is kept. An animal that is not yours answers 404.
   *
   * POST /api/animal/rename
   */
  renameAnimal(animalDid, name) {
    requireArgs("renameAnimal", { animalDid: animalDid, name: name });
    return this.request("POST", "/api/animal/rename", {
      fields: { "animal_did": animalDid, "name": name },
    });
  }

  /**
   * Is the animal in this photo the enrolled individual `animal_did`? One-to-one, not a
   * search. Returns {ok, verified, confidence}; `confidence` is a word band, not a score.
   * An animal that is not yours answers 404, an unreadable image 422.
   *
   * POST /api/animal/verify
   */
  verifyAnimal(animalDid, image) {
    requireArgs("verifyAnimal", { animalDid: animalDid, image: image });
    return this.request("POST", "/api/animal/verify", {
      fields: { "animal_did": animalDid },
      files: [["image", image]],
    });
  }

  /**
   * One of your animals' records. Recognition vectors are never returned.
   *
   * GET /api/animal/{animal_did}
   */
  getAnimal(animalDid) {
    requireArgs("getAnimal", { animalDid: animalDid });
    return this.request("GET", `/api/animal/${encodeURIComponent(animalDid)}`);
  }

  /**
   * Delete one of your animals' recognition data. The deletion is logged for audit.
   *
   * DELETE /api/animal/{animal_did}
   */
  deleteAnimal(animalDid) {
    requireArgs("deleteAnimal", { animalDid: animalDid });
    return this.request("DELETE", `/api/animal/${encodeURIComponent(animalDid)}`);
  }

  /**
   * 3D data of one of your animals. Always HTTP 200 - read `available` first.
   *
   * `available: false` comes with `meta.status` `none` (never reconstructed, the usual case)
   * or `failed` (show `reason_vi`). `available: true` comes with `ready`, and then
   * `meta.trust` must be shown next to the model.
   *
   * GET /api/animal/{animal_did}/model3d
   */
  animalModel3d(animalDid) {
    requireArgs("animalModel3d", { animalDid: animalDid });
    return this.request("GET", `/api/animal/${encodeURIComponent(animalDid)}/model3d`);
  }

  /**
   * Settle the SPECIES for the one-button scan flow; this does not identify the individual.
   * A new farm or a single-species farm answers without a photo, so `image` is optional.
   * Returns {ok, detected, need_confirm, source, candidates[], confidence}.
   *
   * POST /api/animal/detect
   */
  detectAnimalSpecies(farmId, { image } = {}) {
    requireArgs("detectAnimalSpecies", { farmId: farmId });
    return this.request("POST", "/api/animal/detect", {
      fields: { "farm_id": farmId },
      files: (image === undefined || image === null) ? [] : [["image", image]],
    });
  }

  /**
   * Growth drift and look-alike warnings for the animals of one of your farms.
   *
   * GET /api/animal/drift/report
   */
  animalDriftReport(farmId) {
    requireArgs("animalDriftReport", { farmId: farmId });
    return this.request("GET", "/api/animal/drift/report", {
      params: { "farm_id": farmId },
    });
  }

  /**
   * Guess a TREE's species from photos (up to 8, 12 MB each).
   *
   * Returns {ok, scan_token, modality, species_guess, confidence, need_confirm, source,
   * top_k[]}. `source: "stub"` means the server has no species prototypes yet and the
   * result carries no information; `need_confirm` is then always true. Let the user choose
   * from `top_k`, and never settle on `species_guess` by yourself when `source` is `stub`.
   *
   * POST /api/scan
   */
  scanSpecies(images) {
    requireArgs("scanSpecies", { images: images });
    return this.request("POST", "/api/scan", {
      files: asFileList(images).map((f) => ["files", f]),
    });
  }

  /**
   * Confirm the species the user chose from scan_species(). The token is single-use, expires
   * and belongs to the account; `species` must be one of the scan's `top_k` (400 otherwise).
   *
   * The returned `route.params.species` is NOT accepted by identify_tree() and would be
   * dropped in silence - `route.params_warning` says so. Keep the species with
   * set_tree_species() once the tree has an identifier.
   *
   * POST /api/scan/confirm
   */
  confirmSpecies(scanToken, species) {
    requireArgs("confirmSpecies", { scanToken: scanToken, species: species });
    return this.request("POST", "/api/scan/confirm", {
      fields: { "scan_token": scanToken, "species": species },
    });
  }

  /**
   * Record a head count for one zone of your farm. Owner only: a farm that is not yours
   * answers 404, like one that does not exist.
   *
   * Returns {ok, count, alerts[]}; an alert is `DROP_SUDDEN`, `DROP_GRADUAL`, `ZONE_EMPTY` or
   * `OVERCROWDED`.
   *
   * POST /api/population/count
   */
  recordPopulationCount(farmId, zoneId, zoneName, count, { method, deviceId } = {}) {
    requireArgs("recordPopulationCount", { farmId: farmId, zoneId: zoneId, zoneName: zoneName, count: count });
    return this.request("POST", "/api/population/count", {
      json: dropEmpty({ "farm_id": farmId, "zone_id": zoneId, "zone_name": zoneName, "count": count, "method": method, "device_id": deviceId }),
    });
  }

  /**
   * The population dashboard of a farm. Readable by its owner and by accounts granted
   * `read_private` on it; anyone else gets 404.
   *
   * GET /api/population/farm/{farm_id}
   */
  populationDashboard(farmId) {
    requireArgs("populationDashboard", { farmId: farmId });
    return this.request("GET", `/api/population/farm/${encodeURIComponent(farmId)}`);
  }

  /**
   * Population alerts of the last 48 hours for a farm, with the same access rule.
   *
   * GET /api/population/alerts/{farm_id}
   */
  populationAlerts(farmId) {
    requireArgs("populationAlerts", { farmId: farmId });
    return this.request("GET", `/api/population/alerts/${encodeURIComponent(farmId)}`);
  }

  /**
   * The PhoenixKey asset identity of a farm, tree or fruit you own.
   *
   * `entity_type` is `tree`, `fruit` or `farm` (422 otherwise). `status: "none"` is neither
   * an error nor a warning: everything else works without an asset identity.
   *
   * GET /api/{entity_type}/{entity_id}/did
   */
  entityDid(entityType, entityId) {
    requireArgs("entityDid", { entityType: entityType, entityId: entityId });
    return this.request("GET", `/api/${entityType}/${encodeURIComponent(entityId)}/did`);
  }

  /**
   * Step 1 of minting an asset identity: the server builds the payload and returns
   * `signing_message_hex` for the owner to sign with their PhoenixKey key.
   *
   * Returns {ok, status: "awaiting_signature", signing_message_hex, signing_inputs,
   * endpoint}, or {ok, already: true, did, status: "assigned"} when one exists.
   * `signing_inputs` lets you rebuild the message and check it before signing. Do not call
   * this again between signing and submitting: a new request carries a new nonce and the
   * earlier signature stops matching.
   *
   * Failures are HTTP 200 with {ok: false, reason, message_vi}; show `message_vi`.
   *
   * POST /api/{entity_type}/{entity_id}/did/request
   */
  requestEntityDid(entityType, entityId) {
    requireArgs("requestEntityDid", { entityType: entityType, entityId: entityId });
    return this.request("POST", `/api/${entityType}/${encodeURIComponent(entityId)}/did/request`);
  }

  /**
   * Step 2: send the owner's signature over `signing_message_hex`. Returns
   * {ok, status: "assigned", did, ...}; failures arrive as in request_entity_did().
   *
   * POST /api/{entity_type}/{entity_id}/did/submit
   */
  submitEntityDid(entityType, entityId, ownerSignature) {
    requireArgs("submitEntityDid", { entityType: entityType, entityId: entityId, ownerSignature: ownerSignature });
    return this.request("POST", `/api/${entityType}/${encodeURIComponent(entityId)}/did/submit`, {
      fields: { "owner_signature": ownerSignature },
    });
  }

  /**
   * The static table of tasks: which operation codes each task declares, in which unit, and
   * whether it is wired into production.
   *
   * No MAGIC price is returned, on purpose: the price comes from the pricing beacon when the
   * transaction is built. The quantity measured for one actual call arrives in that call's
   * own response as `op_declaration`. `max_op_count` is the largest count a JSON reader must
   * hold exactly (2^53 - 1).
   *
   * GET /api/magic/tasks
   */
  magicTasks() {
    return this.request("GET", "/api/magic/tasks");
  }

  /**
   * Send a note to the OriLife team, optionally with a `context` string.
   *
   * POST /api/feedback
   */
  sendFeedback(note, { context } = {}) {
    requireArgs("sendFeedback", { note: note });
    return this.request("POST", "/api/feedback", {
      fields: { "note": note, "context": context },
    });
  }
}
