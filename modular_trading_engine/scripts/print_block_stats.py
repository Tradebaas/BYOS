import sys, os
sys.path.append(os.getcwd())
import pandas as pd
from src.layer1_data.csv_parser import load_historical_1m_data

candles = load_historical_1m_data('data/historical/NQ_1min.csv')

def parse_time(ts):
    from datetime import datetime, timezone
    return ts.strftime('%H:%M:%S UTC')

for c in candles[-150:]:
    t = c.timestamp.strftime('%H:%M')
    if "10:30" <= t <= "10:50":
        bull_bear = "🟩" if c.is_bullish else "🟥" if c.is_bearish else "⬜"
        print(f"[{t}] {bull_bear} O:{c.open} H:{c.high} L:{c.low} C:{c.close}")
