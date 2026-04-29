import pandas as pd
import sys
import os

LAKE_FILE = "data/backtest/candles/NQ_1min.csv"

def verify():
    if not os.path.exists(LAKE_FILE):
        print(f"File {LAKE_FILE} not found!")
        sys.exit(1)

    df = pd.read_csv(LAKE_FILE)
    
    total_rows = len(df)
    
    if total_rows == 0:
        print("Data Lake CSV is empty.")
        return
        
    df['dt'] = pd.to_datetime(df['datetime_utc'])
    df = df.sort_values(by='timestamp_ms')
    
    min_date = df['dt'].min()
    max_date = df['dt'].max()
    
    print("-" * 50)
    print("VERIFICATION: DATA LAKE CSV")
    print("-" * 50)
    print(f"Total Rows:      {total_rows}")
    print(f"Oldest Candle:   {min_date}")
    print(f"Newest Candle:   {max_date}")
    print(f"Timespan (days): {(max_date - min_date).days}")
    
    # Check for gaps > 2 days (weekends)
    df['diff'] = df['dt'].diff()
    large_gaps = df[df['diff'] > pd.Timedelta(days=3)]
    if not large_gaps.empty:
        print(f"⚠️ WARNING: Found {len(large_gaps)} time gaps larger than 3 days. This might just be weekends/holidays, or missing API data.")
    else:
        print("✅ No extreme data gaps found.")
        
    # Check uniqueness
    duplicates = df.duplicated(subset=['timestamp_ms']).sum()
    if duplicates > 0:
        print(f"❌ ERROR: Found {duplicates} duplicate timestamps!")
    else:
        print("✅ No duplicate candles detected.")

if __name__ == "__main__":
    verify()
