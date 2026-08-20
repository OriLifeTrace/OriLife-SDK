/**
 * The API client has to behave at the places that only show up when the network is bad — which is
 * exactly when nobody is watching the logs. A fake `fetch` recreates those moments without a
 * network, and pins down the PATH and the PARAMETERS that go out on the wire: an endpoint renamed
 * or a field dropped is a bug the user only meets in the orchard, with no signal at all.
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

/** A client whose every call succeeds, so a test can look only at what was sent. */
function quietClient(script = []) {
  const f = fakeFetch(script);
  return { c: new Client('https://x.test', { fetch: f, token: 'k' }), f };
}

const img = (name = 'a.jpg') => ({ name, data: new Uint8Array([1, 2, 3]) });

test('the token rides in a Bearer header, not in a cookie', async () => {
  const f = fakeFetch([[200, { ok: true, token: 'abc123' }], [200, { ok: true }]]);
  const c = new Client('https://x.test', { fetch: f });
  await c.login('my_orchard', 'durian.orchard.2026');
  assert.equal(c.token, 'abc123');
  await c.me();
  assert.equal(f.seen[1].init.headers.Authorization, 'Bearer abc123');
  assert.equal(f.seen[1].init.credentials, undefined, 'must not carry cookies cross-origin');
});

test('the password travels in the JSON body, never in the query string', async () => {
  const f = fakeFetch([[200, { ok: true, token: 't' }]]);
  await new Client('https://x.test', { fetch: f }).login('someone', 'long.enough.password');
  assert.ok(!f.seen[0].url.includes('?'));
  assert.equal(JSON.parse(f.seen[0].init.body).password, 'long.enough.password');
});

test('empty fields are dropped, never sent as the string "null"', async () => {
  const f = fakeFetch([[200, { ok: true }]]);
  const c = new Client('https://x.test', { fetch: f });
  await c.identifyAuto([img()], { lat: 10.5 });
  const form = f.seen[0].init.body;
  assert.equal(form.get('lat'), '10.5');
  assert.equal(form.get('lon'), null);
  assert.ok(form.get('files'), 'the image must be attached');
});

test('being rate limited waits exactly as long as the server asked', async () => {
  const f = fakeFetch([
    [429, { ok: false, error: 'busy' }, { 'Retry-After': '0.05' }],
    [200, { ok: true }],
  ]);
  const t0 = Date.now();
  const out = await new Client('https://x.test', { fetch: f }).health();
  assert.equal(out.ok, true);
  assert.ok(Date.now() - t0 >= 50, 'the Retry-After header was ignored');
});

test('a failed WRITE endpoint is NOT resent', async () => {
  const f = fakeFetch([[500, { ok: false, error: 'broken' }], [200, { ok: true }]]);
  const c = new Client('https://x.test', { fetch: f });
  await assert.rejects(() => c.enrollTree([img()], { name: 'tree 1' }), errors.ServerError);
  assert.equal(f.seen.length, 1, 'a WRITE endpoint was resent');
});

test('a READ endpoint that breaks on the server side is retried', async () => {
  const f = fakeFetch([[500, { ok: false, error: 'broken' }], [200, { ok: true }]]);
  const out = await new Client('https://x.test', { fetch: f }).health();
  assert.equal(out.ok, true);
  assert.equal(f.seen.length, 2);
});

test('every status code becomes its own error type', async () => {
  const table = [[400, errors.InvalidRequestError], [401, errors.AuthError],
    [403, errors.PermissionError], [404, errors.NotFoundError],
    [413, errors.TooLargeError], [422, errors.InvalidRequestError],
    [500, errors.ServerError]];
  for (const [status, Kind] of table) {
    const f = fakeFetch([[status, { ok: false, error: 'the sentence for the user' }]]);
    const c = new Client('https://x.test', { fetch: f, maxRetries: 0 });
    await assert.rejects(() => c.resolve('ORI-0000000-AAAAAAAA'), (e) => {
      assert.ok(e instanceof Kind, `${status} must be ${Kind.name}, got ${e.name}`);
      assert.equal(e.message, 'the sentence for the user');
      assert.equal(e.status, status);
      return true;
    });
  }
});

