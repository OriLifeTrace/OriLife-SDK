#!/usr/bin/env python3
"""Sinh mã khách từ `contract/methods.json` — MỘT nguồn, nhiều bản cài.

    python3 tools/generate.py           # ghi lại các tệp sinh
    python3 tools/generate.py --check   # không ghi; đỏ nếu tệp trên đĩa lệch bản sinh

Vì sao có tệp này. Trước đây `python/orilife/client.py` và `javascript/src/client.js` là hai bản
chép tay của cùng một hợp đồng: sửa một cửa phải nhớ sửa hai chỗ, và không có gì kêu khi một bên
lệch. Hai lỗi đo được ngay lúc dựng tệp này — `create_farm` gửi `[10.762, 106.66]` bên Python và
`[10.762,106.66]` bên JavaScript (khác BYTE), `update_farm` mã hoá JSON cho mảng ở Python mà không
làm thế ở JavaScript — đều là loại lỗi không test nào bắt được, vì mỗi bên tự kiểm chính mình.

Bản sinh được COMMIT vào kho, không sinh lúc cài. Ba lý do: đọc được bằng mắt, hiện lên trong
`git diff` khi hợp đồng đổi, và không bắt người dùng có Python để cài gói JavaScript. Cổng chống
trôi là `--check` chạy trong CI: quên sinh lại thì CI đỏ, không phải chờ ai đó phát hiện.
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

BANNER_PY = '"""SINH TỰ ĐỘNG từ contract/methods.json — ĐỪNG SỬA TAY.\n\nSửa hợp đồng rồi chạy `python3 tools/generate.py`. Sửa thẳng tệp này thì lần sinh sau mất hết,\nvà CI (`tools/generate.py --check`) đỏ ngay ở commit đó.\n"""'
BANNER_JS = ("/**\n * SINH TỰ ĐỘNG từ contract/methods.json — ĐỪNG SỬA TAY.\n *\n"
             " * Sửa hợp đồng rồi chạy `python3 tools/generate.py`. Sửa thẳng tệp này thì lần sinh\n"
             " * sau mất hết, và CI (`tools/generate.py --check`) đỏ ngay ở commit đó.\n */")


# ── tên định danh ────────────────────────────────────────────────────────────────────────────

def camel(snake: str) -> str:
    head, *rest = snake.split("_")
    return head + "".join(w[:1].upper() + w[1:] for w in rest)


def js_lit(value) -> str:
    return json.dumps(value, ensure_ascii=False)


# ── đọc hợp đồng ─────────────────────────────────────────────────────────────────────────────

def load():
    with open(CONTRACT, encoding="utf-8") as fh:
        contract = json.load(fh)
    return contract, [m for m in contract["methods"] if m.get("generated", True)]


def split_args(method):
    """Tách tham số thành (vị trí, tuỳ chọn). `center_pair_other` đi kèm bạn của nó."""
    args = method.get("args", [])
    positional = [a for a in args if a.get("positional")]
    optional = [a for a in args if not a.get("positional")]
    return positional, optional


def wire_of(method):
    """Ba rổ đi lên dây: fields (biểu mẫu), params (truy vấn), files, json."""
    fields, params, files, jsonb = [], [], [], []
    extras = []          # bbox / varfields — cần dựng riêng
    for arg in method.get("args", []):
        kind = arg["kind"]
        if kind == "field":
            fields.append(arg)
        elif kind == "param":
            params.append(arg)
        elif kind in ("file", "files", "one_file"):
            files.append(arg)
        elif kind in ("json", "json_payload"):
            jsonb.append(arg)
        elif kind in ("bbox", "varfields", "center_pair"):
            extras.append(arg)
        elif kind in ("path", "path_raw", "center_pair_other"):
            pass
        else:
            raise SystemExit(f"kind lạ trong hợp đồng: {kind!r} ({method['name']})")
    return fields, params, files, jsonb, extras


# ── sinh Python ──────────────────────────────────────────────────────────────────────────────

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

    dict_items = [f'{js_lit(a["field"])}: {a["name"]}' for a in fields]
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
        else:
            call.append('files=[(%s, %s)]' % (js_lit(arg["field"]), arg["name"]))
    if jsonb:
        pairs = []
        for arg in jsonb:
            value = f"{arg['name']} or {{}}" if arg["kind"] == "json_payload" else arg["name"]
            pairs.append(f'{js_lit(arg["field"])}: {value}')
        call.append("json_body={%s}" % ", ".join(pairs))
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
        "from ._wire import (_as_file_list, _bbox_fields, _center_json, _encode_containers,",
        "                    _one_file, _quote)",
        "",
        '__all__ = ["GeneratedMethods", "CONTRACT_VERSION"]',
        "",
        "CONTRACT_VERSION = %s" % js_lit(contract["contract_version"]),
        "",
        "",
        "class GeneratedMethods:",
        '    """Mọi cửa API, sinh từ hợp đồng. `Client` kế thừa lớp này và cấp `request()`."""',
        "",
        "    request: Any",
        "    timeout: float",
        "    token: Any",
        "",
    ]
    out.append("\n\n".join(py_method(m) for m in methods))
    return "\n".join(out).rstrip() + "\n"


# ── sinh JavaScript ──────────────────────────────────────────────────────────────────────────

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

    dict_items = ["%s: %s" % (js_lit(a["field"]), camel(a["name"])) for a in fields]
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
        else:
            opts.append("files: [[%s, %s]]" % (js_lit(arg["field"]), camel(arg["name"])))
    if jsonb:
        pairs = []
        for arg in jsonb:
            value = "%s || {}" % camel(arg["name"]) if arg["kind"] == "json_payload" else camel(arg["name"])
            pairs.append("%s: %s" % (js_lit(arg["field"]), value))
        opts.append("json: { %s }" % ", ".join(pairs))
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
        "import { asFileList, bboxFields, centerJson, encodeContainers, oneFile, requireArgs } from './wire.js';",
        "",
        "export const CONTRACT_VERSION = %s;" % js_lit(contract["contract_version"]),
        "",
        "/** Mọi cửa API, sinh từ hợp đồng. `Client` kế thừa lớp này và cấp `request()`. */",
        "export class GeneratedMethods {",
    ]
    out.append("\n\n".join(js_method(m) for m in methods))
    out.append("}")
    return "\n".join(out).rstrip() + "\n"


# ── sinh bảng tra cho người đọc ──────────────────────────────────────────────────────────────

def emit_markdown(contract, methods):
    rows = ["<!-- SINH TỰ ĐỘNG từ contract/methods.json — ĐỪNG SỬA TAY. -->",
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


# ── ghi / kiểm ───────────────────────────────────────────────────────────────────────────────

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
            print("đã ghi %s" % os.path.relpath(path, ROOT))
    if check:
        if stale:
            print("LỆCH — các tệp sinh không khớp hợp đồng: %s" % ", ".join(stale),
                  file=sys.stderr)
            print("chạy `python3 tools/generate.py` rồi commit kết quả", file=sys.stderr)
            return 1
        print("KHỚP — %d cửa, các tệp sinh đúng bản hợp đồng v%s"
              % (len(methods), contract["contract_version"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
