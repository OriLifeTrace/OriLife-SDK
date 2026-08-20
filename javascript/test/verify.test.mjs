/**
 * The JavaScript build must produce EXACTLY the numbers production produces — the same vector set
 * the Python build is checked against.
 *
 * Two independent implementations agreeing on one vector set is far stronger evidence than one
 * implementation checking itself: a bug now has to appear identically in both languages to slip
 * through.
 *
 * Run it with: node --test  (nothing to install)
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

test('SHA3-256 matches the standard FIPS 202 vectors', () => {
  assert.equal(sha3_256(''), 'a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a');
  assert.equal(sha3_256('abc'), '3a985da74fe225b2045c172d6bd390bd855f086e3e9d525b46bfe24511431532');
  assert.equal(
    sha3_256('abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq'),
    '41c0dba2a9d6240849100376a8235e2c82e1b9998a999e21db32dd97496d3376',
  );
});

test('BLAKE2b takes an output length, it does not truncate BLAKE2b-512', () => {
  assert.equal(blake2b('', 32), '0e5751c026e543b2e8ab2eb06099daa1d1e5df47778f7787faab45cdf12fe3a8');
  assert.equal(blake2b('abc', 32), 'bddd813c634239723171ef3fee98579b94964e3bb1cb3e427262c8c068d52319');
  // Slicing the 64-byte digest does NOT give the 32-byte one — the length is in the initial value.
  assert.notEqual(blake2b('abc', 64).slice(0, 64), blake2b('abc', 32));
});

test('entity codes match the generator running in production', () => {
  for (const c of V.codes) assert.equal(verify.entityCode(c.entity_id, c.gps), c.code, c.entity_id);
});

test('a code with no coordinates still has the right shape', () => {
  const code = verify.entityCode('no-coordinates', null);
  assert.ok(code.startsWith('ORI-0000000-'));
  assert.equal(code.length, 4 + 7 + 1 + 8);
});

test('deterministic serialisation: the order keys come in does not change the result', () => {
  const shuffled = Object.fromEntries(Object.entries(V.record).reverse());
  assert.equal(verify.canonicalJson(V.record), verify.canonicalJson(shuffled));
});

test('non-ASCII text survives verbatim, never as \\uXXXX', () => {
  // Real records carry Vietnamese names, so the sample text comes from the shared vectors rather
  // than from a literal typed here: the bytes under test are the bytes production hashes.
  const raw = verify.canonicalJson({ name: V.record.name });
  assert.ok(raw.includes(V.record.name));
  assert.ok(!raw.includes('\\u'));
});

test('record hashes match production', () => {
  assert.equal(verify.recordHash(V.record), V.record_hash_sha3_256);
  assert.equal(verify.verifyRecord(V.record, V.record_hash_sha3_256), true);
});

test('old records stay verifiable, without being rehashed', () => {
  assert.equal(verify.recordAlgorithm(V.record_v1), verify.HASH_ALGORITHM_LEGACY);
  assert.equal(verify.verifyRecord(V.record_v1, V.record_v1_hash_blake2b_256), true);
});

test('changing one character breaks the hash', () => {
  const tampered = { ...V.record, name: `${V.record.name} ` };
  assert.equal(verify.verifyRecord(tampered, V.record_hash_sha3_256), false);
});

test('downgrading the algorithm declared in a record does not help a forger', () => {
  const weakened = { ...V.record, hash_alg: verify.HASH_ALGORITHM_LEGACY };
  assert.equal(verify.verifyRecord(weakened, V.record_hash_sha3_256), false);
});

test('an unknown algorithm is refused, with no fallback to the default', () => {
  assert.equal(verify.verifyRecord({ ...V.record, hash_alg: 'rot13' }, V.record_hash_sha3_256), false);
});

test('junk input returns false instead of throwing', () => {
  assert.equal(verify.verifyRecord(null, 'abc'), false);
  assert.equal(verify.verifyRecord({}, ''), false);
  assert.equal(verify.verifyRecord({ v: 1 }, null), false);
});

test('the summary separates a record missing fields from a record that was altered', () => {
  const ok = verify.summarize(V.record, V.record_hash_sha3_256);
  assert.equal(ok.hashMatches, true);
  assert.deepEqual(ok.missingFields, []);
  const short = verify.summarize({ v: 2, code: 'ORI-0000000-AAAAAAAA' }, '0'.repeat(64));
  assert.ok(short.missingFields.length > 0);
  assert.equal(short.hashMatches, false);
});
