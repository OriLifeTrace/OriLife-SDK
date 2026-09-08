#!/usr/bin/env python3
"""Đối chiếu `contract/methods.json` với đặc tả máy chủ đang chạy.

    python3 tools/check_server_drift.py                       # đo api.orilife.io
    python3 tools/check_server_drift.py --base-url https://…  # đo một máy chủ khác

Trả về BA trạng thái, không phải hai:

    KHỚP           mã thoát 0 — mọi cửa trong hợp đồng đều có trong `/openapi.json` của máy chủ
    LỆCH           mã thoát 1 — có cửa hợp đồng khai mà máy chủ không có
    KHÔNG ĐO ĐƯỢC  mã thoát 2 — không lấy được đặc tả (mất mạng, máy chủ im, JSON hỏng)

Trạng thái thứ ba phải KÊU TO HƠN trạng thái thứ hai, và tuyệt đối không được im lặng thành màu
xanh. Một phép đo trả "ổn" đúng lúc nó không đo được gì thì màu xanh của nó vô nghĩa: nó không nói
"ổn", nó nói "tôi không biết" bằng giọng của "ổn".

Vì sao cần phép đo này. `CONTRACT.md` viết tay đã trôi khỏi máy chủ trong mười chín ngày: bản viết
ngày 2026-08-20 khai `/api/identify/auto`, `/.well-known/orilife.json` và `/llms.txt` đều trả 404;
đo lại ngày 2026-09-08 thì lần lượt là 405 (cửa có thật, chỉ nhận POST), 200 và 200. Không có gì
báo trong suốt mười chín ngày ấy — bản sao chết trong im lặng, và người đọc TIN nó.

Phép này KHÁC `tools/generate.py --check`. Cái kia hỏi "mã sinh có khớp hợp đồng không" (chạy
được ngoại tuyến, luôn trả lời được). Cái này hỏi "hợp đồng có khớp máy chủ không" (cần mạng, có
lúc không trả lời được). Hai câu hỏi khác nhau, hai cổng khác nhau, đừng gộp.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRACT = os.path.join(ROOT, "contract", "methods.json")

MATCH, DRIFT, UNMEASURABLE = 0, 1, 2


def fetch_spec(base_url: str, timeout: float):
    """Trả về (đặc tả, lý do hỏng). Đúng một trong hai vế khác None."""
    url = base_url.rstrip("/") + "/openapi.json"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                   "User-Agent": "orilife-sdk-drift-check"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, f"máy chủ trả {e.code} ở {url}"
    except urllib.error.URLError as e:
        return None, f"không tới được {url}: {e.reason}"
    except (ValueError, TimeoutError) as e:
        return None, f"đặc tả ở {url} không đọc được: {e}"


def main(argv) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=None,
                        help="mặc định lấy từ contract/methods.json")
    parser.add_argument("--timeout", type=float, default=20.0)
    opts = parser.parse_args(argv)

    with open(CONTRACT, encoding="utf-8") as fh:
        contract = json.load(fh)
    base_url = opts.base_url or contract["base_url"]
    methods = [m for m in contract["methods"] if m.get("generated", True)]

    spec, why = fetch_spec(base_url, opts.timeout)
    if spec is None:
        print("KHÔNG ĐO ĐƯỢC — %s" % why, file=sys.stderr)
        print("Cổng này KHÔNG chạy lần này. Đừng đọc nó thành 'không có gì lệch'.", file=sys.stderr)
        return UNMEASURABLE

    paths = spec.get("paths")
    if not isinstance(paths, dict) or not paths:
        print("KHÔNG ĐO ĐƯỢC — đặc tả tải về không có mục `paths` nào", file=sys.stderr)
        print("Cổng này KHÔNG chạy lần này.", file=sys.stderr)
        return UNMEASURABLE

    missing = []
    wrong_verb = []
    for method in methods:
        declared = paths.get(method["path"])
        if declared is None:
            missing.append((method["name"], method["verb"], method["path"]))
        elif method["verb"].lower() not in {k.lower() for k in declared}:
            wrong_verb.append((method["name"], method["verb"], method["path"],
                               sorted(k.upper() for k in declared)))

    title = spec.get("info", {}).get("title", "?")
    version = spec.get("info", {}).get("version", "?")
    print("đo %s — %s v%s, đặc tả OpenAPI %s"
          % (base_url, title, version, spec.get("openapi", "?")))

    if missing or wrong_verb:
        print("LỆCH — hợp đồng khai những cửa máy chủ này không phục vụ:", file=sys.stderr)
        for name, verb, path in missing:
            print("  %-24s %s %s   ← không có trong /openapi.json" % (name, verb, path),
                  file=sys.stderr)
        for name, verb, path, have in wrong_verb:
            print("  %-24s %s %s   ← máy chủ chỉ nhận %s" % (name, verb, path, ", ".join(have)),
                  file=sys.stderr)
        print("Sửa contract/methods.json rồi chạy tools/generate.py, HOẶC hỏi bên máy chủ vì sao"
              " một cửa đã bàn giao lại biến mất.", file=sys.stderr)
        return DRIFT

    wrapped = {m["path"] for m in methods}
    print("KHỚP — mọi cửa trong hợp đồng đều có trong đặc tả máy chủ")
    print("       %d cửa SDK, nằm trên %d đường; máy chủ khai %d đường."
          % (len(methods), len(wrapped), len(paths)))
    print("       Phần chênh KHÔNG phải lỗi: SDK cố ý chỉ bọc phần một bên tích hợp cần, chỗ còn")
    print("       lại gọi thẳng bằng request().")
    return MATCH


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
