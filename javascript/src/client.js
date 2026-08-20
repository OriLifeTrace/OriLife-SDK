/**
 * Khách gọi API OriLife cho trình duyệt, Node và tác tử. Không phụ thuộc thư viện nào.
 *
 * Dùng `fetch` và `FormData` có sẵn ở mọi nơi bộ này nhắm tới (trình duyệt, Node 18+, Deno,
 * Bun, Cloudflare Workers). Không phụ thuộc nghĩa là không có gì phải cập nhật vì lý do bảo mật
 * của người khác, và một tệp đọc được bằng mắt thì kiểm được bằng mắt.
 *
 * Từ 2026-08 máy chủ mở CORS cho mọi origin kèm `allow_credentials=false`, nên trang web ở bất kỳ
 * origin nào cũng gọi được. Đổi lại, cookie phiên KHÔNG đi kèm lượt gọi khác origin — khoá phải
 * đi bằng header `Authorization: Bearer`. Đó là lý do bộ này không đụng tới cookie ở đâu cả.
 *
 * Ba việc bộ này làm hộ mà tự viết sẽ quên:
 *   • Chờ đúng nhịp khi bị hạn tần suất (đọc `Retry-After`, không tự đặt nhịp).
 *   • Chỉ thử lại việc thử lại được — cửa GHI hỏng giữa chừng có thể đã tạo bản ghi.
 *   • Không diễn giải phần nội tạng: trường lạ trong phản hồi đi thẳng cho ứng dụng.
 */
import { NetworkError, RateLimitedError, ServerError, fromResponse } from './errors.js';

export const DEFAULT_BASE_URL = 'https://api.orilife.io';

