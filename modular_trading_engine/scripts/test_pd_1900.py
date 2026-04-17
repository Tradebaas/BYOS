import asyncio
from datetime import datetime
import pandas as pd
import sys
import os

# Ensure proper path
sys.path.append('.')
from modular_trading_engine.src.layer2_theory.market_state import MarketTheoryState
from modular_trading_engine.src.layer1_data.csv_parser import parse_historical_data_to_theory_state

async def run():
    # We load the existing DB since we synced it perfectly earlier as seen in logs
    db_file = "modular_trading_engine/data/historical/NQ_1min.csv"
    state = parse_historical_data_to_theory_state(db_file, max_candles=90000)
    
    # We are looking for time around 19:02 UTC
    target_idx = -1
    for i, c in enumerate(state.history):
        dt = datetime.fromtimestamp(c.timestamp)
        if dt.hour == 19 and dt.minute == 2 and dt.day == 14:
            target_idx = i
            print(f"Found Hard Close candle: {dt} | Close: {c.close}")
            break
            
    if target_idx != -1:
        eval_start = max(0, target_idx - 200)
        eval_candles = state.history[eval_start:target_idx+1]
        range_high = max(ck.high for ck in eval_candles)
        range_low = min(ck.low for ck in eval_candles)
        midpoint = (range_high + range_low) / 2
        entry = 25958.75
        
        print(f"--- PREMIUM DISCOUNT FILTER AT 19:02 UTC ---")
        print(f"200-Candle Range: High={range_high}, Low={range_low}")
        print(f"Midpoint (Equilibrium): {midpoint}")
        print(f"Entry Level: {entry}")
        
        if entry >= midpoint:
            print("Status: PREMIUM (Valid for SHORT)")
        else:
            print("Status: DISCOUNT (INVALID for SHORT)")
            
if __name__ == '__main__':
    asyncio.run(run())
