/**
 * Lỗi có KIỂU — để ứng dụng phân biệt ba thứ mà một chuỗi lỗi trộn làm một: lỗi do người dùng,
 * lỗi do ứng dụng, lỗi do phía kia. Ba thứ đó phải xử theo ba cách khác hẳn nhau (hiện câu hướng
 * dẫn / đăng nhập lại / chờ rồi thử lại), nên gộp chúng vào một Error chung là đẩy việc phân loại
 * sang cho người viết ứng dụng, mỗi người tự đoán một kiểu.
 *
 * Mọi lỗi mang `message` là câu tiếng Việt máy chủ đã viết sẵn cho người dùng đọc. Hiện thẳng câu
 * đó, đừng tự dịch mã lỗi thành câu của mình — máy chủ biết ngữ cảnh còn ứng dụng thì không.
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

/** Không nói chuyện được với máy chủ. Yêu cầu có thể CHƯA từng tới nơi — khác hẳn ServerError. */
export class NetworkError extends OriLifeError {}
/** 401 — chưa đăng nhập hoặc khoá hết hạn. Xin khoá mới rồi gọi lại. */
export class AuthError extends OriLifeError {}
/** 403 — đã đăng nhập nhưng không có quyền. Xin khoá mới KHÔNG giúp. */
export class PermissionError extends OriLifeError {}
/**
 * 404 — không có thứ đó. Đừng viết "cây này không tồn tại" lên màn hình: nhiều cửa cố ý trả 404
 * cho cả "không tồn tại" lẫn "của người khác", để người dò mã không đếm được vườn người ta.
 */
export class NotFoundError extends OriLifeError {}
/** 413 — vượt trần. Nén nhỏ lại rồi gửi lại, đừng thử lại nguyên trạng. */
export class TooLargeError extends OriLifeError {}
/** 400/422 — thiếu trường, sai kiểu, hoặc không đạt luật. */
export class InvalidRequestError extends OriLifeError {}
/** 5xx — yêu cầu đã tới nơi và phía kia hỏng. Thử lại được, giãn dần khoảng cách. */
export class ServerError extends OriLifeError {}

/** 429 — gọi quá dày. CHỜ ĐÚNG `retryAfter` giây; thử lại ngay chỉ kéo dài thời gian bị chặn. */
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
 * Câu cho người dùng, theo đúng thứ tự ưu tiên máy chủ dùng. `detail` là khuôn của tầng kiểm
 * tham số nên nó thường là cấu trúc, không phải câu — lấy nó hiện lên màn hình là cách nhanh
 * nhất để một chuỗi kỹ thuật rơi vào mắt nông dân.
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
  const message = messageOf(payload, `Máy chủ trả về mã ${status}.`);
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
