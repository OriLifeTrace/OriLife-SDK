#!/usr/bin/env python3
"""Generate the client code from `contract/methods.json` — ONE source, several implementations.

    python3 tools/generate.py           # rewrite the generated files
    python3 tools/generate.py --check   # write nothing; red if a file on disk differs

Why this file exists. `python/orilife/client.py` and `javascript/src/client.js` used to be two
hand-written copies of the same contract: changing one endpoint meant remembering to change two
places, and nothing complained when one side drifted. Two bugs were measured when this file was
built — `create_farm` sent `[10.762, 106.66]` from Python and `[10.762,106.66]` from JavaScript
(different BYTES), and `update_farm` JSON-encoded an array in Python but not in JavaScript — both
the kind of bug no test catches, because each side only tests itself.

The generated output is COMMITTED, not generated at install time. Three reasons: it can be read,
it shows up in `git diff` when the contract changes, and nobody needs Python to install the
JavaScript package. The drift gate is `--check` in CI: forget to regenerate and CI goes red,
instead of waiting for someone to notice.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONTRACT = os.path.join(ROOT, "contract", "methods.json")

PY_OUT = os.path.join(ROOT, "python", "orilife", "_generated.py")
JS_OUT = os.path.join(ROOT, "javascript", "src", "generated.js")
MD_OUT = os.path.join(ROOT, "contract", "METHODS.md")

BANNER_PY = '"""GENERATED from contract/methods.json — DO NOT EDIT BY HAND.\n\nEdit the contract, then run `python3 tools/generate.py`. Edits made directly to this file are lost\nat the next generation, and CI (`tools/generate.py --check`) goes red on that very commit.\n"""'
BANNER_JS = ("/**\n * GENERATED from contract/methods.json — DO NOT EDIT BY HAND.\n *\n"
             " * Edit the contract, then run `python3 tools/generate.py`. Edits made directly to this\n"
             " * file are lost at the next generation, and CI (`tools/generate.py --check`) goes red on\n"
             " * that very commit.\n */")


# ── identifiers ──────────────────────────────────────────────────────────────────────────────────

def camel(snake: str) -> str:
    head, *rest = snake.split("_")
    return head + "".join(w[:1].upper() + w[1:] for w in rest)


def js_lit(value) -> str:
    return json.dumps(value, ensure_ascii=False)


# ── reading the contract───────────────────────────────────────────────────────────────────────

def load():
    with open(CONTRACT, encoding="utf-8") as fh:
        contract = json.load(fh)
    return contract, [m for m in contract["methods"] if m.get("generated", True)]


def split_args(method):
    """Split the arguments into (positional, optional). `center_pair_other` travels with its pair."""
    args = method.get("args", [])
    positional = [a for a in args if a.get("positional")]
    optional = [a for a in args if not a.get("positional")]
    return positional, optional


def wire_of(method):
    """The baskets that go on the wire: fields (form), params (query), files, json."""
    fields, params, files, jsonb = [], [], [], []
    extras = []          # bbox / varfields — built separately
    for arg in method.get("args", []):
        kind = arg["kind"]
        if kind in ("field", "csv"):
            fields.append(arg)
        elif kind == "param":
            params.append(arg)
        elif kind in ("file", "files", "one_file"):
            files.append(arg)
        elif kind in ("json", "json_payload", "json_object"):
            jsonb.append(arg)
        elif kind in ("bbox", "varfields", "center_pair"):
            extras.append(arg)
        elif kind in ("path", "path_raw", "center_pair_other"):
            pass
        else:
            raise SystemExit(f"unknown kind in the contract: {kind!r} ({method['name']})")
    if any(a["kind"] == "json_object" for a in jsonb) and len(jsonb) != 1:
        raise SystemExit(f"a json_object argument must be the whole body ({method['name']})")
    return fields, params, files, jsonb, extras


def drops_empty_json(jsonb):
    """True when a JSON body has optional keys.

    An optional key left out must be ABSENT from the body, not `null`: Python would send `null`
    and JavaScript would drop the key, so the two languages would disagree on the wire — and a
    server field typed `bool` answers `null` with 422. Required-only bodies are left as they are.
    """
    return any(a["kind"] == "json" and not a.get("required") for a in jsonb)


def optional_file(arg):
    """A single file the endpoint accepts but does not require."""
    return arg["kind"] == "file" and not arg.get("required")


# ── Python output ────────────────────────────────────────────────────────────────────────────

def py_signature(method):
    positional, optional = split_args(method)
    parts = ["self"]
    for arg in positional:
        if arg["kind"] == "json_payload":
            parts.append(f"{arg['name']}=None")
        else:
            parts.append(arg["name"])
    var = [a for a in optional if a["kind"] == "varfields"]
    plain = [a for a in optional if a["kind"] != "varfields"]
    if plain:
        parts.append("*")
        for arg in plain:
            parts.append(arg["name"] if arg.get("required") else f"{arg['name']}=None")
    for arg in var:
        parts.append(f"**{arg['name']}")
    return ", ".join(parts)


def py_path(method):
    path = method["path"]
    for arg in method.get("args", []):
        if arg["kind"] == "path":
            path = path.replace("{%s}" % arg["name"], "{_quote(%s)}" % arg["name"])
        elif arg["kind"] == "path_raw":
            path = path.replace("{%s}" % arg["name"], "{%s}" % arg["name"])
    return ('f"%s"' % path) if "{" in path else json.dumps(path)


def py_method(method):
    fields, params, files, jsonb, extras = wire_of(method)
    body = []

    dict_items = [f'{js_lit(a["field"])}: '
                  + (f'_csv({a["name"]})' if a["kind"] == "csv" else a["name"]) for a in fields]
    dict_items += [f"{js_lit(k)}: {js_lit(v)}" for k, v in (method.get("constants") or {}).items()]
    for arg in extras:
        if arg["kind"] == "center_pair":
            other = arg["with"]
            dict_items.append(f'{js_lit(arg["field"])}: _center_json({arg["name"]}, {other})')

    bbox = [a for a in extras if a["kind"] == "bbox"]
    var = [a for a in extras if a["kind"] == "varfields"]

    fields_expr = None
    if var:
        body.append(f"_fields = _encode_containers({var[0]['name']})")
        fields_expr = "_fields"
    elif bbox:
        body.append("_fields = {%s}" % ", ".join(dict_items))
        body.append(f"_fields.update(_bbox_fields({bbox[0]['name']}))")
        fields_expr = "_fields"
    elif dict_items:
        fields_expr = "{%s}" % ", ".join(dict_items)

    call = ["self.request(%s, %s" % (js_lit(method["verb"]), py_path(method))]
    if params:
        call.append("params={%s}" % ", ".join(
            f'{js_lit(a["field"])}: {a["name"]}' for a in params))
    if fields_expr:
        call.append("fields=%s" % fields_expr)
    if files:
        arg = files[0]
        if arg["kind"] == "files":
            call.append(
                'files=[(%s, _f) for _f in _as_file_list(%s)]' % (js_lit(arg["field"]), arg["name"]))
        elif arg["kind"] == "one_file":
            call.append('files=[(%s, _one_file(%s, %s))]'
                        % (js_lit(arg["field"]), arg["name"], js_lit(arg["error"])))
        elif optional_file(arg):
            call.append('files=[(%s, %s)] if %s is not None else None'
                        % (js_lit(arg["field"]), arg["name"], arg["name"]))
        else:
            call.append('files=[(%s, %s)]' % (js_lit(arg["field"]), arg["name"]))
    if jsonb and jsonb[0]["kind"] == "json_object":
        call.append("json_body=_json_object(%s, %s)"
                    % (jsonb[0]["name"], js_lit(method["name"])))
    elif jsonb:
        pairs = []
        for arg in jsonb:
            value = f"{arg['name']} or {{}}" if arg["kind"] == "json_payload" else arg["name"]
            pairs.append(f'{js_lit(arg["field"])}: {value}')
        body_expr = "{%s}" % ", ".join(pairs)
        if drops_empty_json(jsonb):
            body_expr = "_drop_empty(%s)" % body_expr
        call.append("json_body=%s" % body_expr)
    if method.get("timeout_min_seconds"):
        call.append("timeout=max(self.timeout, %.1f)" % float(method["timeout_min_seconds"]))
    request = ",\n            ".join(call) + ")"

    after = method.get("after")
    if after == "keep_token":
        body.append("return self._keep_token(%s)" % request)
    elif after == "clear_token":
        body.append("_out = %s" % request)
        body.append("self.token = None")
        body.append("return _out")
    else:
        body.append("return %s" % request)

    doc = method.get("doc") or []
    out = ["    def %s(%s) -> dict:" % (method["name"], py_signature(method))]
    if doc:
        out.append('        """%s' % doc[0])
        for line in doc[1:]:
            out.append(("        " + line).rstrip())
        out.append('        """')
    verb_note = "        # %s %s" % (method["verb"], method["path"])
    out.append(verb_note)
    for line in body:
        out.append("        " + line)
    return "\n".join(out)


