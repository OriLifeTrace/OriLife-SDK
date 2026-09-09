/**
 * Chạy bộ ca DÙNG CHUNG `contract/conformance.json` trên bản cài JavaScript.
 *
 * Bộ kiểm riêng của mỗi ngôn ngữ chỉ chứng minh bên đó tự nhất quán với chính nó. Hai bên tự nhất
 * quán mà lệch nhau thì vẫn xanh cả hai — đó đúng là chỗ ba lỗi thật đã đi qua (xem đầu tệp
 * `python/orilife/_wire.py`). Tệp này và bản song sinh `python/tests/test_conformance.py` chạy
 * CÙNG một danh sách ca, nên một bên lệch là một bên đỏ.
 *
 * Ranh giới đo: chốt ở chỗ hàm gọi ra `request()` — phần ÁNH XẠ (đường, tên trường, cách mã hoá).
 * Tầng vận chuyển bên dưới do `client.test.mjs` giữ. Xanh ở đây KHÔNG có nghĩa là đã kiểm hết.
 */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { Client } from '../src/client.js';
import { load } from './_contract.mjs';

const CONTRACT = load('methods.json');
const CASES = load('conformance.json').cases;
const SPEC = Object.fromEntries(CONTRACT.methods.map((m) => [m.name, m]));
const GENERATED = CONTRACT.methods.filter((m) => m.generated !== false).map((m) => m.name);

// Cùng một khối byte cho mọi tệp giả — nội dung không phải thứ đang đo, tên trường mới là.
const BLOB = new Uint8Array([1, 2, 3]);

const camel = (snake) => snake.split('_')
  .map((w, i) => (i === 0 ? w : w.charAt(0).toUpperCase() + w.slice(1)))
  .join('');

/** Đúng cái đi lên dây: bỏ giá trị rỗng, ép chuỗi phần còn lại. */
function clean(mapping) {
  const out = {};
  for (const [k, v] of Object.entries(mapping || {})) {
    if (v !== undefined && v !== null) out[k] = String(v);
  }
  return out;
}

/**
 * Chỗ giữ tệp trong ca kiểm thành một tệp thật của ngôn ngữ này.
 *
 * `$single_file` là MỘT tệp lẻ không bọc trong mảng. Bên Python nó dựng thành chuỗi đường dẫn vì
 * đó là chỗ ngôn ngữ đó hỏng; bên này chuỗi không phải kiểu tệp hợp lệ, nên lối tự nhiên là một
 * đối tượng tệp — và nó vẫn chạm đúng lỗi của bên này: gọi `.map` trên thứ không phải mảng.
 */
function materialise(value) {
  if (Array.isArray(value)) return value.map(materialise);
  if (value && typeof value === 'object' && '$file' in value) {
    return { name: value.$file, data: BLOB };
  }
  if (value && typeof value === 'object' && '$single_file' in value) {
    return { name: value.$single_file, data: BLOB };
  }
  return value;
}

/** Client thật, chỉ thay tầng vận chuyển bằng một cuốn sổ. */
class Recorder extends Client {
  constructor() {
    super('https://x.test', { token: 'k', maxRetries: 0 });
    this.seen = null;
  }

  async request(verb, path, {
    params, fields, files, json, timeout,
  } = {}) {
    this.seen = {
      verb,
      path,
      query: clean(params),
      fields: clean(fields),
      files: (files || []).map(([key, item]) => [key, item.name]),
      json,
      timeout,
    };
    return { ok: true, token: 'tok' };
  }
}

/** Dựng lệnh gọi từ đặc tả tham số trong hợp đồng, không đoán theo tên ca. */
function invoke(client, testCase) {
  const spec = SPEC[testCase.method];
  const args = Object.fromEntries(
    Object.entries(testCase.args).map(([k, v]) => [k, materialise(v)]),
  );
  const positional = (spec.args || []).filter((a) => a.positional);
  const optional = (spec.args || []).filter((a) => !a.positional);
  const plain = optional.filter((a) => a.kind !== 'varfields');
  const varfields = optional.filter((a) => a.kind === 'varfields');

  const callArgs = [];
  for (const arg of positional) {
    if (arg.name in args) callArgs.push(args[arg.name]);
    else if (arg.kind === 'json_payload') callArgs.push(null);
    else throw new Error(`ca ${testCase.name}: thiếu tham số bắt buộc ${arg.name}`);
  }
  if (plain.length) {
    const opts = {};
    for (const arg of plain) if (arg.name in args) opts[camel(arg.name)] = args[arg.name];
    callArgs.push(opts);
  }
  for (const arg of varfields) callArgs.push(args[arg.name] || {});

  return client[camel(testCase.method)](...callArgs);
}

for (const testCase of CASES) {
  test(testCase.name, async () => {
    const client = new Recorder();

    if (testCase.throws) {
      await assert.rejects(
        async () => invoke(client, testCase),
        (e) => e instanceof TypeError || e instanceof RangeError,
      );
      // Ném là chưa đủ: nó phải ném TRƯỚC khi có byte nào rời máy. Ném sau khi đã tải ảnh lên
      // trên đường truyền yếu là cả phút chờ để nhận một lỗi lẽ ra biết trước.
      assert.equal(client.seen, null, 'phải chặn trước khi gửi, không phải sau');
      return;
    }

    await invoke(client, testCase);
    const seen = client.seen;
    assert.ok(seen, 'hàm không gọi ra request() lần nào');

    const want = testCase.expect;
    assert.equal(seen.verb, want.verb);
    assert.equal(seen.path, want.path);
    if ('query' in want) assert.deepEqual(seen.query, want.query);
    if ('fields' in want) assert.deepEqual(seen.fields, want.fields);
    if ('files' in want) assert.deepEqual(seen.files, want.files);
    if ('json' in want) assert.deepEqual(seen.json, want.json);
    if ('timeout_seconds_at_least' in want) {
      assert.ok(seen.timeout >= want.timeout_seconds_at_least * 1000,
        `hạn chờ ${seen.timeout}ms nhỏ hơn mức hợp đồng đòi`);
    }

    for (const [key, value] of Object.entries(testCase.after || {})) {
      assert.equal(client[key], value);
    }
  });
}

test('mọi cửa sinh ra đều có ít nhất một ca kiểm dùng chung', () => {
  // Một cửa không có ca nào là một cửa không ai canh. Cổng này ở đây chứ không ở bộ sinh: bộ sinh
  // mà tự chấm điểm cho mình thì nó vừa ra đề vừa chấm bài.
  const covered = new Set(CASES.map((c) => c.method));
  const missing = GENERATED.filter((name) => !covered.has(name));
  assert.deepEqual(missing, [], `chưa có ca kiểm dùng chung cho: ${missing.join(', ')}`);
});

test('mọi ca kiểm đều gọi một cửa có thật trong hợp đồng', () => {
  const unknown = [...new Set(CASES.map((c) => c.method))].filter((name) => !SPEC[name]);
  assert.deepEqual(unknown, [], `ca kiểm gọi cửa không có trong hợp đồng: ${unknown.join(', ')}`);
});
