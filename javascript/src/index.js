/**
 * The OriLife SDK — identifying individuals from photographs of them.
 *
 * Two halves, deliberately kept apart:
 *
 *   import { Client } from '@orilife/sdk';          // call the API
 *   import * as verify from '@orilife/sdk/verify';  // independent verification, no network
 *
 * The second half is the one that matters. `Client` asks the server and repeats the answer — using
 * it means you are trusting OriLife. `verify` recomputes hashes from the record itself, so it can
 * check what OriLife claims without OriLife being present.
 */
export { Client, CONTRACT_VERSION, DEFAULT_BASE_URL } from './client.js';
export {
  AuthError, InvalidRequestError, NetworkError, NotFoundError, OriLifeError,
  PermissionError, RateLimitedError, ServerError, TooLargeError,
} from './errors.js';
export * as verify from './verify.js';
export { blake2b, sha256, sha3_256 } from './hash.js';
