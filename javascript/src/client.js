/**
 * OriLife API client for browsers, Node and agents. No dependencies.
 *
 * Uses `fetch` and `FormData`, both available everywhere this package targets (browsers, Node 18+,
 * Deno, Bun, Cloudflare Workers). No dependencies means nothing to update because of somebody
 * else's security advisory, and a file you can read with your own eyes is a file you can audit
 * with your own eyes.
 *
 * Since 2026-08 the server opens CORS to every origin with `allow_credentials=false`, so a web page
 * served from any origin can call it. The trade-off: session cookies do NOT travel with
 * cross-origin calls — the token has to ride in an `Authorization: Bearer` header. That is why this
 * package never touches cookies anywhere.
 *
 * Three things it does for you that hand-rolled code forgets:
 *   • Waits the way the server asked when you are rate limited (reads `Retry-After`, never invents
 *     its own pace).
 *   • Retries only what is safe to retry — a WRITE endpoint that failed midway may already have
 *     created the record.
 *   • Never interprets the internals: unknown fields in a response are handed straight to your app.
 */
import { NetworkError, NotFoundError, RateLimitedError, ServerError, fromResponse } from './errors.js';

export const DEFAULT_BASE_URL = 'https://api.orilife.io';

const IDEMPOTENT = new Set(['GET', 'HEAD']);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** One file: a Blob/File, or { name, data } where data is a Blob/ArrayBuffer/Uint8Array. */
function toBlob(item) {
  if (typeof Blob !== 'undefined' && item instanceof Blob) return { blob: item, name: item.name || 'upload.jpg' };
  if (item && item.data !== undefined) {
    const data = item.data instanceof Uint8Array || item.data instanceof ArrayBuffer
      ? new Blob([item.data], { type: item.type || 'image/jpeg' })
      : item.data;
    return { blob: data, name: item.name || 'upload.jpg' };
  }
  throw new TypeError('a file must be a Blob/File or { name, data }');
}

/**
 * The fruit endpoints record ONE photo per call.
 *
 * Sending several parts named `file` would not upload several views — the server reads the first
 * one and the rest vanish without a word. Losing a photo in silence is worse than an error, so this
 * refuses instead: enrol with one view, then add the others one call at a time.
 */
function oneImage(images, endpoint, hint) {
  const list = Array.isArray(images) ? images : [images];
  if (list.length !== 1) throw new TypeError(`${endpoint} takes exactly one image per call; ${hint}`);
  return list[0];
}

/**
 * Turn a bounding box into the four form fields the server expects.
 *
 * Accepts `[x, y, w, h]` or `{ x, y, w, h }`. Anything else throws, because a box that is quietly
 * ignored means the fruit is enrolled from the whole photo instead of from the fruit — a wrong
 * record rather than a visible error.
 */
function bboxFields(bbox) {
  if (bbox === undefined || bbox === null) return {};
  let box;
  if (Array.isArray(bbox)) {
    box = bbox;
    if (box.length !== 4) throw new TypeError('bbox must hold exactly four numbers: [x, y, w, h]');
  } else if (typeof bbox === 'object') {
    box = ['x', 'y', 'w', 'h'].map((k) => {
      if (bbox[k] === undefined) throw new TypeError(`bbox object is missing key '${k}'; expected x, y, w, h`);
      return bbox[k];
    });
  } else {
    throw new TypeError('bbox must be [x, y, w, h] or { x, y, w, h }');
  }
  return { bbox_x: box[0], bbox_y: box[1], bbox_w: box[2], bbox_h: box[3] };
}

export class Client {
  /**
   * @param {string} baseUrl
   * @param {{token?: string, timeout?: number, maxRetries?: number, fetch?: Function}} [opts]
   */
  constructor(baseUrl = DEFAULT_BASE_URL, opts = {}) {
    this.baseUrl = String(baseUrl).replace(/\/+$/, '');
    this.token = opts.token || null;
    this.timeout = opts.timeout ?? 30000;
    this.maxRetries = opts.maxRetries ?? 2;
    this._fetch = opts.fetch || ((...a) => globalThis.fetch(...a));
    this._declaredPaths = null;   // the endpoint index, read once by supports()
  }

