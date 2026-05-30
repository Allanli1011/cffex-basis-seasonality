import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from datetime import datetime
import os

# Configuration
PRODUCT = 'IF' # IF/IH/IC/IM
MONTH = '09'   # Target Contract Month
START_YEAR = 2010 # IF started in 2010
CURRENT_YEAR = 2026 # Current year (red line)

SPOT_SYMBOL = {
    'IF': 'sh000300',
    'IH': 'sh000016',
    'IC': 'sh000905',
    'IM': 'sh000852'
}

def fetch_contract_data(product, year, month):
    """
    Fetch daily bars for a specific contract (e.g. IF2009)
    """
    yr_short = str(year)[-2:] # '20'
    symbol = f"{product}{yr_short}{month}"
    
    print(f"Fetching {symbol}...")
    try:
        # Try primary symbol format
        df = ak.futures_zh_daily_sina(symbol=symbol)
        
        # If empty, try alternative? (Sina usually consistent for main contracts)
        if df.empty:
            print(f"⚠️ Empty data for {symbol}")
            return None, symbol
            
        return df, symbol
    except Exception as e:
        print(f"❌ Error fetching {symbol}: {e}")
        return None, symbol

def fetch_spot_data(symbol):
    """
    Fetch full history of spot index
    """
    print(f"Fetching Spot {symbol}...")
    try:
        df = ak.stock_zh_index_daily(symbol=symbol)
        if not df.empty:
            # Standardize date column to datetime
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date']).dt.normalize()
            else:
                # Some interfaces return index as date
                df.index = pd.to_datetime(df.index).normalize()
                df['date'] = df.index
            return df
    except Exception as e:
        print(f"❌ Error fetching spot {symbol}: {e}")
    return pd.DataFrame()

def analyze_basis_seasonality():
    # 1. Get Spot Data
    product_key = 'IF' # Hardcoded for now, can be param
    spot_sym = 'sh000300' # Default IF
    
    df_spot = fetch_spot_data(spot_sym)
    if df_spot.empty:
        print("❌ Spot data missing, aborting.")
        return

    all_basis_series = {} # Key: Year, Value: Series of Basis Rate
    history_matrix = []   # List of lists (basis values) for range calculation
    
    # 2. Loop Years
    for year in range(START_YEAR, CURRENT_YEAR + 1):
        df_fut, contract_name = fetch_contract_data(PRODUCT, year, MONTH)
        
        if df_fut is None or df_fut.empty:
            continue
            
        # Process Futures Data
        # Sina futures daily returns 'date' as string usually "YYYY-MM-DD"
        df_fut['date'] = pd.to_datetime(df_fut['date']).dt.normalize()
        
        # Rename close to avoid conflict
        df_fut = df_fut[['date', 'close']].rename(columns={'close': 'close_fut'})
        
        # Merge with Spot (inner join to align trading days)
        # Spot df needs 'date' and 'close'
        spot_subset = df_spot[['date', 'close']].rename(columns={'close': 'close_spot'})
        
        df_merged = pd.merge(df_fut, spot_subset, on='date', how='inner')
        
        if df_merged.empty:
            print(f"⚠️ No overlapping dates for {contract_name}")
            continue
            
        # Calculate Basis Points (Absolute Value)
        # Future - Spot
        df_merged['basis_points'] = df_merged['close_fut'] - df_merged['close_spot']
        
        basis_values = df_merged['basis_points'].tolist()
        all_basis_series[year] = basis_values
        
        if year != CURRENT_YEAR:
            history_matrix.append(basis_values)
            print(f"✅ Loaded history: {contract_name} ({len(basis_values)} days)")
        else:
            print(f"🔴 Loaded current: {contract_name} ({len(basis_values)} days)")

    # 3. Plotting
    if not all_basis_series:
        print("❌ No data to plot.")
        return

    plt.figure(figsize=(14, 7))
    plt.title(f"{PRODUCT} Futures - {MONTH} Contract Basis Seasonality ({START_YEAR}-{CURRENT_YEAR})", fontsize=14)
    plt.xlabel("Trading Days Since Listing", fontsize=12)
    plt.ylabel("Basis Points (Points)", fontsize=12)
    plt.grid(True, alpha=0.3, linestyle='--')
    
    # Prepare Range (Blue Shadow)
    # Align all history series to max length
    if history_matrix:
        max_len = max([len(x) for x in history_matrix])
        min_curve = []
        max_curve = []
        
        for i in range(max_len):
            day_vals = []
            for series in history_matrix:
                if i < len(series):
                    day_vals.append(series[i])
            
            if day_vals:
                min_curve.append(np.min(day_vals))
                max_curve.append(np.max(day_vals))
            else:
                min_curve.append(np.nan)
                max_curve.append(np.nan)
                
        # Plot Range
        days_hist = range(1, len(min_curve) + 1)
        plt.fill_between(days_hist, min_curve, max_curve, color='skyblue', alpha=0.3, label='Historical Range (Min-Max)')
    
    # Plot Historical Lines (Grey)
    for year, values in all_basis_series.items():
        days = range(1, len(values) + 1)
        if year != CURRENT_YEAR:
            plt.plot(days, values, color='gray', alpha=0.3, linewidth=1)
    
    # Plot Current Year (Red)
    if CURRENT_YEAR in all_basis_series:
        values = all_basis_series[CURRENT_YEAR]
        days = range(1, len(values) + 1)
        plt.plot(days, values, color='red', linewidth=2.5, label=f'{PRODUCT}{str(CURRENT_YEAR)[-2:]}{MONTH} (Current)')
        
        # Mark latest point
        plt.scatter(days[-1], values[-1], color='red', s=50, zorder=5)
        plt.text(days[-1]+2, values[-1], f"{values[-1]:.2f}", color='red', fontsize=10, va='center')

    plt.legend(loc='upper right')
    plt.tight_layout()
    
    # Save Plot
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
    os.makedirs(output_dir, exist_ok=True)
    save_path = os.path.join(output_dir, f"{PRODUCT}_basis_seasonality_month{MONTH}.png")
    plt.savefig(save_path, dpi=300)
    print(f"✅ Chart saved to: {save_path}")

if __name__ == "__main__":
    analyze_basis_seasonality()