test('the sentence shown to the user never comes from the validation shape', async () => {
  const f = fakeFetch([[422, { detail: [{ loc: ['body', 'file'], msg: 'field required' }] }]]);
  const c = new Client('https://x.test', { fetch: f, maxRetries: 0 });
  await assert.rejects(() => c.lookupFruit(img()), (e) => {
    assert.ok(!e.message.includes('loc'));
    assert.ok(e.payload.detail, 'the raw body is still there for whoever is debugging');
    return true;
  });
});

test('an unreachable server is a NetworkError, not a ServerError', async () => {
  const f = async () => { throw new TypeError('failed to fetch'); };
  const c = new Client('https://x.test', { fetch: f, maxRetries: 0 });
  await assert.rejects(() => c.health(), errors.NetworkError);
});

test('unknown fields in a response reach the app untouched', async () => {
  const f = fakeFetch([[200, { ok: true, decision: 'MATCH', a_field_added_next_year: 42 }]]);
  const out = await new Client('https://x.test', { fetch: f }).identifyTree([img()]);
  assert.equal(out.a_field_added_next_year, 42);
});

// ── supports(): ask the server once, then remember ──────────────────────────────────────────

test('supports() reads the endpoint index once and answers from memory afterwards', async () => {
  const { c, f } = quietClient([[200, { count: 2, routes: [{ path: '/api/identify', methods: ['POST'] }] }]]);
  assert.equal(await c.supports('/api/identify'), true);
  assert.equal(await c.supports('/api/identify/auto'), false);
  assert.equal(await c.supports('/api/identify'), true);
  assert.equal(f.seen.length, 1, 'the index was fetched more than once');
  assert.equal(f.seen[0].url, 'https://x.test/api');
});

test('a server with no endpoint index answers false instead of throwing', async () => {
  const { c } = quietClient([[404, { ok: false, error: 'no such thing' }]]);
  assert.equal(await c.supports('/api/identify/auto'), false);
});

test('supports() compares paths the way the server declares them', async () => {
  const index = [200, { routes: [{ path: '/api/farm/{farm_id}', methods: ['GET'] }] }];
  const { c } = quietClient([index]);
  assert.equal(await c.supports('/api/farm/{farm_id}'), true);
  assert.equal(await c.supports('api/farm/{farm_id}/'), true, 'a stray slash is not a different endpoint');
  assert.equal(await c.supports('/api/farm/{farm_id}?x=1'), true);
  assert.equal(await c.supports('/api/farm/abc123'), false, 'a filled-in template is not a declared path');
  assert.equal(await c.supports(''), false);
});

test('supports() caches nothing when the question was never answered', async () => {
  const f = async () => { throw new TypeError('failed to fetch'); };
  const c = new Client('https://x.test', { fetch: f, maxRetries: 0 });
  await assert.rejects(() => c.supports('/api/identify'), errors.NetworkError);
  assert.equal(c._declaredPaths, null, 'a network blip must not poison the cache');
});

test('a missing endpoint is an error, never a quiet fallback to another one', async () => {
  const { c, f } = quietClient([[404, { ok: false, error: 'no such thing' }]]);
  await assert.rejects(() => c.identifyAuto([img()]), errors.NotFoundError);
  assert.equal(f.seen.length, 1, 'the client tried a second endpoint on its own');
});

// ── orchards ────────────────────────────────────────────────────────────────────────────────

test('createFarm sends the centre as one pair, and only when both halves are there', async () => {
  const { c, f } = quietClient();
  await c.createFarm('Bay orchard', { lat: 10.5, lon: 106.6 });
  assert.equal(f.seen[0].url, 'https://x.test/api/farm');
  assert.equal(f.seen[0].init.method, 'POST');
  assert.equal(f.seen[0].init.body.get('name'), 'Bay orchard');
  assert.equal(f.seen[0].init.body.get('center_json'), '[10.5,106.6]');

  await c.createFarm('no coordinates', { lat: 10.5 });
  assert.equal(f.seen[1].init.body.get('center_json'), null, 'half a coordinate is not a place');
});

test('listFarms and getFarm hit the right paths, with the identifier escaped', async () => {
  const { c, f } = quietClient();
  await c.listFarms();
  assert.equal(f.seen[0].url, 'https://x.test/api/farms');
  assert.equal(f.seen[0].init.method, 'GET');

  await c.getFarm('farm 1/2');
  assert.equal(f.seen[1].url, 'https://x.test/api/farm/farm%201%2F2');
});

