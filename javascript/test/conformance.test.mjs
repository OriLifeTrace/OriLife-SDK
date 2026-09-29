/**
 * Run the SHARED cases in `contract/conformance.json` against the JavaScript implementation.
 *
 * Each language's own suite only proves that side agrees with itself. Two sides that agree with
 * themselves and disagree with each other stay green on both — exactly the gap three real bugs
 * went through (see the top of `python/orilife/_wire.py`). This file and its twin
 * `python/tests/test_conformance.py` run the SAME list of cases, so a side that drifts goes red.
 *
 * Measurement boundary: pinned where a method calls `request()` — the MAPPING (path, field names,
 * encoding). The transport underneath is held by `client.test.mjs`. Green here does NOT mean
 * everything is tested.
 */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { Client } from '../src/client.js';
import { load } from './_contract.mjs';

const CONTRACT = load('methods.json');
const CASES = load('conformance.json').cases;
const SPEC = Object.fromEntries(CONTRACT.methods.map((m) => [m.name, m]));
const GENERATED = CONTRACT.methods.filter((m) => m.generated !== false).map((m) => m.name);

// The same bytes for every fake file — the content is not what is measured, the field name is.
const BLOB = new Uint8Array([1, 2, 3]);

const camel = (snake) => snake.split('_')
  .map((w, i) => (i === 0 ? w : w.charAt(0).toUpperCase() + w.slice(1)))
  .join('');

/** Exactly what goes on the wire: drop empty values, stringify the rest. */
function clean(mapping) {
  const out = {};
  for (const [k, v] of Object.entries(mapping || {})) {
    if (v !== undefined && v !== null) out[k] = String(v);
  }
  return out;
}

/**
 * Turn a file placeholder in a test case into a real file of this language.
 *
 * `$single_file` is ONE file not wrapped in an array. On the Python side it becomes a path string,
 * because that is where that language breaks; here a string is not a valid file type, so the
 * natural form is a file object — and it still reaches this side's bug: calling `.map` on something
 * that is not an array.
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

/** The real client, with only the transport swapped for a notebook. */
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

/** Build the call from the argument spec in the contract, never guess from the case name. */
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
    else throw new Error(`case ${testCase.name}: missing required argument ${arg.name}`);
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
      // Throwing is not enough: it must throw BEFORE any byte leaves the machine. Throwing after
      // the images went up over a weak link is a full minute of waiting for a known error.
      assert.equal(client.seen, null, 'must refuse before sending, not after');
      return;
    }

    await invoke(client, testCase);
    const seen = client.seen;
    assert.ok(seen, 'the method never called request()');

    const want = testCase.expect;
    assert.equal(seen.verb, want.verb);
    assert.equal(seen.path, want.path);
    if ('query' in want) assert.deepEqual(seen.query, want.query);
    if ('fields' in want) assert.deepEqual(seen.fields, want.fields);
    if ('files' in want) assert.deepEqual(seen.files, want.files);
    if ('json' in want) assert.deepEqual(seen.json, want.json);
    if ('timeout_seconds_at_least' in want) {
      assert.ok(seen.timeout >= want.timeout_seconds_at_least * 1000,
        `timeout ${seen.timeout}ms is below what the contract requires`);
    }

    for (const [key, value] of Object.entries(testCase.after || {})) {
      assert.equal(client[key], value);
    }
  });
}

test('every generated method has at least one shared case', () => {
  // A method without a case is a method nobody guards. This gate lives here and not in the
  // generator: a generator that grades itself both sets the exam and marks it.
  const covered = new Set(CASES.map((c) => c.method));
  const missing = GENERATED.filter((name) => !covered.has(name));
  assert.deepEqual(missing, [], `no shared case yet for: ${missing.join(', ')}`);
});

test('every case calls a method that exists in the contract', () => {
  const unknown = [...new Set(CASES.map((c) => c.method))].filter((name) => !SPEC[name]);
  assert.deepEqual(unknown, [], `a case calls a method missing from the contract: ${unknown.join(', ')}`);
});
