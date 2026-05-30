import akshare as ak
import pandas as pd

# Debug fetch for IH contracts
contracts = ['IH1903', 'IH2003', 'IH2603']

print("Debugging contract fetch...")

for symbol in contracts:
    print(f"\nTesting {symbol}...")
    try:
        # Try default
        df = ak.futures_zh_daily_sina(symbol=symbol)
        if not df.empty:
            print(f"✅ Success! Rows: {len(df)}")
            print(df.head(2))
        else:
            print(f"❌ Empty result for {symbol}")
            
        # Try alternate symbol format (e.g. IH2603.CFE)
        symbol_alt = f"{symbol}.CFE"
        print(f"Testing {symbol_alt}...")
        df_alt = ak.futures_zh_daily_sina(symbol=symbol_alt)
        if not df_alt.empty:
            print(f"✅ Success (Alt)! Rows: {len(df_alt)}")
        else:
            print(f"❌ Empty result for {symbol_alt}")

    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
