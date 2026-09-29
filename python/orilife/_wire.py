"""How request bodies are built — shared by every endpoint, and it must MATCH the JavaScript
version byte for byte.

This file is the Python twin of `javascript/src/wire.js`. The two files deliberately implement the
same transformation, and `contract/conformance.json` is what keeps them equal: every case in it
declares exactly what goes on the wire, and both languages replay the same list of cases.

What was wrong before this file existed (measured 2026-09-08, on `origin/main`):

  • `create_farm(lat=10.762, lon=106.66)` sent `center_json=[10.762, 106.66]` from Python and
    `[10.762,106.66]` from JavaScript. One space apart is different bytes; an endpoint that hashes
    the request body to detect duplicates would read two identical submissions as two different
    ones.
  • `update_farm(boundary_json=[[10.7, 106.6]])` JSON-encoded the value in Python, while in
    JavaScript `URLSearchParams` called `String([[10.7,106.6]])` and sent `10.7,106.6` — the server
    received a string that is not JSON, and neither side reported an error.
  • `identify_tree("photo.jpg")` in Python iterated the STRING character by character and uploaded
    9 one-character files. No function raised; the server received 9 junk files.

All three were silent failures: no exception, no error code, only wrong data at the far end.
"""
from __future__ import annotations

import json
import mimetypes
import os
import urllib.parse
import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

__all__ = [
    "FileArg", "_as_file", "_as_file_list", "_one_file", "_bbox_fields", "_center_json",
    "_encode_containers", "_multipart", "_quote",
]

FileArg = Union[str, bytes, Tuple[str, bytes], Tuple[str, bytes, str]]


def _quote(value: Any) -> str:
    """One path segment, escaped. `safe=''` so a `/` inside an identifier cannot cut the path."""
    return urllib.parse.quote(str(value), safe="")


def _as_file(item: FileArg) -> Tuple[str, bytes, str]:
    """Accept a path, a byte string, or a tuple; return (file name, bytes, content type)."""
    if isinstance(item, str):
        with open(item, "rb") as fh:
            data = fh.read()
        name = os.path.basename(item)
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        return name, data, ctype
    if isinstance(item, bytes):
        return "upload.jpg", item, "image/jpeg"
    if isinstance(item, tuple) and len(item) == 2:
        return item[0], item[1], (mimetypes.guess_type(item[0])[0] or "application/octet-stream")
    if isinstance(item, tuple) and len(item) == 3:
        return item
    raise TypeError("a file must be a path, bytes, (name, bytes) or (name, bytes, content type)")


def _as_file_list(images: Union[FileArg, Iterable[FileArg]]) -> List[FileArg]:
    """Turn "one image or several images" into a list.

    A path is a `str`, and a `str` is iterable — so treating the argument as a sequence without
    this guard turns "photo.jpg" into nine one-character files. Stop it here instead of uploading
    junk.
    """
    if isinstance(images, (str, bytes, tuple)):
        return [images]
    return list(images)


def _one_file(images: Union[FileArg, Iterable[FileArg]], message: str) -> FileArg:
    """Exactly ONE image for an endpoint that takes one image — raise on extras, never drop them
    quietly."""
    items = _as_file_list(images)
    if len(items) != 1:
        raise ValueError(message)
    return items[0]


def _bbox_fields(bbox: Any) -> Dict[str, Any]:
    """A bounding box as the four form fields the server expects.

    Accepts `(x, y, w, h)` or `{"x":…, "y":…, "w":…, "h":…}`. Anything else raises: a box that is
    silently ignored means the fruit is recorded from the WHOLE frame instead of from the fruit — a
    wrong record, which is worse than a visible error.
    """
    if bbox is None:
        return {}
    if isinstance(bbox, dict):
        try:
            x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
        except KeyError as e:
            raise ValueError(f"bbox dict is missing key {e}; expected x, y, w, h") from None
    else:
        box = list(bbox)
        if len(box) != 4:
            raise ValueError("bbox must hold exactly four numbers: (x, y, w, h)")
        x, y, w, h = box
    return {"bbox_x": x, "bbox_y": y, "bbox_w": w, "bbox_h": h}


def _compact_json(value: Any) -> str:
    """JSON WITHOUT extra spaces — exactly what `JSON.stringify` produces on the JavaScript side.

    `json.dumps` inserts a space after each comma by default; JavaScript does not. The same call in
    the two languages would yield two different strings, and neither side would know.
    """
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _center_json(lat: Any, lon: Any) -> Optional[str]:
    """Farm centre: send it only when BOTH halves are present. Half a coordinate is not a place."""
    if lat is None or lon is None:
        return None
    return _compact_json([lat, lon])


def _encode_containers(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Free-form fields: lists and mappings are JSON-encoded, everything else is kept; `None` is
    dropped.

    `boundary_json=[[lat, lon], …]` must reach the server as a JSON STRING. Leaving it to the form
    builder means each language stringifies it its own way.
    """
    return {k: (_compact_json(v) if isinstance(v, (list, dict, tuple)) else v)
            for k, v in fields.items() if v is not None}


def _multipart(fields: Dict[str, Any],
               files: Sequence[Tuple[str, FileArg]]) -> Tuple[bytes, str]:
    """Build the multipart body by hand.

    Written here instead of using `email.mime` because that module wraps lines the way mail does,
    and one extra byte inside a binary part is a broken photo at the far end.
    """
    boundary = f"----orilife{uuid.uuid4().hex}"
    out = bytearray()
    for key, value in fields.items():
        if value is None:
            continue
        out += f"--{boundary}\r\n".encode()
        out += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
        out += str(value).encode("utf-8") + b"\r\n"
    for key, item in files:
        name, data, ctype = _as_file(item)
        out += f"--{boundary}\r\n".encode()
        out += (f'Content-Disposition: form-data; name="{key}"; '
                f'filename="{name}"\r\n').encode()
        out += f"Content-Type: {ctype}\r\n\r\n".encode()
        out += data + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"
