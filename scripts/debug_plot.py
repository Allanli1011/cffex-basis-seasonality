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
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def plot_seasonality(symbol):
    prod = symbol[:2]
    month = symbol[-2:] 
    
    print(f"\n📊 Plotting {symbol} (History: {month} contracts)...")
    
    conn = sqlite3.connect(DB_PATH)
    # Use wildcards correctly
    query = f"SELECT symbol, date, basis FROM futures_daily WHERE symbol LIKE '{prod}%{month}' ORDER BY date"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        print(f"❌ No history found in DB for {symbol}")
        return

    # Extract Year from Symbol (e.g. IH1903 -> 2019)
    # Assumes format: XXYYMM (2 letters + 2 digit year + 2 digit month)
    try:
        df['contract_year'] = df['symbol'].apply(lambda x: int("20" + x[2:4]))
    except:
        print("❌ Symbol format error")
        return

    current_yr = int("20" + symbol[2:4])
    years = df['contract_year'].unique()
    print(f"✅ Found history years: {years}")
    
    aligned_data = {} 
    for yr, group in df.groupby('contract_year'):
        # Sort by date just in case
        group = group.sort_values('date')
        basis_vals = group['basis'].tolist()
        aligned_data[yr] = basis_vals
        # print(f"  - {yr}: {len(basis_vals)} days")

    plt.figure(figsize=(12, 6))
    plt.title(f"{symbol} Basis Seasonality vs History ({month} Contracts)", fontsize=14)
    plt.xlabel("Trading Days Since Listing", fontsize=12)
    plt.ylabel("Basis Points", fontsize=12)
    plt.grid(True, alpha=0.3, linestyle='--')
    
    history_matrix = []
    
    # Plot history lines (grey)
    for yr, vals in aligned_data.items():
        if yr != current_yr:
            plt.plot(range(1, len(vals)+1), vals, color='gray', alpha=0.3, linewidth=1)
            history_matrix.append(vals)
            
    # Plot range (blue)
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
        
    # Plot current (red)
    if current_yr in aligned_data:
        vals = aligned_data[current_yr]
        if len(vals) > 0:
            days = range(1, len(vals)+1)
            plt.plot(days, vals, color='red', linewidth=2.5, label=f'{symbol} (Current)')
            # Mark latest
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

if __name__ == "__main__":
    # Test IH2603 specifically
    test_symbol = 'IH2603'
    plot_seasonality(test_symbol)
