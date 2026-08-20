/**
 * Kiểm chứng ĐỘC LẬP trong trình duyệt, Node, hay bất cứ đâu chạy được JavaScript.
 *
 * Cùng phép toán với `orilife.verify` bên Python, và cùng ra một con số — có bài kiểm đối chiếu
 * với bộ vector sinh từ chính mã đang chạy trên máy chủ.
 *
 * Vì sao cần bản JavaScript riêng: nếu cách duy nhất để kiểm một bản ghi là chạy Python thì người
 * mua cầm điện thoại không kiểm được, và "ai cũng kiểm được" trở thành "ai có máy tính và biết
 * cài Python thì kiểm được". Trang web tĩnh nhúng tệp này là đủ để một người lạ tự kiểm.
 *
 * Không mạng, không phụ thuộc, không trạng thái.
 */
import { blake2b, sha256, sha3_256 } from './hash.js';

export const RECORD_VERSION = 2;
export const HASH_ALGORITHM = 'sha3-256';
export const HASH_ALGORITHM_LEGACY = 'blake2b-256';

const GEOHASH_ALPHABET = '0123456789bcdefghjkmnpqrstuvwxyz';
// Crockford base32: bỏ I, L, O, U để người đọc mã bằng mắt không nhầm với 1 và 0.
const CROCKFORD_ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';

// Bảng thuật toán ĐƯỢC PHÉP. Thuật toán ngoài bảng thì trả về sai, KHÔNG rơi về mặc định — rơi
// về mặc định là mở đúng cánh cửa mà việc bản ghi tự khai thuật toán dựng ra để đóng.
const HASHERS = {
  'sha3-256': (bytes) => sha3_256(bytes),
  'blake2b-256': (bytes) => blake2b(bytes, 32),
};

/** Geohash chuẩn (Niemeyer). Bảy ký tự ≈ ô 150 m: đủ nói "vùng nào", không đủ chỉ một gốc cây. */
export function geohash(lat, lon, precision = 7) {
  const latRange = [-90, 90];
  const lonRange = [-180, 180];
  let out = '';
  let bit = 0;
  let acc = 0;
  let even = true;
  while (out.length < precision) {
    if (even) {
      const mid = (lonRange[0] + lonRange[1]) / 2;
      if (lon > mid) { acc |= 1 << (4 - bit); lonRange[0] = mid; } else { lonRange[1] = mid; }
    } else {
      const mid = (latRange[0] + latRange[1]) / 2;
      if (lat > mid) { acc |= 1 << (4 - bit); latRange[0] = mid; } else { latRange[1] = mid; }
    }
    even = !even;
    if (bit < 4) { bit += 1; } else { out += GEOHASH_ALPHABET[acc]; bit = 0; acc = 0; }
  }
  return out;
}

function crockford(hexDigest, nChars) {
  let number = BigInt(`0x${hexDigest}`);
  const totalBits = BigInt(hexDigest.length * 4);
  let out = '';
  for (let i = 0; i < nChars; i += 1) {
    const shift = totalBits - 5n * BigInt(i + 1);
    const index = shift < 0n ? Number((number << -shift) & 0x1fn) : Number((number >> shift) & 0x1fn);
    out += CROCKFORD_ALPHABET[index];
  }
  return out;
}

/**
 * Mã công khai ổn định của một cá thể: `ORI-<geohash7>-<8 ký tự>`.
 *
 * Dùng để ĐỐI CHIẾU: cầm mã in trên phiếu, gọi hàm này với định danh máy chủ trả về, hai bên phải
 * ra cùng một chuỗi. Lệch nghĩa là một trong hai đầu đã đổi.
 */
export function entityCode(entityId, gps = null) {
  const digest = blake2b(entityId, 8);
  const suffix = crockford(digest, 8);
  const cell = (gps && gps.length === 2 && gps[0] != null && gps[1] != null)
    ? geohash(Number(gps[0]), Number(gps[1]), 7)
    : '0000000';
  return `ORI-${cell}-${suffix}`;
}

/**
 * So khoá theo ĐIỂM MÃ Unicode, không theo đơn vị UTF-16.
 *
 * `Array.prototype.sort()` mặc định so theo đơn vị UTF-16, khác với Python ở những ký tự ngoài
 * mặt phẳng cơ bản. Khoá của bản ghi hôm nay đều là ASCII nên hai cách cho cùng kết quả, nhưng
 * một khoá mới có ký tự lạ sẽ làm mã băm lệch mà chẳng ai hiểu vì sao — nên khoá cách so ở đây.
 */
