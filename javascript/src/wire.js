/**
 * How request bodies are built — shared by every endpoint, and it must MATCH the Python version
 * byte for byte.
 *
 * This file is the JavaScript twin of `python/orilife/_wire.py`. The two files deliberately
 * implement the same transformation, and `contract/conformance.json` is what keeps them equal:
 * every case in it declares exactly what goes on the wire, and both languages replay the same list
 * of cases.
 *
 * What was wrong before this file existed (measured 2026-09-08, on `origin/main`) — the full story
 * is at the top of the Python `_wire.py`, not repeated here.
 */

/** Turn "one image or several images" into an array. A lone image is not an array, nor is a string. */
export function asFileList(images) {
  if (images === null || images === undefined) return [];
  return Array.isArray(images) ? images.slice() : [images];
}

/**
 * Exactly ONE image for an endpoint that takes one image — throw on extras, never drop them quietly.
 *
 * Sending several parts named `file` does NOT upload several angles: the server reads the first
 * part and the rest disappear without a word. Losing a photo in silence is worse than an error.
 */
export function oneFile(images, message) {
  const items = asFileList(images);
  if (items.length !== 1) throw new TypeError(message);
  return items[0];
}

/**
 * A bounding box as the four form fields the server expects. Accepts `[x, y, w, h]` or
 * `{ x, y, w, h }`.
 *
 * Anything else throws: a box that is silently ignored means the fruit is recorded from the WHOLE
 * frame instead of from the fruit — a wrong record, which is worse than a visible error.
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

/** Farm centre: send it only when BOTH halves are present. Half a coordinate is not a place. */
export function centerJson(lat, lon) {
  if (lat === null || lat === undefined || lon === null || lon === undefined) return undefined;
  return JSON.stringify([lat, lon]);
}

/**
 * Free-form fields: arrays and objects are JSON-encoded, everything else is kept; empty values are
 * dropped.
 *
 * `boundary_json: [[lat, lon], …]` must reach the server as a JSON STRING. Leaving it to
 * `URLSearchParams` means it calls `String([[10.7,106.6]])` and sends `10.7,106.6`.
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
 * A required argument that is missing throws AT ONCE, before any image is uploaded.
 *
 * In Python the language does this itself (keyword-only parameters without a default). In
 * JavaScript a missing key is just `undefined`, the field is then dropped while the form is built,
 * and a few megabytes of images travel to an endpoint that is certain to refuse them — on a weak
 * connection that is a full minute of waiting for an error that could have been known up front.
 */
export function requireArgs(method, args) {
  const missing = Object.keys(args).filter((k) => args[k] === undefined || args[k] === null);
  if (missing.length) {
    throw new TypeError(`${method}() is missing required argument(s): ${missing.join(', ')}`);
  }
}

/** One uploaded file: a `Blob`/`File`, or `{ name, data }` where `data` is a Blob/ArrayBuffer/Uint8Array. */
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