def emit_python(contract, methods):
    out = [
        BANNER_PY,
        "from __future__ import annotations",
        "",
        "from typing import Any",
        "",
        "from ._wire import (_as_file_list, _bbox_fields, _center_json, _csv, _drop_empty,",
        "                    _encode_containers, _json_object, _one_file, _quote)",
        "",
        '__all__ = ["GeneratedMethods", "CONTRACT_VERSION"]',
        "",
        "CONTRACT_VERSION = %s" % js_lit(contract["contract_version"]),
        "",
        "",
        "class GeneratedMethods:",
        '    """Every API endpoint, generated from the contract. `Client` inherits this class and provides `request()`."""',
        "",
        "    request: Any",
        "    timeout: float",
        "    token: Any",
        "",
    ]
    out.append("\n\n".join(py_method(m) for m in methods))
    return "\n".join(out).rstrip() + "\n"


# ── JavaScript output ───────────────────────────────────────────────────────────────────────

def js_signature(method):
    positional, optional = split_args(method)
    parts = []
    for arg in positional:
        parts.append(camel(arg["name"]) + (" = null" if arg["kind"] == "json_payload" else ""))
    var = [a for a in optional if a["kind"] == "varfields"]
    plain = [a for a in optional if a["kind"] != "varfields"]
    if plain:
        names = ", ".join(camel(a["name"]) for a in plain)
        tail = "" if any(a.get("required") for a in plain) else " = {}"
        parts.append("{ %s }%s" % (names, tail))
    for arg in var:
        parts.append("%s = {}" % camel(arg["name"]))
    return ", ".join(parts)


