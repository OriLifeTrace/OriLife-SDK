/**
 * Đường tới `contract/` — MỘT nơi giữ, mọi bộ kiểm trỏ về đây.
 *
 * Trước đây tệp này đọc `../../python/tests/vectors.json`: gói JavaScript thò tay vào ruột gói
 * Python. Xuất bản riêng một gói là đứt đường đó, mà không lệnh nào báo. Nay cả hai bên cùng trỏ
 * vào `contract/`, không bên nào sở hữu dữ liệu của bên kia.
 */
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const CONTRACT_DIR = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'contract');

/**
 * Đọc một tệp trong `contract/`. Thiếu tệp thì NÉM — đừng trả rỗng rồi chạy tiếp, bộ kiểm 0 ca
 * vẫn xanh và ai đọc cũng tưởng là đã kiểm.
 */
export function load(name) {
  return JSON.parse(readFileSync(join(CONTRACT_DIR, name), 'utf8'));
}
