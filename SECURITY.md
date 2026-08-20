# An toàn

## Báo lỗ hổng

Gửi về `security@orilife.io`. Đừng mở issue công khai cho lỗ hổng — cho chúng tôi thời gian vá
trước khi nó thành công thức cho người khác.

## Khoá đi đâu, và không đi đâu

**Khoá thuộc về người dùng, không thuộc về ứng dụng.** Mỗi người dùng đăng nhập bằng tài khoản của
chính họ và nhận khoá riêng. Đừng nhúng một tài khoản dùng chung vào ứng dụng rồi để mọi người
dùng đi qua nó: mọi người sẽ nhìn thấy vườn của nhau, và khi cần thu hồi thì không thu hồi được
riêng ai.

**Không nhúng mật khẩu hay khoá vào gói ứng dụng.** Tệp `.apk`, `.ipa` và gói JavaScript đều mở ra
đọc được. Mọi thứ nhúng vào đó là công khai, chỉ là chưa ai để ý.

**Khoá sống 12 giờ.** Hết hạn thì cửa trả `401`. Bắt lấy và đăng nhập lại; đừng giữ mật khẩu trong
bộ nhớ suốt vòng đời ứng dụng để tự đăng nhập lại ngầm — đó là đổi một lỗi nhìn thấy được lấy một
rủi ro không nhìn thấy.

**Giữ khoá ở kho khoá của hệ điều hành**, không ở `localStorage` nếu ứng dụng có phần nào chạy
trong trình duyệt.

**Nghi lộ thì gọi `POST /api/logout-all`** — nó bỏ mọi khoá của tài khoản, không riêng khoá đang cầm.

## Trình duyệt

Máy chủ mở CORS cho mọi origin, kèm **không** gửi cookie khác origin. Hai vế đi cùng nhau và vế thứ
hai mới là vế giữ an toàn: không có cookie đi kèm thì không có quyền-đi-kèm nào để một trang web lạ
lợi dụng, và cả lớp CSRF biến mất. Đổi lại, khoá **phải** đi bằng header `Authorization: Bearer`.

Đường cookie chỉ hoạt động ở cùng origin với máy chủ.

## Dữ liệu người dùng

**Ảnh gửi lên là ảnh vườn của một người thật.** Đừng ghi chúng vào nhật ký, đừng gửi sang dịch vụ
thứ ba để "tiện gỡ lỗi", đừng giữ lại sau khi đã dùng xong.

**Toạ độ là dữ liệu nhạy cảm.** Nó chỉ đúng tới gốc cây của một người. Cửa công khai đã làm thô
toạ độ trước khi trả; đừng khôi phục lại độ chính xác bằng dữ liệu bạn có từ nguồn khác rồi công
bố.

**Không đưa dữ liệu cá nhân vào chuỗi truy vấn.** Chuỗi truy vấn rơi vào nhật ký của mọi máy trên
đường đi. Bộ công cụ này gửi mật khẩu trong thân JSON chính vì lý do đó.

## Kiểm chứng

Bộ kiểm chứng (`orilife.verify`, `@orilife/sdk/verify`) không mạng, không phụ thuộc, không trạng
thái. Đó là chủ ý: một bộ kiểm chứng phải kiểm được cả trong trường hợp bạn không tin bên đã viết
ra nó. Đọc hết `python/orilife/verify.py` mất chừng mười phút.

Đối chiếu với bộ vector trong `python/tests/vectors.json` — sinh từ chính mã đang chạy trên máy
chủ, và cả hai bản cài đặt (Python, JavaScript) đều phải khớp.
