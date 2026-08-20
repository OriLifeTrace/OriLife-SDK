"""Kiểm một mã OriLife mà KHÔNG cần tin OriLife.

Tải bản ghi từ kho lưu trữ theo nội dung, băm lại, so với con số đã neo lên chuỗi Cardano. Phép
băm chạy tại chỗ bằng thư viện chuẩn — không hỏi máy chủ "bản ghi này có đúng không", vì hỏi như
vậy là để bên bị kiểm tự chấm điểm mình.

Chạy:  python examples/kiem_chung.py ORI-w3gv5j2-A7K9PQ2M
"""
import json
import sys
import urllib.request

from orilife import Client, NotFoundError, verify

LAMPNET = "https://lampnet.cloud"


def kiem(code: str) -> int:
    client = Client()

    try:
        prov = client.tree_by_code(code)["provenance"]
    except NotFoundError:
        # 404 ở đây KHÔNG có nghĩa là mã sai. Cá thể riêng tư và cá thể không tồn tại trả cùng một
        # câu trả lời, cố ý như vậy để người dò mã không đếm được vườn người khác.
        print(f"{code}: không tra được (mã không có, hoặc chủ chưa mở công khai)")
        return 2

    with urllib.request.urlopen(f"{LAMPNET}/{prov['record_cid']}") as fh:
        record = json.load(fh)

    summary = verify.summarize(record, prov["record_hash"])
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if summary["missing_fields"]:
        # Bản ghi THIẾU trường khác hẳn bản ghi ĐỦ mà lệch mã băm: ca này gần như luôn là tải hụt
        # hoặc lấy nhầm mảnh, không phải ai đó đã sửa dữ liệu.
        print("\n⚠ bản ghi thiếu trường — nhiều khả năng tải chưa đủ, hãy tải lại")
        return 3

    if not summary["hash_matches"]:
        print("\n✗ mã băm KHÔNG khớp — bản ghi đã khác đi kể từ lúc neo")
        return 1

    print("\n✓ bản ghi khớp mã băm đã neo")
    anchor = prov.get("anchor") or {}
    if anchor.get("tx_hash"):
        # Bước cuối và là bước quan trọng nhất: con số vừa so là con số máy chủ đưa. Mở giao dịch
        # trên trình duyệt khối và đọc lại bằng mắt thì mới thoát khỏi lời khai của một bên.
        print(f"  đọc lại trên chuỗi: {anchor.get('explorer_url') or anchor['tx_hash']}")
        print(f"  metadata nhãn 1454, trường \"h\" phải bằng {prov['record_hash']}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("dùng: python kiem_chung.py ORI-…")
    sys.exit(kiem(sys.argv[1]))