test('updateFarm passes field names through untouched', async () => {
  const { c, f } = quietClient();
  await c.updateFarm('f-1', { name: 'renamed', note: 'behind the house', boundary_method: 'gps_walk' });
  assert.equal(f.seen[0].url, 'https://x.test/api/farm/f-1/update');
  assert.equal(f.seen[0].init.method, 'POST');
  assert.equal(f.seen[0].init.body.get('name'), 'renamed');
  assert.equal(f.seen[0].init.body.get('note'), 'behind the house');
  assert.equal(f.seen[0].init.body.get('boundary_method'), 'gps_walk');
});

test('deleteFarm uses DELETE and is never resent by itself', async () => {
  const f = fakeFetch([[500, { ok: false, error: 'broken' }], [200, { ok: true }]]);
  const c = new Client('https://x.test', { fetch: f });
  await assert.rejects(() => c.deleteFarm('f-1'), errors.ServerError);
  assert.equal(f.seen[0].init.method, 'DELETE');
  assert.equal(f.seen[0].url, 'https://x.test/api/farm/f-1');
  assert.equal(f.seen.length, 1, 'a delete was resent');
});

// ── fruits ──────────────────────────────────────────────────────────────────────────────────

test('enrollFruit sends the tree, the name, the four bbox numbers and one file', async () => {
  const { c, f } = quietClient();
  await c.enrollFruit([img('fruit.jpg')], { treeId: 't-7', name: 'fruit 3', bbox: [10, 20, 30, 40] });
  assert.equal(f.seen[0].url, 'https://x.test/api/fruit/enroll');
  const form = f.seen[0].init.body;
  assert.equal(form.get('tree_id'), 't-7');
  assert.equal(form.get('name'), 'fruit 3');
  assert.deepEqual(
    ['bbox_x', 'bbox_y', 'bbox_w', 'bbox_h'].map((k) => form.get(k)),
    ['10', '20', '30', '40'],
  );
  assert.ok(form.get('file'), 'the image must be attached');
});

test('enrollFruit takes the bbox as four numbers or as named keys', async () => {
  const { c, f } = quietClient();
  await c.enrollFruit([img()], { treeId: 't-7', bbox: { x: 1, y: 2, w: 3, h: 4 } });
  assert.deepEqual(
    ['bbox_x', 'bbox_y', 'bbox_w', 'bbox_h'].map((k) => f.seen[0].init.body.get(k)),
    ['1', '2', '3', '4'],
  );
  // A box that is quietly ignored enrols the whole photo instead of the fruit — a wrong record
  // rather than a visible error, so a malformed box throws.
  assert.throws(() => c.enrollFruit([img()], { treeId: 't-7', bbox: [1, 2, 3] }), TypeError);
  assert.throws(() => c.enrollFruit([img()], { treeId: 't-7', bbox: { x: 1, y: 2, w: 3 } }), TypeError);
});

test('a second image is refused rather than silently dropped', async () => {
  const { c, f } = quietClient();
  assert.throws(() => c.enrollFruit([img('a.jpg'), img('b.jpg')], { treeId: 't-7' }), TypeError);
  assert.throws(() => c.addFruitView('fr-1', [img('a.jpg'), img('b.jpg')]), TypeError);
  assert.equal(f.seen.length, 0, 'a call went out with an image the server would have thrown away');
});

test('addFruitView names the fruit and sends the view under `file`', async () => {
  const { c, f } = quietClient();
  await c.addFruitView('fr-1', [img('side.jpg')]);
  assert.equal(f.seen[0].url, 'https://x.test/api/fruit/add_view');
  assert.equal(f.seen[0].init.body.get('fruit_id'), 'fr-1');
  assert.ok(f.seen[0].init.body.get('file'));
});

// ── animals ─────────────────────────────────────────────────────────────────────────────────

test('enrollAnimal sends every image under `images`, plus species and orchard', async () => {
  const { c, f } = quietClient();
  await c.enrollAnimal([img('a.jpg'), img('b.jpg')], {
    species: 'goat', farmId: 'f-1', name: 'number 12', ownerDid: 'did:phoenix:abc',
  });
  assert.equal(f.seen[0].url, 'https://x.test/api/animal/enroll');
  const form = f.seen[0].init.body;
  assert.equal(form.get('species'), 'goat');
  assert.equal(form.get('farm_id'), 'f-1');
  assert.equal(form.get('name'), 'number 12');
  assert.equal(form.get('owner_did'), 'did:phoenix:abc');
  assert.equal(form.getAll('images').length, 2);
});

