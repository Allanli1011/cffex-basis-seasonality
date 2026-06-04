"""common.py — CFFEX 基差日历效应分析的共享工具。

集中放置配置、数据库 schema、akshare 取数、基差/年化计算与绘图，
供各脚本 `from common import ...` 复用，避免逻辑复制。
"""
import os
import glob
import sqlite3
import logging
import datetime as dt

import akshare as ak
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # 无界面后端，cron 环境安全
import matplotlib.pyplot as plt

# ---- 路径与配置 ----
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "cffex_basis.db")
OUTPUT_DIR = os.path.join(ROOT, "output")

SPOT_MAP = {"IF": "sh000300", "IH": "sh000016", "IC": "sh000905", "IM": "sh000852"}
PRODUCTS = tuple(SPOT_MAP.keys())

# 年化截断阈值：剩余自然日 < 此值的点不参与绘图（规避年化发散）
ANNUALIZE_MIN_DAYS = 3

# ---- 日志 ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("cffex")


# ---- 工具 ----
def to_int(x):
    """安全转换为 int，规避 numpy.int64 被 sqlite3 存成 BLOB。"""
    try:
        return int(x) if pd.notna(x) else 0
    except (TypeError, ValueError):
        return 0


def to_float(x):
    try:
        return float(x) if pd.notna(x) else None
    except (TypeError, ValueError):
        return None


def expiry_date(year, month):
    """中金所股指期货到期日 = 合约月份第三个周五。"""
    d = dt.date(year, month, 1)
    first_friday = d + dt.timedelta(days=(4 - d.weekday()) % 7)
    return first_friday + dt.timedelta(days=14)


def annualize(basis_rate, dates, year, month, min_days=ANNUALIZE_MIN_DAYS):
    """基差率(%)按距到期自然日年化：basis_rate × 365 / 剩余自然日。
    临近到期(剩余 < min_days 自然日)年化发散，予以截断。返回 numpy 数组。"""
    expiry = pd.Timestamp(expiry_date(year, month))
    dte = (expiry - pd.to_datetime(dates)).dt.days
    ann = np.asarray(basis_rate, dtype=float) * 365.0 / dte.clip(lower=1).to_numpy()
    return ann[dte.to_numpy() >= min_days]


# ---- 数据库 ----
SCHEMA = """
CREATE TABLE IF NOT EXISTS futures_daily (
    symbol TEXT, date TEXT,
    open REAL, high REAL, low REAL, close REAL,
    volume INTEGER, hold INTEGER,
    spot_close REAL, basis REAL, basis_rate REAL,
    PRIMARY KEY (symbol, date)
)
"""