  headers(extra) {
    const h = { Accept: 'application/json', ...(extra || {}) };
    if (this.token) h.Authorization = `Bearer ${this.token}`;
    return h;
  }

  /** Call one endpoint. Throws a typed error when the far side refuses; returns decoded data. */
  async request(method, path, { params, fields, files, json, timeout } = {}) {
    let url = this.baseUrl + path;
    if (params) {
      const q = new URLSearchParams();
      for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null) q.set(k, v);
      if ([...q].length) url += `?${q}`;
    }

    let body;
    const extra = {};
    if (files && files.length) {
      const form = new FormData();
      for (const [k, v] of Object.entries(fields || {})) {
        // Empty fields are DROPPED, never sent as the string "null" — sending it builds junk data
        // at the other end.
        if (v !== undefined && v !== null) form.append(k, String(v));
      }
      for (const [k, item] of files) {
        const { blob, name } = toBlob(item);
        form.append(k, blob, name);
      }
      body = form;   // Do NOT set Content-Type: the multipart boundary comes from fetch.
    } else if (json !== undefined) {
      body = JSON.stringify(json);
      extra['Content-Type'] = 'application/json';
    } else if (fields) {
      const form = new URLSearchParams();
      for (const [k, v] of Object.entries(fields)) if (v !== undefined && v !== null) form.set(k, v);
      body = form;
      extra['Content-Type'] = 'application/x-www-form-urlencoded';
    }

