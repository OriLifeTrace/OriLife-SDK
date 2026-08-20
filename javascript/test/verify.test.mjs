/**
 * Bản JavaScript phải cho ra ĐÚNG con số mà máy sản xuất tạo ra — cùng bộ vector với bản Python.
 *
 * Hai bản cài đặt độc lập cùng khớp một bộ vector là bằng chứng mạnh hơn hẳn một bản tự kiểm lấy
 * mình: một lỗi phải xuất hiện y hệt ở cả hai ngôn ngữ mới lọt được.
 *
 * Chạy: node --test  (không cài gì thêm)
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { test } from 'node:test';

import { blake2b, sha3_256 } from '../src/hash.js';
import * as verify from '../src/verify.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const V = JSON.parse(readFileSync(join(HERE, '..', '..', 'python', 'tests', 'vectors.json'), 'utf8'));

test('SHA3-256 khớp vector chuẩn FIPS 202', () => {
  assert.equal(sha3_256(''), 'a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a');
  assert.equal(sha3_256('abc'), '3a985da74fe225b2045c172d6bd390bd855f086e3e9d525b46bfe24511431532');
  assert.equal(
    sha3_256('abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq'),
    '41c0dba2a9d6240849100376a8235e2c82e1b9998a999e21db32dd97496d3376',
  );
});

test('BLAKE2b nhận độ dài đầu ra, không phải cắt ngắn BLAKE2b-512', () => {
  assert.equal(blake2b('', 32), '0e5751c026e543b2e8ab2eb06099daa1d1e5df47778f7787faab45cdf12fe3a8');
  assert.equal(blake2b('abc', 32), 'bddd813c634239723171ef3fee98579b94964e3bb1cb3e427262c8c068d52319');
  // Cắt ngắn bản 64 byte KHÔNG ra bản 32 byte — độ dài đầu ra nằm trong giá trị khởi tạo.
  assert.notEqual(blake2b('abc', 64).slice(0, 64), blake2b('abc', 32));
});

test('mã cá thể khớp bộ sinh trên máy sản xuất', () => {
  for (const c of V.codes) assert.equal(verify.entityCode(c.entity_id, c.gps), c.code, c.entity_id);
});

test('mã không có toạ độ vẫn đúng khuôn', () => {
  const code = verify.entityCode('khong-toa-do', null);
  assert.ok(code.startsWith('ORI-0000000-'));
  assert.equal(code.length, 4 + 7 + 1 + 8);
});

test('tuần tự hoá tất định: thứ tự khoá nhập vào không đổi kết quả', () => {
  const shuffled = Object.fromEntries(Object.entries(V.record).reverse());
  assert.equal(verify.canonicalJson(V.record), verify.canonicalJson(shuffled));
});

test('chữ tiếng Việt giữ nguyên, không thành \\uXXXX', () => {
  const raw = verify.canonicalJson({ name: 'cây sầu riêng' });
  assert.ok(raw.includes('cây sầu riêng'));
  assert.ok(!raw.includes('\\u'));
});

test('băm bản ghi khớp máy sản xuất', () => {
  assert.equal(verify.recordHash(V.record), V.record_hash_sha3_256);
  assert.equal(verify.verifyRecord(V.record, V.record_hash_sha3_256), true);
});

test('bản ghi cũ vẫn kiểm được, không phải băm lại', () => {
  assert.equal(verify.recordAlgorithm(V.record_v1), verify.HASH_ALGORITHM_LEGACY);
  assert.equal(verify.verifyRecord(V.record_v1, V.record_v1_hash_blake2b_256), true);
});

test('đổi một ký tự là mã băm gãy', () => {
  const tampered = { ...V.record, name: `${V.record.name} ` };
  assert.equal(verify.verifyRecord(tampered, V.record_hash_sha3_256), false);
});

test('hạ cấp thuật toán khai trong bản ghi không giúp được kẻ sửa', () => {
  const weakened = { ...V.record, hash_alg: verify.HASH_ALGORITHM_LEGACY };
  assert.equal(verify.verifyRecord(weakened, V.record_hash_sha3_256), false);
});

test('thuật toán lạ bị từ chối, không rơi về mặc định', () => {
  assert.equal(verify.verifyRecord({ ...V.record, hash_alg: 'rot13' }, V.record_hash_sha3_256), false);
});

test('đầu vào rác trả false chứ không ném lỗi', () => {
  assert.equal(verify.verifyRecord(null, 'abc'), false);
  assert.equal(verify.verifyRecord({}, ''), false);
  assert.equal(verify.verifyRecord({ v: 1 }, null), false);
});

test('bản tóm tắt tách được bản ghi thiếu trường khỏi bản ghi bị sửa', () => {
  const ok = verify.summarize(V.record, V.record_hash_sha3_256);
  assert.equal(ok.hashMatches, true);
  assert.deepEqual(ok.missingFields, []);
  const short = verify.summarize({ v: 2, code: 'ORI-0000000-AAAAAAAA' }, '0'.repeat(64));
  assert.ok(short.missingFields.length > 0);
  assert.equal(short.hashMatches, false);
});
