import sqlite3
import akshare as ak
import pandas as pd
import os
from datetime import datetime

# DB Path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cffex_basis.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Create Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS futures_daily (
            symbol TEXT,
            date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            hold INTEGER,
            spot_close REAL,
            basis REAL,
            PRIMARY KEY (symbol, date)
        )
    ''')
    conn.commit()
    conn.close()
    print(f"✅ Database initialized at {DB_PATH}")

def save_to_db(df, symbol):
    if df.empty: return
    conn = sqlite3.connect(DB_PATH)
    # Use pandas to insert/replace
    # Ensure columns match
    # Calculate Basis first if spot_close exists
    # But here we might just save raw futures data and compute basis later?
    # Better: Save raw futures data. Spot data in separate table?
    # For simplicity: Keep spot data separate or merge on fly.
    # Let's keep a separate spot table.
    
    # Futures Table
    df['symbol'] = symbol
    df.to_sql('futures_daily', conn, if_exists='append', index=False, method='multi') # 'append' might fail on PK constraint
    # Better: Use REPLACE or custom insert
    # Pandas to_sql doesn't support UPSERT easily.
    # Let's iterate and execute SQL.
    cursor = conn.cursor()
    for _, row in df.iterrows():
        cursor.execute('''
            INSERT OR REPLACE INTO futures_daily (symbol, date, open, high, low, close, volume, hold, spot_close, basis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            symbol, 
            row['date'].strftime('%Y-%m-%d'), 
            row['open'], row['high'], row['low'], row['close'], 
            row['volume'], row['hold'], 
            row.get('spot_close', None), # Spot might be added later
            row.get('basis', None)
        ))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    init_db()
