/**
 * OriLife API client for browsers, Node and agents. No dependencies.
 *
 * Uses `fetch` and `FormData`, both available everywhere this package targets (browsers, Node 18+,
 * Deno, Bun, Cloudflare Workers). No dependencies means nothing to update because of somebody
 * else's security advisory, and a file you can read with your own eyes is a file you can audit
 * with your own eyes.
 *
 * This file holds the TRANSPORT and nothing else: headers, retries, error typing, decoding. The
 * endpoint methods live in `generated.js`, written by `tools/generate.py` from
 * `contract/methods.json` — the one place where "which path, which field name, which file field"
 * is recorded, for every language this SDK is published in.
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
import { CONTRACT_VERSION, GeneratedMethods } from './generated.js';
import { toBlob } from './wire.js';

export const DEFAULT_BASE_URL = 'https://api.orilife.io';
export { CONTRACT_VERSION };

const IDEMPOTENT = new Set(['GET', 'HEAD']);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export class Client extends GeneratedMethods {
  /**
   * @param {string} baseUrl
   * @param {{token?: string, timeout?: number, maxRetries?: number, fetch?: Function}} [opts]
   */
  constructor(baseUrl = DEFAULT_BASE_URL, opts = {}) {
    super();
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
  async request(method, path, {
    params, fields, files, json, timeout,
  } = {}) {
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
          : `Could not reach the server: ${e && e.message}`, { path },
      );
    } finally {
      if (timer) clearTimeout(timer);
    }

    const text = await resp.text();
    let payload;
    try { payload = text ? JSON.parse(text) : {}; } catch { payload = { error: text.slice(0, 400) }; }
    if (!resp.ok) throw fromResponse(resp.status, payload, { path, headers: resp.headers });
    return payload;
  }

  /** Hold on to the token an authentication endpoint just handed back. */
  _keep(data) { if (data && data.token) this.token = data.token; return data; }

  // ── the one method that is not a single HTTP call ─────────────────────────────────────────

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
}
