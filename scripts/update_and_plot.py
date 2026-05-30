import sqlite3
import akshare as ak
import pandas as pd
import os
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
import warnings

warnings.filterwarnings("ignore")

# Config
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cffex_basis.db")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")

SPOT_MAP = {
    'IF': 'sh000300', 'IH': 'sh000016', 'IC': 'sh000905', 'IM': 'sh000852'
}

def get_current_contracts():
    """
    Identify active contracts (Current, Next, Next Q, Next Next Q)
    Or fetch all available from akshare daily summary.
    """
    print("Fetching active contracts...")
    active_contracts = []
    
    today_str = datetime.now().strftime('%Y%m%d')
    try:
        # Get CFFEX Daily Summary
        df = ak.get_cffex_daily(date=today_str)
        if df.empty:
            print("No daily data (maybe non-trading day).")
            return []
            
        # Extract symbols (instrument usually)
        col = 'instrument' if 'instrument' in df.columns else ('symbol' if 'symbol' in df.columns else df.columns[0])
        symbols = df[col].unique().tolist()
        
        # Filter only IF/IH/IC/IM
        for s in symbols:
            s = s.strip()
            if s[:2] in ['IF', 'IH', 'IC', 'IM']:
                active_contracts.append(s)
                
    except Exception as e:
        print(f"Error fetching active contracts: {e}")
        # Fallback logic if API fails?
        # Maybe generate based on current date (e.g. current month + next + 2 quarters)
        pass
        
    return active_contracts

def update_db(contracts):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get Spot Data for Today (Optimization: fetch once per product)
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

    today_str = datetime.now().strftime('%Y-%m-%d')
    
    # Loop contracts
    for symbol in contracts:
        prod = symbol[:2]
        if prod not in spot_today: continue
        
        spot_info = spot_today[prod]
        spot_price = spot_info['close']
        spot_date = spot_info['date'] # Use spot date as anchor (trading day)
        
        # Fetch Contract Daily (Just last row)
        try:
            df = ak.futures_zh_daily_sina(symbol=symbol)
            if df.empty: continue
            
            last_row = df.iloc[-1]
            fut_date = pd.to_datetime(last_row['date']).strftime('%Y-%m-%d')
            
            # Ensure dates match (or close enough for intraday check)
            if fut_date != spot_date:
                # Mismatch (maybe one updated, one not?)
                # Skip if not same day
                continue
                
            fut_close = float(last_row['close'])
            basis = fut_close - spot_price
            
            # Upsert
            c.execute('''
                INSERT OR REPLACE INTO futures_daily (symbol, date, open, high, low, close, volume, hold, spot_close, basis)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                symbol, fut_date,
                last_row['open'], last_row['high'], last_row['low'], fut_close,
                last_row['volume'], last_row['hold'],
                spot_price, basis
            ))
            
            print(f"✅ Updated {symbol} ({fut_date}): Basis {basis:.2f}")
            
        except Exception as e:
            print(f"❌ Failed to update {symbol}: {e}")
            
    conn.commit()
    conn.close()

def plot_seasonality(symbol):
    """
    Plot seasonality for a specific contract (e.g. IF2609)
    using history of same-month contracts (IF1909, IF2009...)
    """
    prod = symbol[:2]
    month = symbol[-2:] # '09'
    year_short = symbol[2:4] # '26'
    current_year_full = 2000 + int(year_short)
    
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Fetch History
    # We want all contracts ending with 'month' for this product
    query = f"SELECT symbol, date, basis FROM futures_daily WHERE symbol LIKE '{prod}%{month}' ORDER BY date"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty: return

    # Group by Year (Contract)
    # Symbol format: IF1909 -> Year 2019
    df['contract_year'] = df['symbol'].apply(lambda x: int("20" + x[2:4]))
    
    # Align Data
    # Align by "Trading Days from Listing"
    aligned_data = {} # Key: Year, Val: List of basis
    
    for yr, group in df.groupby('contract_year'):
        basis_vals = group['basis'].tolist()
        aligned_data[yr] = basis_vals

    # Plot
    plt.figure(figsize=(10, 6))
    plt.title(f"{symbol} Basis Seasonality vs History ({month} Contracts)")
    plt.xlabel("Trading Days Since Listing")
    plt.ylabel("Basis Points")
    plt.grid(True, alpha=0.3)
    
    # Calculate Range (excluding current)
    history_matrix = []
    for yr, vals in aligned_data.items():
        if yr != current_year_full:
            plt.plot(range(1, len(vals)+1), vals, color='gray', alpha=0.2)
            history_matrix.append(vals)
            
    # Draw Range
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
        
        plt.fill_between(range(1, len(min_curve)+1), min_curve, max_curve, color='skyblue', alpha=0.3, label='Historical Range')
        
    # Draw Current
    if current_year_full in aligned_data:
        vals = aligned_data[current_year_full]
        days = range(1, len(vals)+1)
        plt.plot(days, vals, color='red', linewidth=2, label=f'{symbol} (Current)')
        # Label last point
        plt.scatter(days[-1], vals[-1], color='red', s=40)
        plt.text(days[-1]+2, vals[-1], f"{vals[-1]:.2f}", color='red')

    plt.legend()
    
    # Save
    save_path = os.path.join(OUTPUT_DIR, f"basis_{symbol}.png")
    plt.savefig(save_path)
    plt.close()
    print(f"📈 Chart saved: {save_path}")

if __name__ == "__main__":
    # 1. Update Data
    # active = get_current_contracts() # Fetch real active contracts
    # For demo, let's assume specific list or fetch real
    active = ['IF2602', 'IF2603', 'IF2606', 'IF2609'] # Example
    # In real run: active = get_current_contracts()
    
    # update_db(active)
    
    # 2. Plot for each active contract
    for s in active:
        plot_seasonality(s)
