"""
一次性数据库迁移脚本 (P0)

目的：
1. 为 futures_daily 表新增 basis_rate 列（基差率，单位 %），对齐 README 定义：
       basis_rate = (期货收盘 - 现货收盘) / 现货收盘 * 100
   原 basis 列（绝对点数）保留不动。
2. 用已有的 basis 与 spot_close 直接回填 basis_rate（无需重新联网抓数）。
3. 修复历史上被错误写成二进制 BLOB 的 volume / hold 字段
   （成因：akshare 返回 numpy.int64，直接传入 sqlite3 时按 buffer 协议存成了原始字节）。

本脚本幂等，可重复运行。
"""
import os
import sqlite3
import sys

# Windows 控制台默认 GBK，强制 stdout 用 utf-8 以正常输出中文/emoji
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cffex_basis.db"
)


def migrate():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 1. 新增 basis_rate 列（若不存在）
    cols = [r[1] for r in c.execute("PRAGMA table_info(futures_daily)")]
    if "basis_rate" not in cols:
        c.execute("ALTER TABLE futures_daily ADD COLUMN basis_rate REAL")
        print("✅ 新增列 basis_rate")
    else:
        print("ℹ️  basis_rate 列已存在，跳过新增")

    # 2. 修复 BLOB 类型的 volume / hold（小端 8 字节整数）
    c.execute(
        "SELECT rowid, volume, hold FROM futures_daily "
        "WHERE typeof(volume)='blob' OR typeof(hold)='blob'"
    )
    blob_rows = c.fetchall()
    for rowid, vol, hold in blob_rows:
        nv = int.from_bytes(vol, "little") if isinstance(vol, (bytes, bytearray)) else vol
        nh = int.from_bytes(hold, "little") if isinstance(hold, (bytes, bytearray)) else hold
        c.execute(
            "UPDATE futures_daily SET volume=?, hold=? WHERE rowid=?", (nv, nh, rowid)
        )
    print(f"✅ 修复 BLOB 行：{len(blob_rows)} 行")

    # 3. 回填 basis_rate
    c.execute(
        "UPDATE futures_daily "
        "SET basis_rate = ROUND(basis * 100.0 / spot_close, 6) "
        "WHERE spot_close IS NOT NULL AND spot_close != 0"
    )
    print(f"✅ 回填 basis_rate：{c.rowcount} 行")

    conn.commit()
    conn.close()
    print("🎉 迁移完成")


if __name__ == "__main__":
    migrate()