function byCodePoint(a, b) {
  const ca = [...a];
  const cb = [...b];
  for (let i = 0; i < Math.min(ca.length, cb.length); i += 1) {
    const d = ca[i].codePointAt(0) - cb[i].codePointAt(0);
    if (d !== 0) return d;
  }
  return ca.length - cb.length;
}

/**
 * Tuần tự hoá TẤT ĐỊNH: khoá sắp xếp, không khoảng trắng thừa, giữ nguyên chữ ngoài ASCII.
 *
 * Ba lựa chọn đó đều bắt buộc. Thứ tự khoá khác nhau, một dấu cách sau dấu hai chấm, hay một chữ
 * tiếng Việt bị chuyển thành `\\uXXXX` — mỗi thứ đủ để mã băm lệch trong khi nội dung y hệt, và
 * người kiểm sẽ kết luận là bị sửa chứ không kết luận là do khác cách tuần tự hoá.
 */
export function canonicalJson(value) {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  const keys = Object.keys(value).filter((k) => value[k] !== undefined).sort(byCodePoint);
  return `{${keys.map((k) => `${JSON.stringify(k)}:${canonicalJson(value[k])}`).join(',')}}`;
}

const utf8 = (s) => new TextEncoder().encode(s);

export function hashBytes(bytes, algorithm = HASH_ALGORITHM) {
  const fn = HASHERS[String(algorithm || '').trim().toLowerCase()];
  if (!fn) throw new RangeError(`thuật toán băm không hỗ trợ: ${algorithm}`);
  return fn(bytes);
}

/**
 * Thuật toán băm CỦA CHÍNH BẢN GHI NÀY — đọc từ bản ghi, không đoán theo thời điểm. Bản ghi cũ
 * không khai thì `v<=1` nghĩa là blake2b; thiếu cả `v` cũng coi là v=1, vì bản ghi càng cũ càng
 * thiếu trường nên mặc định phải nghiêng về phía cũ thì lịch sử mới kiểm được.
 */
export function recordAlgorithm(record) {
  const declared = String((record && record.hash_alg) || '').trim().toLowerCase();
  if (declared) return declared;
  const version = Number((record && record.v) || 1);
  return Number.isFinite(version) && version <= 1 ? HASH_ALGORITHM_LEGACY : HASH_ALGORITHM;
}

/** Băm bản ghi bằng thuật toán HIỆN HÀNH. Muốn KIỂM bản ghi đã có thì dùng `verifyRecord`. */
export function recordHash(record) {
  return hashBytes(utf8(canonicalJson(record)), HASH_ALGORITHM);
}

/**
 * Bản ghi này có đúng là thứ đã băm ra `expectedHash` không?
 *
 * Đưa vào JSON bản ghi lấy từ kho lưu trữ và con số đọc trên trình duyệt khối, nhận về true/false.
 * Không có đường hạ cấp: khoá `hash_alg` nằm TRONG phần được băm, nên sửa nó để ép dùng thuật
 * toán yếu hơn là đã đổi luôn nội dung, và mã băm không còn khớp.
 */
export function verifyRecord(record, expectedHash) {
  if (!record || typeof record !== 'object' || typeof expectedHash !== 'string' || !expectedHash) {
    return false;
  }
  try {
    return hashBytes(utf8(canonicalJson(record)), recordAlgorithm(record)) === expectedHash.trim().toLowerCase();
  } catch {
    return false;
  }
}

/** SHA-256 của một khối byte — để so với trường `sha256` trong bản ghi. */
export async function sha256Of(bytes) { return sha256(bytes); }

/**
 * Trường bắt buộc nào vắng mặt. Có mặt để phân biệt hai ca rất khác nhau: bản ghi ĐỦ mà lệch mã
 * băm (nghi bị sửa) với bản ghi THIẾU trường (nhiều khả năng tải hụt hoặc lấy nhầm mảnh).
 */
export function missingFields(record, required = ['v', 'code', 'gps', 'enrolled_at', 'images']) {
  return required.filter((k) => !(record && k in record));
}

/** Một dòng tóm tắt cho công cụ và cho tác tử: bản ghi này nói gì, có khớp không. */
export function summarize(record, expectedHash = null) {
  const images = (record && record.images) || [];
  return {
    code: record && record.code,
    version: record && record.v,
    algorithm: recordAlgorithm(record),
    enrolledAt: record && record.enrolled_at,
    nImages: Array.isArray(images) ? images.length : 0,
    has3d: Boolean(record && record.model3d),
    missingFields: missingFields(record),
    hashMatches: expectedHash ? verifyRecord(record, expectedHash) : null,
  };
}
