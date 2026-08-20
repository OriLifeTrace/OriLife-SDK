"""Luồng đầy đủ ngoài vườn: mở tài khoản, định danh, xử ba kết quả có thể ra, bồi hồ sơ.

Chạy:  python examples/nhan_dien.py anh1.jpg anh2.jpg
"""
import sys

from orilife import AuthError, Client, NetworkError, RateLimitedError

USERNAME = "vuon_cua_toi"          # 3–32 ký tự, chữ thường/số/chấm/gạch dưới — KHÔNG gạch nối
PASSWORD = "vuon.sau.rieng.2026"   # ≥10 ký tự, ≥2 nhóm ký tự, không nằm trong danh sách phổ biến


def dang_nhap() -> Client:
    client = Client()
    try:
        client.login(USERNAME, PASSWORD)
    except AuthError:
        client.signup(USERNAME, PASSWORD)
    return client


def main(paths):
    client = dang_nhap()

    # Đọc năng lực TRƯỚC khi hiện màn hình nào. Danh sách này sinh từ bảng đường dẫn thật của máy
    # chủ, nên nó không lạc hậu — viết cứng ở phía ứng dụng thì máy chủ thêm năng lực mà ứng dụng
    # vẫn giấu, còn máy chủ bỏ thì ứng dụng vẫn mời gọi.
    health = client.health()
    print(f"máy chủ {health['version']}, làm được: {', '.join(health.get('features', []))}")

    try:
        out = client.identify_auto(paths, lat=10.762622, lon=106.660172)
    except RateLimitedError as e:
        print(f"máy đang bận, chờ {e.retry_after:g} giây rồi thử lại")
        return
    except NetworkError as e:
        print(f"không gửi được: {e.message}")
        return

    if out["kind"] is None:
        # Máy chưa nhận ra đang nhìn cái gì. KHÔNG đoán hộ, KHÔNG thử lại — hỏi người dùng.
        print(out["message"])
        return

    if out.get("need"):
        print(f"loại {out['kind']} còn cần: {', '.join(out['need'])}")
        return

    result = out["result"]
    decision = result.get("decision")

    if decision == "MATCH":
        print(f"đúng rồi: {result['name']} (mức tin cậy {result['confidence']})")
        # Bồi hồ sơ NGAY sau một lần nhận đúng — thêm góc chụp lúc này đáng giá hơn nhiều so với
        # chụp thật nhiều góc trong một buổi, vì nó ghi lại cây ở một thời điểm khác.
        client.verify_add(result["tree_id"], paths)

    elif decision in ("UNCERTAIN", "MOVED"):
        # "Chưa chắc" là một KẾT QUẢ, không phải lỗi. Đừng thử lại, đừng hiện vòng xoay.
        print("chưa chắc là cây nào. Ứng viên:")
        for c in result.get("candidates", [])[:5]:
            print(f"  · {c['name']}")
        if result.get("allow_enroll_new"):
            print("  · hoặc: không phải cây nào cả")

    else:
        print("chưa gặp cây này bao giờ")
        if result.get("allow_enroll_new"):
            new = client.enroll_tree(paths, name="cây mới", lat=10.762622, lon=106.660172)
            print(f"đã đăng ký, mã {new.get('code')}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("dùng: python nhan_dien.py <ảnh> [ảnh...]")
    main(sys.argv[1:])
