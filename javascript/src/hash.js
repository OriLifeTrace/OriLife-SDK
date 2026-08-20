/**
 * BLAKE2b và SHA3-256 viết thuần JavaScript, không phụ thuộc gì.
 *
 * Vì sao phải tự viết. Trình duyệt có WebCrypto nhưng WebCrypto chỉ có SHA-1/SHA-2 — không có
 * SHA-3, không có BLAKE2b. Node có `crypto` nhưng OpenSSL chỉ cho BLAKE2b-512, trong khi bản ghi
 * OriLife dùng BLAKE2b với độ dài đầu ra 32 byte. Hai thứ đó KHÔNG phải một: BLAKE2b nhét độ dài
 * đầu ra vào khối tham số ngay từ giá trị khởi tạo, nên cắt ngắn BLAKE2b-512 xuống 32 byte cho ra
 * một con số hoàn toàn khác. Ai "tối ưu" chỗ này bằng cách cắt ngắn sẽ làm mọi bản ghi cũ đọc
 * thành bị sửa.
 *
 * Dùng BigInt cho các thanh ghi 64 bit thay vì ghép hai số 32 bit. Chậm hơn vài lần, nhưng thứ
 * cần băm ở đây là một bản ghi vài trăm byte chứ không phải một luồng video — và mã ngắn thì đọc
 * được bằng mắt, mà cả tệp này tồn tại để người ngoài đọc bằng mắt.
 */

const M64 = (1n << 64n) - 1n;
const rotl = (x, n) => ((x << n) | (x >> (64n - n))) & M64;
const rotr = (x, n) => ((x >> n) | (x << (64n - n))) & M64;

function toBytes(input) {
  if (typeof input === 'string') return new TextEncoder().encode(input);
  if (input instanceof Uint8Array) return input;
  if (input instanceof ArrayBuffer) return new Uint8Array(input);
  throw new TypeError('cần chuỗi, Uint8Array hoặc ArrayBuffer');
}

const hex = (bytes) => Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');

// ── SHA3-256 ────────────────────────────────────────────────────────────────────────────────

const KECCAK_RC = [
  0x0000000000000001n, 0x0000000000008082n, 0x800000000000808an, 0x8000000080008000n,
  0x000000000000808bn, 0x0000000080000001n, 0x8000000080008081n, 0x8000000000008009n,
  0x000000000000008an, 0x0000000000000088n, 0x0000000080008009n, 0x000000008000000an,
  0x000000008000808bn, 0x800000000000008bn, 0x8000000000008089n, 0x8000000000008003n,
  0x8000000000008002n, 0x8000000000000080n, 0x000000000000800an, 0x800000008000000an,
  0x8000000080008081n, 0x8000000000008080n, 0x0000000080000001n, 0x8000000080008008n,
];
const KECCAK_ROT = [
  0n, 1n, 62n, 28n, 27n, 36n, 44n, 6n, 55n, 20n, 3n, 10n, 43n,
  25n, 39n, 41n, 45n, 15n, 21n, 8n, 18n, 2n, 61n, 56n, 14n,
];
/**
 * Hoán vị π, TÍNH RA chứ không chép tay: lane (x, y) chuyển tới (y, 2x+3y mod 5), với chỉ số
 * phẳng i = x + 5y. Bảng này chép tay sai một ô thì SHA3 vẫn chạy, vẫn ra 32 byte trông ngẫu
 * nhiên, và chỉ lộ khi đối chiếu với một giá trị chuẩn — nên tính ra là rẻ hơn.
 */
const KECCAK_PI = (() => {
  const map = new Array(25);
  for (let y = 0; y < 5; y += 1) {
    for (let x = 0; x < 5; x += 1) map[x + 5 * y] = y + 5 * ((2 * x + 3 * y) % 5);
  }
  return map;
})();

function keccakF(state) {
  for (let round = 0; round < 24; round += 1) {
    // θ
    const c = new Array(5);
    for (let x = 0; x < 5; x += 1) {
      c[x] = state[x] ^ state[x + 5] ^ state[x + 10] ^ state[x + 15] ^ state[x + 20];
    }
    for (let x = 0; x < 5; x += 1) {
      const d = c[(x + 4) % 5] ^ rotl(c[(x + 1) % 5], 1n);
      for (let y = 0; y < 25; y += 5) state[x + y] ^= d;
    }
    // ρ và π
    const b = new Array(25);
    for (let i = 0; i < 25; i += 1) b[KECCAK_PI[i]] = rotl(state[i], KECCAK_ROT[i]);
    // χ
    for (let y = 0; y < 25; y += 5) {
      for (let x = 0; x < 5; x += 1) {
        state[y + x] = (b[y + x] ^ ((~b[y + ((x + 1) % 5)] & M64) & b[y + ((x + 2) % 5)])) & M64;
      }
    }
    // ι
    state[0] ^= KECCAK_RC[round];
  }
}

/** SHA3-256 theo FIPS 202: nhịp 136 byte, đệm 0x06 … 0x80. */
export function sha3_256(input) {
  const message = toBytes(input);
  const RATE = 136;
  const padded = new Uint8Array(Math.ceil((message.length + 1) / RATE) * RATE);
  padded.set(message);
  padded[message.length] = 0x06;
  padded[padded.length - 1] |= 0x80;

  const state = new Array(25).fill(0n);
  for (let offset = 0; offset < padded.length; offset += RATE) {
    for (let lane = 0; lane < RATE / 8; lane += 1) {
      let word = 0n;
      for (let byte = 7; byte >= 0; byte -= 1) {
        word = (word << 8n) | BigInt(padded[offset + lane * 8 + byte]);
      }
      state[lane] ^= word;
    }
    keccakF(state);
  }

  const out = new Uint8Array(32);
  for (let i = 0; i < 32; i += 1) {
    out[i] = Number((state[Math.floor(i / 8)] >> BigInt((i % 8) * 8)) & 0xffn);
  }
  return hex(out);
}

