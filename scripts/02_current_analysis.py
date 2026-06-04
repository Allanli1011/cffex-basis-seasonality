"""每日增量更新 + 出图（cron 主链路）。

用法：
  python scripts/02_current_analysis.py                  # 更新最新交易日并出图
  python scripts/02_current_analysis.py --date 20260213  # 补录指定历史日期
  python scripts/02_current_analysis.py --no-trading-check  # 跳过交易日检查
  python scripts/02_current_analysis.py --no-cleanup     # 不删除过期合约的旧图
"""
import argparse

import common as c


def main():
    ap = argparse.ArgumentParser(description="CFFEX 基差日历效应：每日更新 + 出图")
    ap.add_argument("--date", help="补录指定日期 YYYYMMDD（默认最新交易日）")
    ap.add_argument("--no-trading-check", action="store_true", help="跳过交易日检查")
    ap.add_argument("--no-cleanup", action="store_true", help="不删除过期合约的旧图")
    args = ap.parse_args()

    # 0. 交易日检查（仅在更新最新数据时；补录历史日期不检查）
    if not args.date and not args.no_trading_check:
        if not c.is_trading_day():
            c.log.info("今天不是交易日，跳过。")
            return

    # 1. 活跃合约
    contracts = c.active_contracts(args.date)
    if not contracts:
        c.log.warning("未获取到活跃合约，退出。")
        return
    c.log.info("活跃合约 (%d): %s", len(contracts), contracts)

    # 2. 增量更新（现货/期货同日校验在 update_contracts 内部）
    c.update_contracts(contracts, args.date)

    # 3. 清理过期合约旧图（补录历史日期时跳过，避免误删当前图）
    if not args.no_cleanup and not args.date:
        c.cleanup_charts(contracts)

    # 4. 出图
    for s in contracts:
        try:
            c.plot_seasonality(s)
        except Exception as e:
            c.log.error("绘图失败 %s: %s", s, e)
    c.log.info("全部完成。")


if __name__ == "__main__":
    main()
