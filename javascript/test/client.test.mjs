/**
 * Khách gọi API phải cư xử đúng ở những chỗ chỉ lộ ra khi mạng xấu — tức là đúng lúc không ai
 * ngồi xem nhật ký. Thay `fetch` bằng một hàm giả để dựng đúng những lúc đó mà không cần mạng.
 */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { Client } from '../src/client.js';
import * as errors from '../src/errors.js';

function fakeFetch(script) {
  const seen = [];
  const fn = async (url, init) => {
    seen.push({ url, init });
    const [status, payload, headers = {}] = script.shift() || [200, { ok: true }, {}];
    return {
      ok: status < 400,
      status,
      headers: { get: (k) => headers[k] ?? null },
      text: async () => JSON.stringify(payload),
    };
  };
  fn.seen = seen;
  return fn;
}

test('khoá đi bằng header Bearer, không bằng cookie', async () => {
  const f = fakeFetch([[200, { ok: true, token: 'abc123' }], [200, { ok: true }]]);
  const c = new Client('https://x.test', { fetch: f });
  await c.login('vuon_cua_toi', 'vuon.sau.rieng.2026');
  assert.equal(c.token, 'abc123');
  await c.me();
  assert.equal(f.seen[1].init.headers.Authorization, 'Bearer abc123');
  assert.equal(f.seen[1].init.credentials, undefined, 'không được kèm cookie khác origin');
});

test('mật khẩu đi trong thân JSON, không trong chuỗi truy vấn', async () => {
  const f = fakeFetch([[200, { ok: true, token: 't' }]]);
  await new Client('https://x.test', { fetch: f }).login('ai_do', 'mat.khau.dai.that');
  assert.ok(!f.seen[0].url.includes('?'));
  assert.equal(JSON.parse(f.seen[0].init.body).password, 'mat.khau.dai.that');
});

test('trường rỗng bị bỏ, không gửi chuỗi "null"', async () => {
  const f = fakeFetch([[200, { ok: true }]]);
  const c = new Client('https://x.test', { fetch: f });
  await c.identifyAuto([{ name: 'a.jpg', data: new Uint8Array([1, 2, 3]) }], { lat: 10.5 });
  const form = f.seen[0].init.body;
  assert.equal(form.get('lat'), '10.5');
  assert.equal(form.get('lon'), null);
  assert.ok(form.get('files'), 'ảnh phải đi kèm');
});

test('bị hạn tần suất thì chờ đúng nhịp máy chủ bảo', async () => {
  const f = fakeFetch([
    [429, { ok: false, error: 'Máy đang bận' }, { 'Retry-After': '0.05' }],
    [200, { ok: true }],
  ]);
  const t0 = Date.now();
  const out = await new Client('https://x.test', { fetch: f }).health();
  assert.equal(out.ok, true);
  assert.ok(Date.now() - t0 >= 50, 'không đọc header Retry-After');
});

test('cửa GHI hỏng thì KHÔNG tự gửi lại', async () => {
  const f = fakeFetch([[500, { ok: false, error: 'hỏng' }], [200, { ok: true }]]);
  const c = new Client('https://x.test', { fetch: f });
  await assert.rejects(
    () => c.enrollTree([{ name: 'a.jpg', data: new Uint8Array([1]) }], { name: 'cây 1' }),
    errors.ServerError,
  );
  assert.equal(f.seen.length, 1, 'đã tự gửi lại một cửa GHI');
});

test('cửa ĐỌC hỏng ở phía máy chủ thì gửi lại', async () => {
  const f = fakeFetch([[500, { ok: false, error: 'hỏng' }], [200, { ok: true }]]);
  const out = await new Client('https://x.test', { fetch: f }).health();
  assert.equal(out.ok, true);
  assert.equal(f.seen.length, 2);
});

test('mỗi mã trạng thái thành một kiểu lỗi riêng', async () => {
  const table = [[400, errors.InvalidRequestError], [401, errors.AuthError],
    [403, errors.PermissionError], [404, errors.NotFoundError],
    [413, errors.TooLargeError], [422, errors.InvalidRequestError],
    [500, errors.ServerError]];
  for (const [status, Kind] of table) {
    const f = fakeFetch([[status, { ok: false, error: 'câu cho người dùng' }]]);
    const c = new Client('https://x.test', { fetch: f, maxRetries: 0 });
    await assert.rejects(() => c.resolve('ORI-0000000-AAAAAAAA'), (e) => {
      assert.ok(e instanceof Kind, `${status} phải là ${Kind.name}, nhận ${e.name}`);
      assert.equal(e.message, 'câu cho người dùng');
      assert.equal(e.status, status);
      return true;
    });
  }
});

test('câu hiện cho người dùng không lấy từ khuôn kiểm tham số', async () => {
  const f = fakeFetch([[422, { detail: [{ loc: ['body', 'file'], msg: 'field required' }] }]]);
  const c = new Client('https://x.test', { fetch: f, maxRetries: 0 });
  await assert.rejects(() => c.lookupFruit({ name: 'a.jpg', data: new Uint8Array([1]) }), (e) => {
    assert.ok(!e.message.includes('loc'));
    assert.ok(e.payload.detail, 'vẫn giữ nguyên thân gốc cho người gỡ lỗi');
    return true;
  });
});

test('không kết nối được là NetworkError, không phải ServerError', async () => {
  const f = async () => { throw new TypeError('failed to fetch'); };
  const c = new Client('https://x.test', { fetch: f, maxRetries: 0 });
  await assert.rejects(() => c.health(), errors.NetworkError);
});

test('trường lạ trong phản hồi đi thẳng cho ứng dụng, không bị cắt', async () => {
  const f = fakeFetch([[200, { ok: true, decision: 'MATCH', truong_moi_cua_may_chu: 42 }]]);
  const out = await new Client('https://x.test', { fetch: f })
    .identifyTree([{ name: 'a.jpg', data: new Uint8Array([1]) }]);
  assert.equal(out.truong_moi_cua_may_chu, 42);
});
