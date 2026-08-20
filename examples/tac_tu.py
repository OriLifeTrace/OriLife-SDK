"""Một tác tử tự tìm hiểu dịch vụ rồi kiểm một lô hàng — không có ai chỉ đường trước.

Đây là luồng mà một con bot hoặc một tác tử ngôn ngữ sẽ đi: đọc bản khai dịch vụ để biết cửa nào
gọi được khi chưa có khoá, rồi chỉ dùng đúng những cửa đó.

Chạy:  python examples/tac_tu.py ORI-w3gv5j2-A7K9PQ2M ORI-…
"""
import json
import sys
import urllib.request

from orilife import Client, NotFoundError, RateLimitedError, verify


def main(codes):
    client = Client()

    # Bước một của mọi tác tử: hỏi "nơi này là gì và tôi được làm gì". Đừng đoán bằng cách thử
    # từng cửa cho tới khi có cửa trả lời — thử mò là cách nhanh nhất để bị hạn tần suất.
    desc = client.describe()
    public = {(e["method"], e["path"]) for e in desc["public_endpoints"]}
    print(f"{desc['name']} {desc['version']} — {len(public)} cửa gọi được khi chưa có khoá")
    print("loại thực thể có tuyến:", ", ".join(k["label"] for k in desc["entity_kinds"]))

    if ("GET", "/api/resolve/{code}") not in public:
        # Bản khai là nguồn sự thật. Nó không khai cửa này thì đừng gọi mò.
        print("dịch vụ không mở cửa tra mã — dừng")
        return

    for code in codes:
        try:
            out = client.resolve(code)
        except RateLimitedError as e:
            print(f"{code}: bị hạn tần suất, chờ {e.retry_after:g}s")
            continue
        except NotFoundError:
            print(f"{code}: không tra được")
            continue

        state = out.get("state") or out.get("status")
        if state != "public":
            # `unknown` KHÔNG kèm lý do. Đừng suy ra sự tồn tại từ chỗ khác biệt — không có chỗ
            # khác biệt nào để suy, và cố suy là đang dò dữ liệu vườn người khác.
            print(f"{code}: {state} — không có gì thêm để nói, và đúng như vậy")
            continue

        prov = (out.get("provenance") or {})
        if not prov.get("record_cid"):
            print(f"{code}: công khai nhưng chưa có bản ghi neo")
            continue

        with urllib.request.urlopen(f"https://lampnet.cloud/{prov['record_cid']}") as fh:
            record = json.load(fh)

        s = verify.summarize(record, prov.get("record_hash"))
        mark = "✓" if s["hash_matches"] else "✗"
        print(f"{code}: {mark} {s['n_images']} ảnh, đăng ký {s['enrolled_at']}, "
              f"băm bằng {s['algorithm']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("dùng: python tac_tu.py ORI-… [ORI-…]")
    main(sys.argv[1:])