def js_path(method):
    path = method["path"]
    has_template = False
    for arg in method.get("args", []):
        if arg["kind"] == "path":
            has_template = True
            path = path.replace("{%s}" % arg["name"], "${encodeURIComponent(%s)}" % camel(arg["name"]))
        elif arg["kind"] == "path_raw":
            has_template = True
            path = path.replace("{%s}" % arg["name"], "${%s}" % camel(arg["name"]))
    return ("`%s`" % path) if has_template else js_lit(path)


def js_method(method):
    fields, params, files, jsonb, extras = wire_of(method)
    lines = []

    required = [a for a in method.get("args", []) if a.get("required")]
    if required:
        pairs = ", ".join("%s: %s" % (camel(a["name"]), camel(a["name"])) for a in required)
        lines.append("requireArgs(%s, { %s });" % (js_lit(camel(method["name"])), pairs))

    dict_items = ["%s: %s" % (js_lit(a["field"]),
                              ("csvField(%s)" % camel(a["name"])) if a["kind"] == "csv"
                              else camel(a["name"])) for a in fields]
    dict_items += ["%s: %s" % (js_lit(k), js_lit(v)) for k, v in (method.get("constants") or {}).items()]
    for arg in extras:
        if arg["kind"] == "center_pair":
            dict_items.append("%s: centerJson(%s, %s)"
                              % (js_lit(arg["field"]), camel(arg["name"]), camel(arg["with"])))

    bbox = [a for a in extras if a["kind"] == "bbox"]
    var = [a for a in extras if a["kind"] == "varfields"]

    fields_expr = None
    if var:
        fields_expr = "encodeContainers(%s)" % camel(var[0]["name"])
    elif bbox:
        fields_expr = "{ %s }" % ", ".join(dict_items + ["...bboxFields(%s)" % camel(bbox[0]["name"])])
    elif dict_items:
        fields_expr = "{ %s }" % ", ".join(dict_items)

    opts = []
    if params:
        opts.append("params: { %s }" % ", ".join(
            "%s: %s" % (js_lit(a["field"]), camel(a["name"])) for a in params))
    if fields_expr:
        opts.append("fields: %s" % fields_expr)
    if files:
        arg = files[0]
        if arg["kind"] == "files":
            opts.append("files: asFileList(%s).map((f) => [%s, f])"
                        % (camel(arg["name"]), js_lit(arg["field"])))
        elif arg["kind"] == "one_file":
            opts.append("files: [[%s, oneFile(%s, %s)]]"
                        % (js_lit(arg["field"]), camel(arg["name"]), js_lit(arg["error"])))
        elif optional_file(arg):
            opts.append("files: (%s === undefined || %s === null) ? [] : [[%s, %s]]"
                        % (camel(arg["name"]), camel(arg["name"]), js_lit(arg["field"]),
                           camel(arg["name"])))
        else:
            opts.append("files: [[%s, %s]]" % (js_lit(arg["field"]), camel(arg["name"])))
    if jsonb and jsonb[0]["kind"] == "json_object":
        opts.append("json: jsonObject(%s, %s)"
                    % (camel(jsonb[0]["name"]), js_lit(camel(method["name"]))))
    elif jsonb:
        pairs = []
        for arg in jsonb:
            value = "%s || {}" % camel(arg["name"]) if arg["kind"] == "json_payload" else camel(arg["name"])
            pairs.append("%s: %s" % (js_lit(arg["field"]), value))
        body_expr = "{ %s }" % ", ".join(pairs)
        if drops_empty_json(jsonb):
            body_expr = "dropEmpty(%s)" % body_expr
        opts.append("json: %s" % body_expr)
    if method.get("timeout_min_seconds"):
        opts.append("timeout: Math.max(this.timeout, %d)" % (int(method["timeout_min_seconds"]) * 1000))

    call = "this.request(%s, %s%s)" % (
        js_lit(method["verb"]), js_path(method),
        (", {\n      " + ",\n      ".join(opts) + ",\n    }") if opts else "")

    after = method.get("after")
    if after == "keep_token":
        lines.append("return this._keep(await %s);" % call)
    elif after == "clear_token":
        lines.append("const out = await %s;" % call)
        lines.append("this.token = null;")
        lines.append("return out;")
    else:
        lines.append("return %s;" % call)

    is_async = after in ("keep_token", "clear_token")
    doc = method.get("doc") or []
    out = []
    if doc:
        out.append("  /**")
        for line in doc:
            out.append(("   * " + line).rstrip())
        out.append("   *")
        out.append("   * %s %s" % (method["verb"], method["path"]))
        out.append("   */")
    out.append("  %s%s(%s) {" % ("async " if is_async else "", camel(method["name"]),
                                 js_signature(method)))
    for line in lines:
        out.append("    " + line)
    out.append("  }")
    return "\n".join(out)