    for (let attempt = 0; ; attempt += 1) {
      try {
        return await this._once(method, url, body, extra, timeout ?? this.timeout, path);
      } catch (e) {
        const isRate = e instanceof RateLimitedError;
        const retryable = isRate || ((e instanceof ServerError || e instanceof NetworkError)
          && IDEMPOTENT.has(method.toUpperCase()));
        if (!retryable || attempt >= this.maxRetries) throw e;
        // Rate limiting is the ONE case where we sleep on the other side's number instead of our
        // own formula — it knows its queue, we do not.
        await sleep(isRate ? Math.min(e.retryAfter * 1000, 60000) : Math.min(2 ** attempt * 1000, 8000));
      }
    }
  }

  async _once(method, url, body, extra, timeout, path) {
    const ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    const timer = ctrl ? setTimeout(() => ctrl.abort(), timeout) : null;
    let resp;
    try {
      resp = await this._fetch(url, {
        method: method.toUpperCase(),
        headers: this.headers(extra),
        body,
        signal: ctrl ? ctrl.signal : undefined,
      });
    } catch (e) {
      throw new NetworkError(
        e && e.name === 'AbortError' ? 'The server did not answer in time.'
          : `Could not reach the server: ${e && e.message}`, { path });
    } finally {
      if (timer) clearTimeout(timer);
    }

    const text = await resp.text();
    let payload;
    try { payload = text ? JSON.parse(text) : {}; } catch { payload = { error: text.slice(0, 400) }; }
    if (!resp.ok) throw fromResponse(resp.status, payload, { path, headers: resp.headers });
    return payload;
  }

  // ── authentication ────────────────────────────────────────────────────────────────────────

  /**
   * Open an account. Usernames are 3–32 characters, lowercase letters, digits, dots and
   * underscores only — NO hyphens. Passwords are at least 10 characters, use at least two
   * character classes, and must not appear in the common-password list. Break a rule and the
   * server answers 400 with a sentence saying exactly what is wrong.
   */
  async signup(username, password) { return this._keep(await this.request('POST', '/api/signup', { json: { username, password } })); }
  async login(username, password) { return this._keep(await this.request('POST', '/api/login', { json: { username, password } })); }
  _keep(data) { if (data && data.token) this.token = data.token; return data; }
  me() { return this.request('GET', '/api/me'); }

  /** End THIS session and forget the token held here. */
  async logout() { const o = await this.request('POST', '/api/logout'); this.token = null; return o; }

  /**
   * End every session of this account, on every device — the answer to a lost phone or a token
   * that may have leaked.
   *
   * The server raises the account's token version, so every token issued so far stops working,
   * including ones this process never saw. The token held here dies with them, so the next call
   * raises AuthError until you `login()` again.
   */
  async logoutAll() { const o = await this.request('POST', '/api/logout-all'); this.token = null; return o; }

  // ── public endpoints: callable while signed OUT ───────────────────────────────────────────

  /** Is the server alive, and what can it do today. Read `features` before choosing a screen. */
  health() { return this.request('GET', '/api/health'); }

  /**
   * Machine-readable service descriptor — which endpoints need no token, what the size caps are,
   * which kinds have a working lane.
   *
   * Only present on servers that declare it in `GET /api`. Ask first, do not assume:
   * `if (await client.supports('/.well-known/orilife.json')) { … }`.
   */
  describe() { return this.request('GET', '/.well-known/orilife.json'); }

  /**
   * The server's own endpoint listing from `GET /api`:
   * `{ count, docs, openapi, routes: [{ path, methods, summary }, …] }`.
   * For a yes/no question about one path, `supports()` is the cheap way to ask.
   */
  endpoints() { return this.request('GET', '/api'); }

  /**
   * Does this server declare `path` (for example `'/api/identify/auto'`)?
   *
   * Reads `GET /api` ONCE per client and remembers the answer, so calling this in a loop costs one
   * request in total. A server that does not serve `/api` at all answers 404, and then this returns
   * false instead of throwing — "I cannot ask" and "the answer is no" lead to the same decision
   * here: do not call that endpoint.
   *
   * Compare against paths exactly as the server declares them, templates included:
   * `supports('/api/farm/{farm_id}')` is true, `supports('/api/farm/abc123')` is not.
   *
   * Errors other than 404 (no network, server down) are NOT swallowed: they mean the question was
   * never answered, so nothing is cached and a later call asks again.
   */
  async supports(path) {
    if (this._declaredPaths === null) {
      try {
        const data = await this.request('GET', '/api');
        const routes = (data && Array.isArray(data.routes)) ? data.routes : [];
        this._declaredPaths = new Set(
          routes.filter((r) => r && r.path).map((r) => String(r.path)),
        );
      } catch (e) {
        if (!(e instanceof NotFoundError)) throw e;
        this._declaredPaths = new Set();
      }
    }
    let wanted = String(path || '').trim().split('?')[0];
    if (!wanted) return false;
    if (!wanted.startsWith('/')) wanted = `/${wanted}`;
    if (wanted.length > 1) wanted = wanted.replace(/\/+$/, '');
    return this._declaredPaths.has(wanted);
  }

  speciesCatalog() { return this.request('GET', '/api/species/catalog'); }

  /**
   * Look up an `ORI-…` code. Three states: `public`, `restricted`, `unknown`.
   * `unknown` comes with NO reason — if "wrong code" answered differently from "private code",
   * anyone scanning codes could count somebody else's orchard. Never infer existence from a
   * difference in the answer.
   */
  resolve(code) { return this.request('GET', `/api/resolve/${encodeURIComponent(code)}`); }

  /**
   * Provenance of one tree by the CODE printed on the slip — for buyers, no account needed.
   * A private tree and a tree that does not exist return the SAME 404. Do not write "wrong code"
   * on the screen.
   */
  treeByCode(code) { return this.request('GET', `/api/tree_by_code/${encodeURIComponent(code)}`); }

  /** One photo of a fruit → candidates in the public set. No account, no data kept about anyone. */
  lookupFruit(image) { return this.request('POST', '/api/fruit/lookup', { files: [['file', image]] }); }

  // ── identification ────────────────────────────────────────────────────────────────────────

  /**
   * ONE endpoint for every kind: the machine works out whether it is looking at a tree, a fruit or
   * an animal and identifies it in the same call — your app never has to ask the user what they are
   * photographing. Returns `kind`, `lane` (the endpoint that ran) and `result`, which is the
   * verbatim response of that endpoint. Animals additionally need `species` + `farmId`; without
   * them `result` is null and `need` lists those two fields, because the server does not guess a
   * species on your behalf.
   *
   * Only present on servers that declare it in `GET /api`, so check before you call:
   * `if (await client.supports('/api/identify/auto')) { … }`. When it is absent this SDK does NOT
   * quietly fall back to another endpoint — changing behaviour in silence is a worse failure than
   * an error.
   */
  identifyAuto(images, { lat, lon, species, farmId } = {}) {
    return this.request('POST', '/api/identify/auto', {
      fields: { lat, lon, species, farm_id: farmId },
      files: images.map((f) => ['files', f]),
    });
  }

  identifyTree(images, { lat, lon, lastTree } = {}) {
    return this.request('POST', '/api/identify', {
      fields: { lat, lon, last_tree: lastTree, source: 'sdk' },
      files: images.map((f) => ['files', f]),
    });
  }

  /** Walk once around the tree instead of taking separate shots. The clip is NOT stored. */
  identifyTreeVideo(video, { lat, lon } = {}) {
    return this.request('POST', '/api/identify/video', {
      fields: { lat, lon, source: 'sdk' }, files: [['file', video]], timeout: Math.max(this.timeout, 120000),
    });
  }

  identifyFruit(image, { treeId } = {}) {
    return this.request('POST', '/api/fruit/identify', { fields: { tree_id: treeId }, files: [['file', image]] });
  }

  identifyAnimal(image, { species, farmId }) {
    return this.request('POST', '/api/animal/identify', {
      fields: { species, farm_id: farmId }, files: [['image', image]],
    });
  }

  /** Only asks WHAT AM I LOOKING AT, no identification. Use it to drive your own flow. */
  identifyKind(image) { return this.request('POST', '/api/kind', { files: [['file', image]] }); }

  /**
   * One button for animals: the server works out the species from the orchard's profile, then
   * identifies the individual.
   *
   * `species` is an override — send it once the user has confirmed the species, to skip the
   * automatic step. `farmId` is required. Only individuals of the signed-in account are searched.
   */
  scanAnimal(image, { farmId, species } = {}) {
    return this.request('POST', '/api/animal/scan', {
      fields: { farm_id: farmId, species }, files: [['image', image]],
    });
  }

  // ── enrolment ─────────────────────────────────────────────────────────────────────────────

  /**
   * Enrol a new tree. This is a WRITE endpoint: this package does NOT resend it on failure,
   * because the request may already have arrived. Catch NetworkError and call `listTrees()` before
   * sending it again.
   */
  enrollTree(images, { name, lat, lon, farmId, species } = {}) {
    return this.request('POST', '/api/enroll', {
      fields: { name, lat, lon, farm_id: farmId, species },
      files: images.map((f) => ['files', f]),
    });
  }

  verifyAdd(treeId, images) {
    return this.request('POST', '/api/verify_add', {
      fields: { tree_id: treeId }, files: images.map((f) => ['files', f]),
    });
  }

  listTrees({ farmId } = {}) { return this.request('GET', '/api/trees', { params: { farm_id: farmId } }); }

  /**
   * Enrol one fruit on the tree `treeId`.
   *
   * `bbox` marks where the fruit sits in the frame, as `[x, y, w, h]` or `{ x, y, w, h }`; without
   * it the whole frame is used. The endpoint takes exactly ONE photo per call, so `images` must
   * hold one item — more than one throws here rather than letting the extra photos be dropped in
   * silence. Add the other angles afterwards with `addFruitView()`.
   *
   * A WRITE endpoint: never retried automatically.
   */
  enrollFruit(images, { treeId, name, bbox } = {}) {
    const file = oneImage(images, '/api/fruit/enroll', 'add further angles with addFruitView()');
    return this.request('POST', '/api/fruit/enroll', {
      fields: { tree_id: treeId, name, ...bboxFields(bbox) },
      files: [['file', file]],
    });
  }

  /**
   * Add another angle to a fruit that is already enrolled. One photo per call, like
   * `enrollFruit()`; call it again for the next angle.
   *
   * Angles gathered over the weeks are what make a fruit recognisable later — one more view next
   * week is worth more than ten views this morning.
   */
  addFruitView(fruitId, images) {
    const file = oneImage(images, '/api/fruit/add_view', 'call it once per angle');
    return this.request('POST', '/api/fruit/add_view', {
      fields: { fruit_id: fruitId }, files: [['file', file]],
    });
  }

  /**
   * Enrol one animal. `species` and `farmId` are required: unlike a tree, the herd an animal
   * belongs to is not something the photograph can tell you.
   */
  enrollAnimal(images, { species, farmId, name, ownerDid }) {
    return this.request('POST', '/api/animal/enroll', {
      fields: { species, farm_id: farmId, name, owner_did: ownerDid },
      files: images.map((f) => ['images', f]),
    });
  }

  /**
   * Animals of the signed-in account, paged. Filter by `farmId` or `species`; page with `limit`
   * and `offset`. The server clamps `limit` to its own maximum, so asking for a huge page returns
   * the server's page size rather than an error.
   */
  listAnimals({ farmId, species, limit, offset } = {}) {
    return this.request('GET', '/api/animal/list', {
      params: { farm_id: farmId, species, limit, offset },
    });
  }

  // ── orchards ──────────────────────────────────────────────────────────────────────────────

  /**
   * Create an orchard. The owner is taken from the token, never from the caller.
   *
   * `lat`/`lon` are sent as the orchard's centre point: give both or neither, since half a
   * coordinate is not a place. To draw a boundary rather than a point, use
   * `updateFarm(farmId, { boundary_json: JSON.stringify([[lat, lon], …]), boundary_method: 'gps_walk' })`.
   *
   * A WRITE endpoint: never retried automatically.
   */
  createFarm(name, { lat, lon } = {}) {
    const hasCentre = lat !== undefined && lat !== null && lon !== undefined && lon !== null;
    return this.request('POST', '/api/farm', {
      fields: { name, center_json: hasCentre ? JSON.stringify([lat, lon]) : undefined },
    });
  }

  /** Every orchard of the signed-in account, each with its tree and animal counts. */
  listFarms() { return this.request('GET', '/api/farms'); }

  getFarm(farmId) { return this.request('GET', `/api/farm/${encodeURIComponent(farmId)}`); }

  /**
   * Change fields of one orchard. Keys go through UNTOUCHED, under the server's own names
   * (`name`, `kind`, `note`, `boundary_json`, `center_json`, …) — a renaming layer here would be
   * one more thing to keep in step with the server, and it would silently drop whatever it did not
   * know about. Fields you do not send are left alone.
   */
  updateFarm(farmId, fields = {}) {
    return this.request('POST', `/api/farm/${encodeURIComponent(farmId)}/update`, { fields });
  }

  /** Delete an orchard. A WRITE endpoint: never resent automatically. */
  deleteFarm(farmId) { return this.request('DELETE', `/api/farm/${encodeURIComponent(farmId)}`); }

  // ── telling the system it was wrong ───────────────────────────────────────────────────────

  /**
   * Record whether a tree identification was right.
   *
   * `queryId` comes from the `identifyTree()` answer and joins the two together; `verdict` is
   * `correct`, `wrong` or `other`. When it was wrong and you know which tree it really was, pass
   * `correctTreeId` — a tree belonging to somebody else is ignored rather than refused, because
   * this is a label, not an access request.
   *
   * This is the call an integration is tempted to skip, and the one that pays: a "no" with the
   * right answer attached is how the gallery learns which individuals look alike, while a silent
   * "no" teaches nothing.
   */
  submitVerdict(queryId, verdict, { correctTreeId } = {}) {
    return this.request('POST', '/api/identify_verdict', {
      fields: { query_id: queryId, verdict, correct_tid: correctTreeId },
    });
  }

  /** Same shape as `submitVerdict()`, for fruit: `queryId` comes from `identifyFruit()`. */
  submitFruitVerdict(queryId, verdict, { correctFruitId } = {}) {
    return this.request('POST', '/api/fruit/identify_verdict', {
      fields: { query_id: queryId, verdict, correct_fruit_id: correctFruitId },
    });
  }

  /**
   * Same shape again, for animals. `verdict` may also be `unknown_ok`, meaning the animal was
   * never enrolled and the server was right to say it did not know.
   */
  submitAnimalVerdict(queryId, verdict, { correctDid } = {}) {
    return this.request('POST', '/api/animal/identify_verdict', {
      fields: { query_id: queryId, verdict, correct_did: correctDid },
    });
  }

  // ── what to photograph next ───────────────────────────────────────────────────────────────

  /**
   * What is missing and what to photograph NEXT — one endpoint for trees, fruit and animals alike.
   * `entityType` is `tree`, `fruit` or `animal`; anything else answers 422.
   *
   * Worth calling twice: when the capture screen opens, so the user reads "this fruit is missing
   * its underside" instead of "4 photos taken", and again right after a rejection, which turns a
   * refusal into a task. `have_kind` in the answer says how to read `have`: `faces` (fruit, counted
   * by face) or `coverage` (trees and animals, counted by photo).
   */
  capturePlan(entityType, entityId) {
    return this.request('GET', '/api/capture/plan', {
      params: { target_type: entityType, target_id: entityId },
    });
  }

  // ── evidence ──────────────────────────────────────────────────────────────────────────────

  /** Code, image addresses, record address, hash, anchor state — the raw material for self-checks. */
  provenance(treeId) { return this.request('GET', `/api/provenance/${encodeURIComponent(treeId)}`); }
  timeline(entityType, entityId) { return this.request('GET', `/api/${entityType}/${encodeURIComponent(entityId)}/timeline`); }
  /** The Merkle path proving one event belongs to the root anchored on chain. */
  proof(entityType, entityId, eventId) {
    return this.request('GET', `/api/${entityType}/${encodeURIComponent(entityId)}/proof/${encodeURIComponent(eventId)}`);
  }

  /**
   * Append one event to a subject's timeline. `entityType` is `tree`, `fruit`, `farm`, `animal` or
   * `plot`; `kind` is the short name of what happened (`observe`, `water`, `harvest`, …); `data` is
   * free-form and is sent as the event payload, with nothing in it interpreted here.
   *
   * The owner's events arrive public and approved; an outsider's arrive private and pending the
   * owner's approval. A subject that was never enrolled answers 403 — a timeline cannot exist
   * before an owner does, otherwise writing the first event would be a way to claim somebody
   * else's tree.
   *
   * `suggest_anchor` in the answer means the server thinks it is worth calling `anchorEvent()` now.
   * It never anchors by itself: anchoring costs money and belongs to the owner.
   *
   * To set the envelope fields the timeline also accepts (`media`, `gps`, `quality`, `visibility`,
   * `review`, `anchor_now`), call `request()` directly with your own JSON body.
   *
   * A WRITE endpoint: never retried automatically.
   */
  addEvent(entityType, entityId, kind, data = null) {
    return this.request('POST', `/api/${entityType}/${encodeURIComponent(entityId)}/event`, {
      json: { kind, payload: data || {} },
    });
  }

  /**
   * Anchor the subject's timeline on Cardano.
   *
   * `eventId` is the event the user pressed "seal" on; the whole chain up to now is folded into one
   * root and that root is what goes on chain, so one anchoring covers the entire history. Only the
   * owner may do it — anyone else, and any subject without a known owner, gets 403.
   *
   * A WRITE endpoint that costs money on chain: never retried automatically.
   */
  anchorEvent(entityType, entityId, eventId) {
    return this.request('POST', `/api/${entityType}/${encodeURIComponent(entityId)}/event/${encodeURIComponent(eventId)}/anchor`);
  }
}
