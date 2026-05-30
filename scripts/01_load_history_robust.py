import akshare as ak
import pandas as pd
import sqlite3
import os
from datetime import datetime, timedelta

# DB Path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cffex_basis.db")

SPOT_MAP = {
    'IF': 'sh000300', 'IH': 'sh000016', 'IC': 'sh000905', 'IM': 'sh000852'
}

START_DATE = "20190101"
END_DATE = "20260213"

def get_trading_days(start_str, end_str):
    try:
        df_cal = ak.tool_trade_date_hist_sina()
        df_cal['trade_date'] = pd.to_datetime(df_cal['trade_date']).dt.strftime('%Y%m%d')
        mask = (df_cal['trade_date'] >= start_str) & (df_cal['trade_date'] <= end_str)
        return df_cal.loc[mask, 'trade_date'].tolist()
    except:
        return []

def load_full_history():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Create Table
    c.execute('''CREATE TABLE IF NOT EXISTS futures_daily (
        symbol TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER, hold INTEGER, spot_close REAL, basis REAL,
        PRIMARY KEY (symbol, date)
    )''')
    conn.commit()

    # Get Trading Days
    dates = get_trading_days(START_DATE, END_DATE)
    if not dates:
        print("Failed to get trading days.")
        return

    # Cache Spot Data (Optimization)
    spot_cache = {} # date -> {prod: close}
    print("Fetching Spot History...")
    for prod, spot_sym in SPOT_MAP.items():
        try:
            df = ak.stock_zh_index_daily(symbol=spot_sym)
            if not df.empty:
                df['date_str'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                spot_dict = df.set_index('date_str')['close'].to_dict()
                for d_str, val in spot_dict.items():
                    if d_str not in spot_cache: spot_cache[d_str] = {}
                    spot_cache[d_str][prod] = float(val)
        except:
            pass

    print(f"Starting crawl for {len(dates)} days...")
    
    for i, date_str in enumerate(dates):
        print(f"Processing {date_str} ({i+1}/{len(dates)})...", end="\r")
        
        try:
            # Get Daily Futures (All Contracts)
            df_day = ak.get_cffex_daily(date=date_str)
            if df_day.empty: continue
            
            # Format Date for DB: YYYY-MM-DD
            db_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            
            rows_to_insert = []
            
            # Iterate contracts
            # Columns usually: instrument, open, high, low, volume, turnover, open_interest, close, settle...
            # Check col name for symbol
            sym_col = 'instrument' if 'instrument' in df_day.columns else ('symbol' if 'symbol' in df_day.columns else df_day.columns[0])
            price_col = 'close' if 'close' in df_day.columns else ('close_price' if 'close_price' in df_day.columns else None)
            
            if not price_col: continue

            for _, row in df_day.iterrows():
                symbol = row[sym_col].strip()
                prod = symbol[:2]
                
                if prod not in SPOT_MAP: continue
                
                # Get Spot Price
                spot_price = spot_cache.get(db_date, {}).get(prod)
                if spot_price is None: continue # Skip if no spot price
                
                fut_close = float(row[price_col])
                basis = fut_close - spot_price
                
                rows_to_insert.append((
                    symbol, db_date,
                    row.get('open', 0), row.get('high', 0), row.get('low', 0), fut_close,
                    row.get('volume', 0), row.get('open_interest', 0),
                    spot_price, basis
                ))
            
            if rows_to_insert:
                c.executemany('''
                    INSERT OR REPLACE INTO futures_daily (symbol, date, open, high, low, close, volume, hold, spot_close, basis)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', rows_to_insert)
                conn.commit()
                
        except Exception as e:
            # print(f"Error on {date_str}: {e}")
            pass
            
    conn.close()
    print("\n🎉 Full history crawl complete!")

if __name__ == "__main__":
    load_full_history()