def emit_javascript(contract, methods):
    out = [
        BANNER_JS,
        "import {",
        "  asFileList, bboxFields, centerJson, csvField, dropEmpty, encodeContainers, jsonObject, oneFile,",
        "  requireArgs,",
        "} from './wire.js';",
        "",
        "export const CONTRACT_VERSION = %s;" % js_lit(contract["contract_version"]),
        "",
        "/** Every API endpoint, generated from the contract. `Client` inherits this class and provides `request()`. */",
        "export class GeneratedMethods {",
    ]
    out.append("\n\n".join(js_method(m) for m in methods))
    out.append("}")
    return "\n".join(out).rstrip() + "\n"


# ── lookup table for people ──────────────────────────────────────────────────────────────────

def emit_markdown(contract, methods):
    rows = ["<!-- GENERATED from contract/methods.json — DO NOT EDIT BY HAND. -->",
            "# Method map",
            "",
            "Generated from `contract/methods.json` v%s by `tools/generate.py`."
            % contract["contract_version"],
            "",
            "Python uses `snake_case`, JavaScript uses `camelCase`; the order and the semantics are",
            "identical, because both sides are generated from the same table.",
            "",
            "| Python | JavaScript | HTTP | Retried on failure |",
            "|---|---|---|---|"]
    for method in methods:
        positional, optional = split_args(method)
        py_args = ", ".join(
            [a["name"] for a in positional]
            + (["*"] if optional else [])
            + [("**" + a["name"]) if a["kind"] == "varfields" else a["name"] for a in optional])
        js_args = ", ".join(
            [camel(a["name"]) for a in positional]
            + (["{ %s }" % ", ".join(camel(a["name"]) for a in optional
                                     if a["kind"] != "varfields")] if any(
                a["kind"] != "varfields" for a in optional) else [])
            + [camel(a["name"]) for a in optional if a["kind"] == "varfields"])
        rows.append("| `%s(%s)` | `%s(%s)` | `%s %s` | %s |" % (
            method["name"], py_args, camel(method["name"]), js_args,
            method["verb"], method["path"],
            "yes, it is a read" if method.get("retry") == "safe" else "no, it may have arrived"))
    hand = [m for m in contract["methods"] if not m.get("generated", True)]
    if hand:
        rows += ["", "## Not generated", "",
                 "| Method | Why it is written by hand |", "|---|---|"]
        for method in hand:
            rows.append("| `%s()` / `%s()` | %s |"
                        % (method["name"], camel(method["name"]),
                           method.get("hand_written_because", "")))
    rows += ["",
             "Two places where the SDK argument name differs from the HTTP field name, because the",
             "HTTP names are abbreviations kept for backward compatibility:",
             "",
             "| SDK argument | HTTP field |", "|---|---|",
             "| `correct_tree_id` | `correct_tid` |",
             "| `entity_type` / `entity_id` in `capture_plan` | `target_type` / `target_id` |",
             ""]
    return "\n".join(rows)


# ── write / check ────────────────────────────────────────────────────────────────────────────

def main(argv):
    check = "--check" in argv
    contract, methods = load()
    wanted = {
        PY_OUT: emit_python(contract, methods),
        JS_OUT: emit_javascript(contract, methods),
        MD_OUT: emit_markdown(contract, methods),
    }
    stale = []
    for path, text in wanted.items():
        current = None
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                current = fh.read()
        if current == text:
            continue
        if check:
            stale.append(os.path.relpath(path, ROOT))
        else:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            print("wrote %s" % os.path.relpath(path, ROOT))
    if check:
        if stale:
            print("DRIFT — generated files do not match the contract: %s" % ", ".join(stale),
                  file=sys.stderr)
            print("run `python3 tools/generate.py` and commit the result", file=sys.stderr)
            return 1
        print("MATCH — %d methods, generated files match contract v%s"
              % (len(methods), contract["contract_version"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