const IDEMPOTENT = new Set(['GET', 'HEAD']);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** Một tệp: Blob/File, hoặc { name, data } với data là Blob/ArrayBuffer/Uint8Array. */
function toBlob(item) {
  if (typeof Blob !== 'undefined' && item instanceof Blob) return { blob: item, name: item.name || 'upload.jpg' };
  if (item && item.data !== undefined) {
    const data = item.data instanceof Uint8Array || item.data instanceof ArrayBuffer
      ? new Blob([item.data], { type: item.type || 'image/jpeg' })
      : item.data;
    return { blob: data, name: item.name || 'upload.jpg' };
  }
  throw new TypeError('tệp phải là Blob/File hoặc { name, data }');
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
  }

  headers(extra) {
    const h = { Accept: 'application/json', ...(extra || {}) };
    if (this.token) h.Authorization = `Bearer ${this.token}`;
    return h;
  }

  /** Gọi một cửa. Ném lỗi có kiểu khi phía kia từ chối; trả về dữ liệu đã giải mã khi xong. */
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
        // Trường rỗng bị BỎ, không gửi chuỗi "null" — gửi nó là dựng dữ liệu rác ở đầu bên kia.
        if (v !== undefined && v !== null) form.append(k, String(v));
      }
      for (const [k, item] of files) {
        const { blob, name } = toBlob(item);
        form.append(k, blob, name);
      }
      body = form;   // KHÔNG tự đặt Content-Type: ranh giới multipart do fetch sinh ra.
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
        // Ca hạn tần suất là ca DUY NHẤT ngủ theo số của phía kia thay vì công thức của mình —
        // phía kia biết hàng chờ của nó, mình thì không.
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
        e && e.name === 'AbortError' ? 'Máy chủ không trả lời kịp.'
          : `Không kết nối được máy chủ: ${e && e.message}`, { path });
    } finally {
      if (timer) clearTimeout(timer);
    }

    const text = await resp.text();
    let payload;
    try { payload = text ? JSON.parse(text) : {}; } catch { payload = { error: text.slice(0, 400) }; }
    if (!resp.ok) throw fromResponse(resp.status, payload, { path, headers: resp.headers });
    return payload;
  }

  // ── xác thực ─────────────────────────────────────────────────────────────────────────────

  /**
   * Mở tài khoản. Tên đăng nhập 3–32 ký tự, chỉ chữ thường, chữ số, dấu chấm và gạch dưới —
   * KHÔNG có gạch nối. Mật khẩu tối thiểu 10 ký tự, ít nhất hai nhóm ký tự, không nằm trong danh
   * sách mật khẩu phổ biến. Sai luật thì máy chủ trả 400 kèm câu nói rõ sai chỗ nào.
   */
  async signup(username, password) { return this._keep(await this.request('POST', '/api/signup', { json: { username, password } })); }
  async login(username, password) { return this._keep(await this.request('POST', '/api/login', { json: { username, password } })); }
  _keep(data) { if (data && data.token) this.token = data.token; return data; }
  me() { return this.request('GET', '/api/me'); }
  async logout() { const o = await this.request('POST', '/api/logout'); this.token = null; return o; }

  // ── cửa công khai: gọi được khi CHƯA đăng nhập ────────────────────────────────────────────

  /** Máy chủ còn sống và hôm nay làm được gì. Đọc `features` rồi mới quyết định hiện màn hình nào. */
  health() { return this.request('GET', '/api/health'); }
  /** Bản khai dịch vụ cho máy — cửa nào không cần khoá, trần bao nhiêu, loại nào có tuyến. */
  describe() { return this.request('GET', '/.well-known/orilife.json'); }
  endpoints() { return this.request('GET', '/api'); }
  speciesCatalog() { return this.request('GET', '/api/species/catalog'); }

  /**
   * Tra một mã `ORI-…`. Ba trạng thái: `public`, `restricted`, `unknown`.
   * `unknown` KHÔNG kèm lý do — nếu "mã sai" trả lời khác "mã riêng tư" thì người dò mã sẽ đếm
   * được vườn người khác. Đừng suy ra sự tồn tại từ chỗ khác biệt.
   */
  resolve(code) { return this.request('GET', `/api/resolve/${encodeURIComponent(code)}`); }

  /**
   * Xuất xứ của một cây theo MÃ in trên phiếu — cho người mua, không cần tài khoản.
   * Cây riêng tư và cây không tồn tại trả CÙNG mã 404. Đừng viết "mã sai" lên màn hình.
   */
  treeByCode(code) { return this.request('GET', `/api/tree_by_code/${encodeURIComponent(code)}`); }

  /** Ảnh một quả → ứng viên trong tập công khai. Không cần tài khoản, không giữ dữ liệu ai. */
  lookupFruit(image) { return this.request('POST', '/api/fruit/lookup', { files: [['file', image]] }); }

  // ── định danh ─────────────────────────────────────────────────────────────────────────────

  /**
   * MỘT cửa cho mọi loại: máy tự nhận cây, quả hay con vật rồi định danh luôn — không phải hỏi
   * người dùng đang chụp gì. Trả `kind`, `lane` (cửa đã chạy) và `result` là nguyên văn phản hồi
   * của cửa đó. Con vật còn đòi `species` + `farmId`; thiếu thì `result` là null và `need` liệt
   * kê hai trường ấy, vì máy chủ không đoán hộ loài.
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

  /** Quay một vòng quanh cây thay vì chụp rời. Clip KHÔNG được lưu, chỉ dùng rồi bỏ. */
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

  /** Chỉ hỏi ĐANG NHÌN CÁI GÌ, chưa định danh. Dùng khi muốn tự điều hướng luồng. */
  identifyKind(image) { return this.request('POST', '/api/kind', { files: [['file', image]] }); }

  // ── đăng ký ───────────────────────────────────────────────────────────────────────────────

  /**
   * Đăng ký một cây mới. Đây là cửa GHI: bộ này KHÔNG tự gửi lại khi hỏng, vì yêu cầu có thể đã
   * tới nơi. Bắt NetworkError rồi hỏi lại `listTrees()` trước khi gửi lại.
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

  // ── bằng chứng ────────────────────────────────────────────────────────────────────────────

  /** Mã, địa chỉ ảnh, địa chỉ bản ghi, mã băm, trạng thái neo — nguyên liệu để tự kiểm. */
  provenance(treeId) { return this.request('GET', `/api/provenance/${encodeURIComponent(treeId)}`); }
  timeline(entityType, entityId) { return this.request('GET', `/api/${entityType}/${encodeURIComponent(entityId)}/timeline`); }
  /** Đường dẫn Merkle chứng minh một sự kiện thuộc gốc đã neo lên chuỗi. */
  proof(entityType, entityId, eventId) {
    return this.request('GET', `/api/${entityType}/${encodeURIComponent(entityId)}/proof/${encodeURIComponent(eventId)}`);
  }
}
