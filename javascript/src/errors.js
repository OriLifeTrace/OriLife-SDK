/**
 * TYPED errors — so an app can tell apart three things a single error string blends into one:
 * the user's mistake, the app's mistake, and the far side's mistake. Those three call for three
 * completely different responses (show guidance / sign in again / wait and retry), so folding them
 * into one Error pushes the sorting onto whoever writes the app, each of them guessing differently.
 *
 * Every error carries a `message` the server already wrote for the end user to read (Vietnamese
 * today, since that is who is standing in the orchard). Show that sentence as it is; do not
 * translate status codes into wording of your own — the server knows the context, the app does not.
 */

export class OriLifeError extends Error {
  constructor(message, { status = null, payload = null, path = '' } = {}) {
    super(message);
    this.name = new.target.name;
    this.status = status;
    this.payload = payload;
    this.path = path;
  }
}

/** Could not talk to the server. The request may NEVER have arrived — unlike ServerError. */
export class NetworkError extends OriLifeError {}
/** 401 — not signed in, or the token expired. Get a new token and call again. */
export class AuthError extends OriLifeError {}
/** 403 — signed in but not allowed. A new token does NOT help. */
export class PermissionError extends OriLifeError {}
/**
 * 404 — no such thing. Do not write "this tree does not exist" on the screen: many endpoints return
 * 404 for both "does not exist" and "belongs to someone else", so that code scanners cannot count
 * other people's orchards.
 */
export class NotFoundError extends OriLifeError {}
/** 413 — over the cap. Compress it and send again; do not retry it unchanged. */
export class TooLargeError extends OriLifeError {}
/** 400/422 — a missing field, a wrong type, or a rule not met. */
export class InvalidRequestError extends OriLifeError {}
/** 5xx — the request did arrive and the far side broke. Retryable, with widening gaps. */
export class ServerError extends OriLifeError {}

/** 429 — calling too fast. WAIT exactly `retryAfter` seconds; retrying now only extends the block. */
export class RateLimitedError extends OriLifeError {
  constructor(message, opts = {}) {
    super(message, opts);
    this.retryAfter = opts.retryAfter > 0 ? opts.retryAfter : 1;
  }
}

const BY_STATUS = {
  400: InvalidRequestError,
  401: AuthError,
  403: PermissionError,
  404: NotFoundError,
  413: TooLargeError,
  422: InvalidRequestError,
  429: RateLimitedError,
};

/**
 * The sentence meant for the user, in the order of preference the server itself uses. `detail` is
 * the shape produced by the parameter-validation layer, so it is usually a structure rather than a
 * sentence — putting it on screen is the fastest way to land a technical string in front of a
 * farmer.
 */
function messageOf(payload, fallback) {
  if (payload && typeof payload === 'object') {
    for (const key of ['error', 'message']) {
      const v = payload[key];
      if (typeof v === 'string' && v.trim()) return v.trim();
    }
    if (typeof payload.detail === 'string' && payload.detail.trim()) return payload.detail.trim();
  }
  return fallback;
}

export function fromResponse(status, payload, { path = '', headers = null } = {}) {
  const message = messageOf(payload, `The server returned status ${status}.`);
  const Cls = BY_STATUS[status] || (status >= 500 ? ServerError : OriLifeError);
  if (Cls === RateLimitedError) {
    let after = Number(headers && headers.get ? headers.get('Retry-After') : NaN);
    if (!Number.isFinite(after) || after <= 0) after = Number(payload && payload.retry_after);
    return new RateLimitedError(message, {
      status, payload, path, retryAfter: Number.isFinite(after) && after > 0 ? after : 1,
    });
  }
  return new Cls(message, { status, payload, path });
}
