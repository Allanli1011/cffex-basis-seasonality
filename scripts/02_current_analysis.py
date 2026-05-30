import sqlite3
import akshare as ak
import pandas as pd
import os
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
import warnings
import glob

warnings.filterwarnings("ignore")

# Config
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cffex_basis.db")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

SPOT_MAP = {
    'IF': 'sh000300', 'IH': 'sh000016', 'IC': 'sh000905', 'IM': 'sh000852'
}

def get_active_contracts():
    print("Fetching active contracts...")
    active_contracts = []
    
    today_str = datetime.now().strftime('%Y%m%d')
    try:
        # Get CFFEX Daily Summary
        df = ak.get_cffex_daily(date=today_str)
        if df.empty:
            print("No daily data (maybe non-trading day).")
            # Fallback for testing: IF2609, IF2606...
            return ['IF2609', 'IF2606', 'IF2603', 'IF2602']
            
        col = 'instrument' if 'instrument' in df.columns else ('symbol' if 'symbol' in df.columns else df.columns[0])
        symbols = df[col].unique().tolist()
        
        for s in symbols:
            s = s.strip()
            if s[:2] in ['IF', 'IH', 'IC', 'IM']:
                active_contracts.append(s)
                
    except Exception as e:
        print(f"Error fetching active contracts: {e}")
        return ['IF2609'] # Fallback
        
    return active_contracts

