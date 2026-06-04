"""全量历史回填：按交易日遍历 CFFEX 日行情，计算基差并写入 SQLite。

数据源：ak.get_cffex_daily（官方日汇总，含全部在交易合约）。
用法：
  python scripts/01_load_history_robust.py                          # 2019-01-01 至今
  python scripts/01_load_history_robust.py --start 20190101 --end 20260213
"""
import argparse
import datetime as dt

import akshare as ak
import pandas as pd

import common as c


def load_history(start_str, end_str):
    conn = c.get_connection()
    c.ensure_schema(conn)

    dates = c.trading_days(start_str, end_str)
    if not dates:
        c.log.error("未取得交易日历，终止。")
        return

    # 预缓存现货全历史：date(YYYY-MM-DD) -> {prod: close}
    c.log.info("缓存现货历史 ...")
    spot_cache = {}
    for prod, sym in c.SPOT_MAP.items():
        try:
            df = ak.stock_zh_index_daily(symbol=sym)
            df["d"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
            for d_str, close in zip(df["d"], df["close"]):
                spot_cache.setdefault(d_str, {})[prod] = float(close)
        except Exception as e:
            c.log.warning("缓存现货 %s 失败: %s", sym, e)

    c.log.info("开始抓取 %d 个交易日 ...", len(dates))
    for i, date_str in enumerate(dates, 1):
        db_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        try:
            df = ak.get_cffex_daily(date=date_str)
        except Exception as e:
            c.log.warning("%s 取数失败: %s", date_str, e)
            continue
        if df is None or df.empty:
            continue

        sym_col = "instrument" if "instrument" in df.columns else df.columns[0]
        price_col = "close" if "close" in df.columns else ("close_price" if "close_price" in df.columns else None)
        if not price_col:
            continue

        rows = []
        for _, r in df.iterrows():
            symbol = str(r[sym_col]).strip()
            prod = symbol[:2]
            if prod not in c.SPOT_MAP:
                continue
            spot_close = spot_cache.get(db_date, {}).get(prod)
            if spot_close is None:
                continue
            rows.append(c.make_row(
                symbol, db_date, r.get("open"), r.get("high"), r.get("low"),
                r[price_col], r.get("volume"), r.get("open_interest"), spot_close))
        c.upsert_rows(conn, rows)
        if i % 50 == 0:
            c.log.info("  进度 %d/%d (%s)", i, len(dates), date_str)

    conn.close()
    c.log.info("全量回填完成。")


def main():
    ap = argparse.ArgumentParser(description="CFFEX 基差全量历史回填")
    ap.add_argument("--start", default="20190101", help="起始日 YYYYMMDD（默认 20190101）")
    ap.add_argument("--end", default=dt.date.today().strftime("%Y%m%d"), help="结束日 YYYYMMDD（默认今天）")
    args = ap.parse_args()
    load_history(args.start, args.end)


if __name__ == "__main__":
    main()