_INSERT_SQL = """
INSERT OR REPLACE INTO futures_daily
    (symbol, date, open, high, low, close, volume, hold, spot_close, basis, basis_rate)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def ensure_schema(conn):
    conn.execute(SCHEMA)
    conn.commit()


def make_row(symbol, date_str, o, h, l, c, vol, hold, spot_close):
    """组装一行 upsert 元组，自动算 basis/basis_rate 并安全转换类型。"""
    fut_close = float(c)
    basis = fut_close - spot_close
    basis_rate = basis / spot_close * 100 if spot_close else None
    return (symbol, date_str, to_float(o), to_float(h), to_float(l), fut_close,
            to_int(vol), to_int(hold), spot_close, basis, basis_rate)


def upsert_rows(conn, rows):
    if rows:
        conn.executemany(_INSERT_SQL, rows)
        conn.commit()


# ---- akshare 取数 ----
def trading_days(start_str, end_str):
    """[start, end] 区间交易日列表（YYYYMMDD）。"""
    try:
        cal = ak.tool_trade_date_hist_sina()
        cal["trade_date"] = pd.to_datetime(cal["trade_date"]).dt.strftime("%Y%m%d")
        mask = (cal["trade_date"] >= start_str) & (cal["trade_date"] <= end_str)
        return cal.loc[mask, "trade_date"].tolist()
    except Exception as e:
        log.warning("获取交易日历失败: %s", e)
        return []


def is_trading_day(date_str=None):
    """date_str 默认今天(YYYYMMDD)。API 失败时返回 True（降级为照常运行）。"""
    date_str = date_str or dt.date.today().strftime("%Y%m%d")
    try:
        cal = ak.tool_trade_date_hist_sina()
        days = set(pd.to_datetime(cal["trade_date"]).dt.strftime("%Y%m%d"))
        return date_str in days
    except Exception as e:
        log.warning("无法获取交易日历(%s)，按交易日处理", e)
        return True


def active_contracts(date_str=None):
    """指定日期 CFFEX 在交易的 IF/IH/IC/IM 合约列表。"""
    date_str = date_str or dt.date.today().strftime("%Y%m%d")
    try:
        df = ak.get_cffex_daily(date=date_str)
    except Exception as e:
        log.error("获取活跃合约失败 (%s): %s", date_str, e)
        return []
    if df is None or df.empty:
        log.info("无当日行情(%s)，可能非交易日", date_str)
        return []
    col = "instrument" if "instrument" in df.columns else df.columns[0]
    return [str(s).strip() for s in df[col].unique() if str(s).strip()[:2] in SPOT_MAP]


def spot_latest():
    """各品种最新现货 {prod: (date_str, close)}。"""
    out = {}
    for prod, sym in SPOT_MAP.items():
        try:
            df = ak.stock_zh_index_daily(symbol=sym)
            if df is not None and not df.empty:
                row = df.iloc[-1]
                out[prod] = (pd.to_datetime(row["date"]).strftime("%Y-%m-%d"), float(row["close"]))
        except Exception as e:
            log.warning("获取现货 %s 失败: %s", sym, e)
    return out


def spot_on_date(date_hyphen):
    """各品种在指定日期(YYYY-MM-DD)的现货收盘 {prod: (date, close)}。"""
    out = {}
    for prod, sym in SPOT_MAP.items():
        try:
            df = ak.stock_zh_index_daily(symbol=sym)
            df = df[pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d") == date_hyphen]
            if not df.empty:
                out[prod] = (date_hyphen, float(df.iloc[0]["close"]))
        except Exception as e:
            log.warning("获取现货 %s@%s 失败: %s", sym, date_hyphen, e)
    return out


# ---- 增量更新 ----
def update_contracts(contracts, date_str=None):
    """抓取并 upsert 指定合约。date_str=None 取最新交易日，否则补录该日(YYYYMMDD)。
    强制现货与期货同日，避免错配。返回成功更新条数。"""
    conn = get_connection()
    ensure_schema(conn)
    if date_str:
        date_hyphen = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        spot = spot_on_date(date_hyphen)
    else:
        spot = spot_latest()

    n = 0
    for symbol in contracts:
        prod = symbol[:2]
        if prod not in spot:
            continue
        spot_date, spot_close = spot[prod]
        try:
            df = ak.futures_zh_daily_sina(symbol=symbol)
            if df is None or df.empty:
                continue
            df["_d"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
            row = df[df["_d"] == spot_date]  # 同日校验：取与现货同一天的期货
            if row.empty:
                log.info("%s 无 %s 期货数据(现货/期货不同步)，跳过", symbol, spot_date)
                continue
            r = row.iloc[0]
            conn.execute(_INSERT_SQL, make_row(
                symbol, spot_date, r["open"], r["high"], r["low"], r["close"],
                r["volume"], r["hold"], spot_close))
            conn.commit()
            n += 1
            basis = float(r["close"]) - spot_close
            log.info("更新 %s @ %s: 基差 %.2f (%.2f%%)", symbol, spot_date, basis, basis / spot_close * 100)
        except Exception as e:
            log.error("更新 %s 失败: %s", symbol, e)
    conn.close()
    return n


# ---- 绘图 ----
def plot_seasonality(symbol, output_dir=OUTPUT_DIR):
    """绘制单合约的年化基差率 vs 历年同月合约。返回保存路径，无数据时返回 None。"""
    prod, month = symbol[:2], symbol[-2:]
    month_int = int(month)
    current_yr = 2000 + int(symbol[2:4])

    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT symbol, date, basis_rate FROM futures_daily WHERE symbol LIKE ? ORDER BY date",
        conn, params=(f"{prod}%{month}",))
    conn.close()
    if df.empty:
        log.warning("%s 无历史数据", symbol)
        return None

    df["yr"] = df["symbol"].str[2:4].astype(int) + 2000
    aligned = {}
    for yr, g in df.groupby("yr"):
        g = g.sort_values("date")
        aligned[yr] = annualize(g["basis_rate"].to_numpy(), g["date"], int(yr), month_int).tolist()

    plt.figure(figsize=(12, 6))
    plt.title(f"{symbol} Annualized Basis Seasonality vs History ({month} Contracts)", fontsize=14)
    plt.xlabel("Trading Days Since Listing", fontsize=12)
    plt.ylabel("Annualized Basis Rate (%)", fontsize=12)
    plt.grid(True, alpha=0.3, linestyle="--")

    hist = []
    for yr, vals in aligned.items():
        if yr != current_yr and vals:
            plt.plot(range(1, len(vals) + 1), vals, color="gray", alpha=0.3, linewidth=1)
            hist.append(vals)
    if hist:
        max_len = max(len(x) for x in hist)
        lo, hi = [], []
        for i in range(max_len):
            day = [s[i] for s in hist if i < len(s)]
            lo.append(np.min(day) if day else np.nan)
            hi.append(np.max(day) if day else np.nan)
        plt.fill_between(range(1, len(lo) + 1), lo, hi, color="skyblue", alpha=0.3, label="Historical Range")

    cur = aligned.get(current_yr)
    if cur:
        days = list(range(1, len(cur) + 1))
        plt.plot(days, cur, color="red", linewidth=2.5, label=f"{symbol} (Current)")
        plt.scatter(days[-1], cur[-1], color="red", s=60, zorder=5)
        plt.text(days[-1] + 2, cur[-1], f"{cur[-1]:.1f}%", color="red", fontsize=10, fontweight="bold", va="center")

    plt.legend(loc="upper right")
    plt.tight_layout()
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"basis_{symbol}.png")
    plt.savefig(path, dpi=150)
    plt.close()
    log.info("图表已保存: %s", path)
    return path


def cleanup_charts(active, output_dir=OUTPUT_DIR):
    """删除不在 active 列表中的旧图。"""
    keep = set(active)
    for p in glob.glob(os.path.join(output_dir, "basis_*.png")):
        contract = os.path.basename(p)[len("basis_"):-len(".png")]
        if contract not in keep:
            try:
                os.remove(p)
                log.info("删除旧图: %s", os.path.basename(p))
            except OSError as e:
                log.warning("删除失败 %s: %s", p, e)
