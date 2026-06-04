"""按品种 / 月份出图 CLI（从数据库读，对齐 README 运行方式）。

用法：
  python scripts/plot_basis.py --product IF --month 09            # 今年的 09 合约
  python scripts/plot_basis.py --product IF --month 09 --year 2026
  python scripts/plot_basis.py --all                             # 数据库中全部合约
"""
import argparse
import datetime as dt

import common as c


def main():
    ap = argparse.ArgumentParser(description="绘制指定合约的年化基差日历效应图")
    ap.add_argument("--product", choices=c.PRODUCTS, help="品种 IF/IH/IC/IM")
    ap.add_argument("--month", help="合约月份，如 09")
    ap.add_argument("--year", type=int, default=dt.date.today().year, help="合约年份（默认今年）")
    ap.add_argument("--all", action="store_true", help="绘制数据库中全部合约")
    args = ap.parse_args()

    if args.all:
        conn = c.get_connection()
        symbols = [r[0] for r in conn.execute(
            "SELECT DISTINCT symbol FROM futures_daily ORDER BY symbol")]
        conn.close()
        for s in symbols:
            c.plot_seasonality(s)
        return

    if not args.product or not args.month:
        ap.error("需指定 --product 和 --month（或用 --all）")

    symbol = f"{args.product}{str(args.year)[-2:]}{int(args.month):02d}"
    if c.plot_seasonality(symbol) is None:
        c.log.warning("%s 无数据，未出图", symbol)


if __name__ == "__main__":
    main()