test('scanAnimal sends the photo under `image`', async () => {
  const { c, f } = quietClient();
  await c.scanAnimal(img('goat.jpg'), { farmId: 'f-1', species: 'goat' });
  assert.equal(f.seen[0].url, 'https://x.test/api/animal/scan');
  assert.equal(f.seen[0].init.body.get('farm_id'), 'f-1');
  assert.equal(f.seen[0].init.body.get('species'), 'goat');
  assert.ok(f.seen[0].init.body.get('image'));
});

test('listAnimals puts its filters in the query string and omits what was not given', async () => {
  const { c, f } = quietClient();
  await c.listAnimals({ farmId: 'f-1', species: 'goat', limit: 50, offset: 100 });
  assert.equal(f.seen[0].url, 'https://x.test/api/animal/list?farm_id=f-1&species=goat&limit=50&offset=100');
  await c.listAnimals();
  assert.equal(f.seen[1].url, 'https://x.test/api/animal/list');
});

// ── verdicts ────────────────────────────────────────────────────────────────────────────────

test('each verdict carries the right name for "which one it really was"', async () => {
  const { c, f } = quietClient();
  await c.submitVerdict('q-1', 'wrong', { correctTreeId: 't-9' });
  await c.submitFruitVerdict('q-2', 'wrong', { correctFruitId: 'fr-9' });
  await c.submitAnimalVerdict('q-3', 'wrong', { correctDid: 'did:phoenix:9' });

  assert.equal(f.seen[0].url, 'https://x.test/api/identify_verdict');
  assert.equal(f.seen[0].init.body.get('query_id'), 'q-1');
  assert.equal(f.seen[0].init.body.get('verdict'), 'wrong');
  assert.equal(f.seen[0].init.body.get('correct_tid'), 't-9');

  assert.equal(f.seen[1].url, 'https://x.test/api/fruit/identify_verdict');
  assert.equal(f.seen[1].init.body.get('correct_fruit_id'), 'fr-9');

  assert.equal(f.seen[2].url, 'https://x.test/api/animal/identify_verdict');
  assert.equal(f.seen[2].init.body.get('correct_did'), 'did:phoenix:9');
});

test('a plain yes carries no correction field at all', async () => {
  const { c, f } = quietClient();
  await c.submitVerdict('q-1', 'correct');
  assert.equal(f.seen[0].init.body.get('correct_tid'), null);
});

// ── capture plan, timeline, anchoring ───────────────────────────────────────────────────────

test('capturePlan asks under the names the server uses for its query', async () => {
  const { c, f } = quietClient();
  await c.capturePlan('fruit', 'fr-9');
  assert.equal(f.seen[0].url, 'https://x.test/api/capture/plan?target_type=fruit&target_id=fr-9');
  assert.equal(f.seen[0].init.method, 'GET');
});

test('addEvent sends the kind and puts the caller data in the payload', async () => {
  const { c, f } = quietClient();
  await c.addEvent('tree', 't 1', 'water', { litres: 30 });
  assert.equal(f.seen[0].url, 'https://x.test/api/tree/t%201/event');
  assert.equal(f.seen[0].init.method, 'POST');
  assert.equal(f.seen[0].init.headers['Content-Type'], 'application/json');
  assert.deepEqual(JSON.parse(f.seen[0].init.body), { kind: 'water', payload: { litres: 30 } });

  await c.addEvent('fruit', 'fr-1', 'observe');
  assert.deepEqual(JSON.parse(f.seen[1].init.body), { kind: 'observe', payload: {} });
});

test('anchorEvent points at the entity and the event it was asked to seal', async () => {
  const { c, f } = quietClient();
  await c.anchorEvent('tree', 't-1', 'ev-2');
  assert.equal(f.seen[0].url, 'https://x.test/api/tree/t-1/event/ev-2/anchor');
  assert.equal(f.seen[0].init.method, 'POST');
});

// ── ending every session ────────────────────────────────────────────────────────────────────

test('logoutAll drops the local token, because the server just killed it', async () => {
  const { c, f } = quietClient();
  await c.logoutAll();
  assert.equal(f.seen[0].url, 'https://x.test/api/logout-all');
  assert.equal(f.seen[0].init.method, 'POST');
  assert.equal(c.token, null);
});