// ── BLAKE2b ─────────────────────────────────────────────────────────────────────────────────

const BLAKE2B_IV = [
  0x6a09e667f3bcc908n, 0xbb67ae8584caa73bn, 0x3c6ef372fe94f82bn, 0xa54ff53a5f1d36f1n,
  0x510e527fade682d1n, 0x9b05688c2b3e6c1fn, 0x1f83d9abfb41bd6bn, 0x5be0cd19137e2179n,
];
const SIGMA = [
  [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
  [14, 10, 4, 8, 9, 15, 13, 6, 1, 12, 0, 2, 11, 7, 5, 3],
  [11, 8, 12, 0, 5, 2, 15, 13, 10, 14, 3, 6, 7, 1, 9, 4],
  [7, 9, 3, 1, 13, 12, 11, 14, 2, 6, 5, 10, 4, 0, 15, 8],
  [9, 0, 5, 7, 2, 4, 10, 15, 14, 1, 11, 12, 6, 8, 3, 13],
  [2, 12, 6, 10, 0, 11, 8, 3, 4, 13, 7, 5, 15, 14, 1, 9],
  [12, 5, 1, 15, 14, 13, 4, 10, 0, 7, 6, 3, 9, 2, 8, 11],
  [13, 11, 7, 14, 12, 1, 3, 9, 5, 0, 15, 4, 8, 6, 2, 10],
  [6, 15, 14, 9, 11, 3, 0, 8, 12, 2, 13, 7, 1, 4, 10, 5],
  [10, 2, 8, 4, 7, 6, 1, 5, 15, 11, 9, 14, 3, 12, 13, 0],
  [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
  [14, 10, 4, 8, 9, 15, 13, 6, 1, 12, 0, 2, 11, 7, 5, 3],
];

function compress(h, block, counter, last) {
  const v = [...h, ...BLAKE2B_IV];
  v[12] ^= counter & M64;
  v[13] ^= (counter >> 64n) & M64;
  if (last) v[14] ^= M64;

  const m = new Array(16);
  for (let i = 0; i < 16; i += 1) {
    let word = 0n;
    for (let byte = 7; byte >= 0; byte -= 1) word = (word << 8n) | BigInt(block[i * 8 + byte]);
    m[i] = word;
  }

  const mix = (a, b, c, d, x, y) => {
    v[a] = (v[a] + v[b] + x) & M64; v[d] = rotr(v[d] ^ v[a], 32n);
    v[c] = (v[c] + v[d]) & M64;     v[b] = rotr(v[b] ^ v[c], 24n);
    v[a] = (v[a] + v[b] + y) & M64; v[d] = rotr(v[d] ^ v[a], 16n);
    v[c] = (v[c] + v[d]) & M64;     v[b] = rotr(v[b] ^ v[c], 63n);
  };

  for (let round = 0; round < 12; round += 1) {
    const s = SIGMA[round];
    mix(0, 4, 8, 12, m[s[0]], m[s[1]]);
    mix(1, 5, 9, 13, m[s[2]], m[s[3]]);
    mix(2, 6, 10, 14, m[s[4]], m[s[5]]);
    mix(3, 7, 11, 15, m[s[6]], m[s[7]]);
    mix(0, 5, 10, 15, m[s[8]], m[s[9]]);
    mix(1, 6, 11, 12, m[s[10]], m[s[11]]);
    mix(2, 7, 8, 13, m[s[12]], m[s[13]]);
    mix(3, 4, 9, 14, m[s[14]], m[s[15]]);
  }
  for (let i = 0; i < 8; i += 1) h[i] = (h[i] ^ v[i] ^ v[i + 8]) & M64;
}

/**
 * BLAKE2b với độ dài đầu ra tuỳ chọn (mặc định 32 byte — bằng `hashlib.blake2b(digest_size=32)`).
 *
 * `outLen` đi vào khối tham số của giá trị khởi tạo, nên đổi nó là đổi TOÀN BỘ phép băm chứ không
 * phải cắt ngắn kết quả. Đây chính là chỗ mà một bản cài đặt dựa vào BLAKE2b-512 rồi cắt sẽ sai.
 */
export function blake2b(input, outLen = 32) {
  if (!Number.isInteger(outLen) || outLen < 1 || outLen > 64) {
    throw new RangeError('outLen phải trong khoảng 1..64');
  }
  const message = toBytes(input);
  const h = [...BLAKE2B_IV];
  h[0] ^= 0x01010000n ^ BigInt(outLen);

  const blocks = Math.max(1, Math.ceil(message.length / 128));
  const padded = new Uint8Array(blocks * 128);
  padded.set(message);

  for (let i = 0; i < blocks - 1; i += 1) {
    compress(h, padded.subarray(i * 128, i * 128 + 128), BigInt((i + 1) * 128), false);
  }
  compress(h, padded.subarray((blocks - 1) * 128), BigInt(message.length), true);

  const out = new Uint8Array(outLen);
  for (let i = 0; i < outLen; i += 1) {
    out[i] = Number((h[Math.floor(i / 8)] >> BigInt((i % 8) * 8)) & 0xffn);
  }
  return hex(out);
}

/** SHA-256 — có sẵn ở mọi nơi qua WebCrypto, nên chỉ bọc lại cho đồng nhất giao diện. */
export async function sha256(input) {
  const digest = await crypto.subtle.digest('SHA-256', toBytes(input));
  return hex(new Uint8Array(digest));
}

export const _internal = { toBytes, hex };
