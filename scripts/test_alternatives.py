import akshare as ak
import pandas as pd

# Test EastMoney interface for old contracts
def test_em_interface(symbol):
    print(f"Testing EM for {symbol}...")
    try:
        # standard symbol mapping for EM might differ
        # Usually it's code without exchange suffix? Or with CFFEX?
        # Try a few variations
        
        # 1. Direct symbol
        df = ak.futures_zh_daily_sina(symbol=symbol) # We know this failed
        
        # 2. Try EM specific function if exists
        # ak.futures_zh_daily_em does not exist directly?
        # Check docs or dir(ak)
        pass
    except:
        pass

# Let's inspect available functions for historical futures
print("Searching for alternative historical data functions...")
print([x for x in dir(ak) if 'futures' in x and 'daily' in x])

# Also try 'get_cffex_daily' for specific date in 2015 to see if CFFEX official source works
print("\nTesting CFFEX Official Source for 2015-09-01...")
try:
    df_2015 = ak.get_cffex_daily(date="20150901")
    if not df_2015.empty:
        print("✅ CFFEX Official Source works for 2015!")
        print(df_2015.head(2))
    else:
        print("❌ CFFEX Official Source empty for 2015")
except Exception as e:
    print(f"Error: {e}")
