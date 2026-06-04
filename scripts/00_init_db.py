"""初始化数据库（建表）。取数 / 计算 / 绘图逻辑见 common.py。"""
import common as c


def main():
    conn = c.get_connection()
    c.ensure_schema(conn)
    conn.close()
    c.log.info("数据库已初始化: %s", c.DB_PATH)


if __name__ == "__main__":
    main()