def update_db(contracts):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get Spot Data for Today
    spot_today = {}
    for prod, spot_sym in SPOT_MAP.items():
        try:
            df = ak.stock_zh_index_daily(symbol=spot_sym)
            if not df.empty:
                last_row = df.iloc[-1]
                spot_today[prod] = {
                    'date': pd.to_datetime(last_row['date']).strftime('%Y-%m-%d'),
                    'close': float(last_row['close'])
                }
        except:
            pass

    # Loop contracts
    for symbol in contracts:
        prod = symbol[:2]
        if prod not in spot_today: continue
        
        spot_info = spot_today[prod]
        spot_price = spot_info['close']
        spot_date = spot_info['date'] 
        
        try:
            df = ak.futures_zh_daily_sina(symbol=symbol)
            if df.empty: continue
            
            last_row = df.iloc[-1]
            fut_date = pd.to_datetime(last_row['date']).strftime('%Y-%m-%d')
            
            # Simple check: only update if date >= spot_date (to allow minor lag, but ideally equal)
            
            fut_close = float(last_row['close'])
            basis = fut_close - spot_price
            
            c.execute('''
                INSERT OR REPLACE INTO futures_daily (symbol, date, open, high, low, close, volume, hold, spot_close, basis)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                symbol, fut_date,
                last_row['open'], last_row['high'], last_row['low'], fut_close,
                last_row['volume'], last_row['hold'],
                spot_price, basis
            ))
            
            print(f"✅ Updated {symbol}: Basis {basis:.2f}")
            
        except Exception as e:
            print(f"❌ Failed to update {symbol}: {e}")
            
    conn.commit()
    conn.close()

def plot_seasonality(symbol):
    prod = symbol[:2]
    month = symbol[-2:] 
    
    print(f"\n📊 Plotting {symbol} (History: {month} contracts)...")
    
    conn = sqlite3.connect(DB_PATH)
    query = f"SELECT symbol, date, basis FROM futures_daily WHERE symbol LIKE '{prod}%{month}' ORDER BY date"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        print(f"❌ No history found in DB for {symbol}")
        return

    try:
        df['contract_year'] = df['symbol'].apply(lambda x: int("20" + x[2:4]))
    except:
        print("❌ Symbol format error")
        return

    current_yr = int("20" + symbol[2:4])
    years = df['contract_year'].unique()
    # print(f"✅ Found history years: {years}")
    
    aligned_data = {} 
    for yr, group in df.groupby('contract_year'):
        group = group.sort_values('date')
        basis_vals = group['basis'].tolist()
        aligned_data[yr] = basis_vals

    plt.figure(figsize=(12, 6))
    plt.title(f"{symbol} Basis Seasonality vs History ({month} Contracts)", fontsize=14)
    plt.xlabel("Trading Days Since Listing", fontsize=12)
    plt.ylabel("Basis Points", fontsize=12)
    plt.grid(True, alpha=0.3, linestyle='--')
    
    history_matrix = []
    
    for yr, vals in aligned_data.items():
        if yr != current_yr:
            plt.plot(range(1, len(vals)+1), vals, color='gray', alpha=0.3, linewidth=1)
            history_matrix.append(vals)
            
    if history_matrix:
        max_len = max([len(x) for x in history_matrix])
        min_curve, max_curve = [], []
        for i in range(max_len):
            day_vals = [s[i] for s in history_matrix if i < len(s)]
            if day_vals:
                min_curve.append(np.min(day_vals))
                max_curve.append(np.max(day_vals))
            else:
                min_curve.append(np.nan)
                max_curve.append(np.nan)
        
        plt.fill_between(range(1, len(min_curve)+1), min_curve, max_curve, color='skyblue', alpha=0.3, label='Historical Range (2019-2025)')
        
    if current_yr in aligned_data:
        vals = aligned_data[current_yr]
        if len(vals) > 0:
            days = range(1, len(vals)+1)
            plt.plot(days, vals, color='red', linewidth=2.5, label=f'{symbol} (Current)')
            plt.scatter(days[-1], vals[-1], color='red', s=60, zorder=5)
            plt.text(days[-1]+2, vals[-1], f"{vals[-1]:.2f}", color='red', fontsize=10, fontweight='bold', va='center')
        else:
            print(f"⚠️ Current year {current_yr} has no data points!")
    else:
        print(f"⚠️ Current year {current_yr} not found in DB!")

    plt.legend(loc='upper right')
    plt.tight_layout()
    
    save_path = os.path.join(OUTPUT_DIR, f"basis_{symbol}.png")
    plt.savefig(save_path, dpi=150)
    plt.close()
    print(f"✅ Chart saved: {save_path}")

def cleanup_old_charts(active_contracts):
    """
    删除不再活跃的合约的旧图表
    """
    # 获取 output 目录所有 PNG 文件
    all_charts = glob.glob(os.path.join(OUTPUT_DIR, "basis_*.png"))
    
    # 提取活跃合约名称
    active_set = set(active_contracts)
    
    # 删除不匹配的图表
    for chart_path in all_charts:
        # 从文件名提取合约代码，如 basis_IF2603.png -> IF2603
        filename = os.path.basename(chart_path)
        contract = filename.replace("basis_", "").replace(".png", "")
        
        if contract not in active_set:
            try:
                os.remove(chart_path)
                print(f"🗑️ 删除旧图表：{filename}")
            except Exception as e:
                print(f"⚠️ 删除失败 {chart_path}: {e}")

def get_trading_calendar_check():
    """
    Check if today is a trading day.
    Returns True if trading day, False otherwise.
    """
    today_str = datetime.now().strftime('%Y%m%d')
    try:
        df_cal = ak.tool_trade_date_hist_sina()
        df_cal['trade_date'] = pd.to_datetime(df_cal['trade_date']).dt.strftime('%Y%m%d')
        
        if today_str in df_cal['trade_date'].values:
            return True
        else:
            print(f"😴 今天 ({today_str}) 不是交易日，无需更新。")
            return False
    except Exception as e:
        print(f"⚠️ 无法获取交易日历 ({e})，尝试直接运行...")
        return True # Fallback to run if API fails

if __name__ == "__main__":
    # 0. Check Trading Day
    if not get_trading_calendar_check():
        exit(0)

    # 1. Get Active Contracts
    active_contracts = get_active_contracts()
    print(f"🎯 活跃合约：{active_contracts}")
    
    if not active_contracts:
        print("⚠️ 未获取到活跃合约列表。")
        exit(0)
    
    # 2. Update DB (Incremental)
    update_db(active_contracts)
    
    # 2.5. Cleanup old charts (删除到期合约的旧图表)
    print("🧹 清理旧合约图表...")
    cleanup_old_charts(active_contracts)
    
    # 3. Plot All
    print("📈 生成日历效应图...")
    for s in active_contracts:
        try:
            plot_seasonality(s)
        except Exception as e:
            print(f"❌ 绘图失败 {s}: {e}")
            
    print("✅ 全部完成！")
