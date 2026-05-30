import akshare as ak
import pandas as pd
import sqlite3
import os
from datetime import datetime

# DB Path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cffex_basis.db")

SPOT_MAP = {
    'IF': 'sh000300',
    'IH': 'sh000016',
    'IC': 'sh000905',
    'IM': 'sh000852'
}

START_YEAR = 2019
CURRENT_YEAR = 2026

def get_spot_data(symbol):
    print(f"Fetching spot {symbol}...")
    try:
        df = ak.stock_zh_index_daily(symbol=symbol)
        df['date'] = pd.to_datetime(df['date']).dt.normalize()
        df = df[['date', 'close']].rename(columns={'close': 'spot_close'})
        return df
    except:
        return pd.DataFrame()

def load_all_history():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Ensure table exists
    c.execute('''CREATE TABLE IF NOT EXISTS futures_daily (
        symbol TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER, hold INTEGER, spot_close REAL, basis REAL,
        PRIMARY KEY (symbol, date)
    )''')
    conn.commit()

    for prod, spot_sym in SPOT_MAP.items():
        # Get Spot
        df_spot = get_spot_data(spot_sym)
        if df_spot.empty:
            print(f"Skipping {prod}, no spot data.")
            continue
            
        # Loop Years 2019-2026
        for yr in range(START_YEAR, CURRENT_YEAR + 1):
            yr_str = str(yr)[-2:]
            # Loop Months 01-12
            for m in range(1, 13):
                m_str = f"{m:02d}"
                symbol = f"{prod}{yr_str}{m_str}"
                
                # Check if already in DB? (Skip for now, or fetch fresh)
                # Just fetch fresh for bulk init
                print(f"Fetching {symbol}...", end="\r")
                
                try:
                    df = ak.futures_zh_daily_sina(symbol=symbol)
                    if df.empty:
                        continue
                        
                    # Process
                    df['date'] = pd.to_datetime(df['date']).dt.normalize()
                    df_merged = pd.merge(df, df_spot, on='date', how='inner') # inner join on trading days
                    
                    if df_merged.empty: continue
                    
                    # Calc Basis Points
                    df_merged['basis'] = df_merged['close'] - df_merged['spot_close']
                    df_merged['symbol'] = symbol
                    
                    # Insert Batch
                    rows = []
                    for _, row in df_merged.iterrows():
                        rows.append((
                            symbol, row['date'].strftime('%Y-%m-%d'),
                            row['open'], row['high'], row['low'], row['close'],
                            row['volume'], row['hold'],
                            row['spot_close'], row['basis']
                        ))
                    
                    c.executemany('''
                        INSERT OR REPLACE INTO futures_daily (symbol, date, open, high, low, close, volume, hold, spot_close, basis)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', rows)
                    conn.commit()
                    
                except Exception as e:
                    pass
        print(f"\n✅ Finished {prod}")

    conn.close()
    print("🎉 All history loaded!")

if __name__ == "__main__":
    load_all_history()
