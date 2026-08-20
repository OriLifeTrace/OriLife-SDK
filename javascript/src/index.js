/**
 * Bộ công cụ OriLife — định danh cá thể bằng chính ảnh chụp nó.
 *
 * Hai nửa, cố ý tách rời:
 *
 *   import { Client } from '@orilife/sdk';          // gọi API
 *   import * as verify from '@orilife/sdk/verify';  // kiểm chứng độc lập, không mạng
 *
 * Nửa thứ hai là nửa quan trọng. `Client` chỉ hỏi máy chủ rồi chép lại câu trả lời — dùng nó thì
 * bạn đang tin OriLife. `verify` tính lại mã băm từ chính bản ghi, nên nó kiểm được lời khai của
 * OriLife mà không cần OriLife có mặt.
 */
export { Client, DEFAULT_BASE_URL } from './client.js';
export {
  AuthError, InvalidRequestError, NetworkError, NotFoundError, OriLifeError,
  PermissionError, RateLimitedError, ServerError, TooLargeError,
} from './errors.js';
export * as verify from './verify.js';
export { blake2b, sha256, sha3_256 } from './hash.js';
