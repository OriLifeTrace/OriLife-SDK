/**
 * Cách dựng thân yêu cầu — dùng chung cho mọi cửa, và phải KHỚP TỪNG BYTE với bản Python.
 *
 * Tệp này là bản JavaScript của `python/orilife/_wire.py`. Hai tệp cố ý viết cùng một phép biến
 * đổi, và `contract/conformance.json` là thứ giữ chúng bằng nhau: mỗi ca trong đó khai đúng cái đi
 * lên dây, rồi cả hai ngôn ngữ chạy lại đúng danh sách ca ấy.
 *
 * Cái đã sai trước khi có tệp này (đo 2026-09-08, trên bản `origin/main`) — lý do đầy đủ nằm ở
 * đầu tệp `_wire.py` bên Python, không chép lại ở đây.
 */

/** Gom "một ảnh hoặc nhiều ảnh" về một mảng. Một ảnh lẻ không phải mảng, và chuỗi cũng không. */
export function asFileList(images) {
  if (images === null || images === undefined) return [];
  return Array.isArray(images) ? images.slice() : [images];
}

/**
 * Đúng MỘT ảnh cho cửa chỉ nhận một ảnh — thừa thì ném, đừng lặng lẽ bỏ bớt.
 *
 * Gửi nhiều phần cùng tên `file` KHÔNG tải lên nhiều góc: máy chủ đọc phần đầu, phần còn lại biến
 * mất không một lời. Mất một tấm ảnh trong im lặng tệ hơn một lỗi.
 */
export function oneFile(images, message) {
  const items = asFileList(images);
  if (items.length !== 1) throw new TypeError(message);
  return items[0];
}

/**
 * Khung bao thành bốn trường biểu mẫu máy chủ chờ. Nhận `[x, y, w, h]` hoặc `{ x, y, w, h }`.
 *
 * Thứ khác thì ném: một khung bị bỏ qua trong im lặng nghĩa là quả được ghi từ CẢ khung hình thay
 * vì từ quả — một bản ghi sai, tệ hơn một lỗi nhìn thấy được.
 */
export function bboxFields(bbox) {
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
  return {
    bbox_x: box[0], bbox_y: box[1], bbox_w: box[2], bbox_h: box[3],
  };
}

/** Tâm vườn: đủ CẢ hai nửa mới gửi. Nửa toạ-độ không phải một chỗ nào cả. */
export function centerJson(lat, lon) {
  if (lat === null || lat === undefined || lon === null || lon === undefined) return undefined;
  return JSON.stringify([lat, lon]);
}

/**
 * Trường tự do: mảng và ánh xạ mã hoá JSON, còn lại giữ nguyên; rỗng thì loại.
 *
 * `boundary_json: [[lat, lon], …]` phải tới máy chủ dưới dạng CHUỖI JSON. Để nguyên rồi phó mặc
 * `URLSearchParams` thì nó gọi `String([[10.7,106.6]])` và gửi lên `10.7,106.6`.
 */
export function encodeContainers(fields) {
  const out = {};
  for (const [k, v] of Object.entries(fields || {})) {
    if (v === null || v === undefined) continue;
    out[k] = (typeof v === 'object') ? JSON.stringify(v) : v;
  }
  return out;
}

/**
 * Tham số bắt buộc mà thiếu thì ném NGAY, trước khi tải ảnh lên.
 *
 * Bên Python việc này do chính ngôn ngữ làm (tham số chỉ-từ-khoá không mặc định). Bên JavaScript
 * một khoá thiếu chỉ là `undefined`, rồi trường bị loại lúc dựng biểu mẫu, rồi vài megabyte ảnh
 * đi lên một cửa chắc chắn từ chối — trên đường truyền yếu đó là cả phút chờ để nhận một lỗi lẽ
 * ra biết trước.
 */
export function requireArgs(method, args) {
  const missing = Object.keys(args).filter((k) => args[k] === undefined || args[k] === null);
  if (missing.length) {
    throw new TypeError(`${method}() is missing required argument(s): ${missing.join(', ')}`);
  }
}

/** Một tệp gửi lên: `Blob`/`File`, hoặc `{ name, data }` với `data` là Blob/ArrayBuffer/Uint8Array. */
export function toBlob(item) {
  if (typeof Blob !== 'undefined' && item instanceof Blob) return { blob: item, name: item.name || 'upload.jpg' };
  if (item && item.data !== undefined) {
    const data = item.data instanceof Uint8Array || item.data instanceof ArrayBuffer
      ? new Blob([item.data], { type: item.type || 'image/jpeg' })
      : item.data;
    return { blob: data, name: item.name || 'upload.jpg' };
  }
  throw new TypeError('a file must be a Blob/File or { name, data }');
}
