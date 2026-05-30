import akshare as ak
import pandas as pd

print("Fetching historical futures data...")

# Test grabbing an expired contract (e.g. IF2009)
try:
    # Attempt 1: futures_zh_daily_sina (symbol usually like 'IF2009')
    contract = "IF2009"
    df = ak.futures_zh_daily_sina(symbol=contract)
    print(f"\nContract: {contract}")
    if not df.empty:
        print(f"✅ Success! Rows: {len(df)}")
        print(df.head(2))
        print(df.tail(2))
    else:
        print(f"❌ Empty data for {contract}")

except Exception as e:
    print(f"Error fetching {contract}: {e}")

# Also check spot index history (sh000300)
try:
    print("\nChecking spot history...")
    df_spot = ak.stock_zh_index_daily(symbol="sh000300")
    if not df_spot.empty:
        print(f"✅ Spot Data Found. Rows: {len(df_spot)}")
        # Check if it covers 2020
        df_2020 = df_spot[df_spot['date'].astype(str).str.contains('2020')]
        print(f"2020 Spot Data Count: {len(df_2020)}")
    else:
        print("❌ Spot data empty")

except Exception as e:
    print(f"Error fetching spot: {e}")
