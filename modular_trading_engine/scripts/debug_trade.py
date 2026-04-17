import os
import sys

os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.append(os.getcwd())

from modular_trading_engine.src.layer1_data.csv_parser import load_historical_1m_data
candles = load_historical_1m_data('modular_trading_engine/data/historical/NQ_1min.csv')

def get_pd(idx):
    if idx < 500:
        return None, 0.0, 0.0, 0.0
    window = candles[idx-500:idx]
    max_h = max(c.high for c in window)
    min_l = min(c.low for c in window)
    eq = (max_h + min_l) / 2
    
    current_close = candles[idx-1].close
    bias = "PREMIUM" if current_close >= eq else "DISCOUNT"
    return bias, eq, max_h, min_l

for i in range(len(candles) - 1000, len(candles)):
    c = candles[i]
    ts_str = str(c.timestamp)
    if "05:34:00" in ts_str and "2026-04-13" in ts_str:
        bias, eq, max_h, min_l = get_pd(i)
        print("====== 05:34 Analysis ======")
        print(f"Time: {ts_str}")
        print(f"Candle Info: High={c.high}, Low={c.low}, Close={c.close}")
        print(f"500-bar Window: Max={max_h}, Min={min_l}, EQ={eq}")
        print(f"Bias calculated: {bias}")
        print("====== ================ ======")
        break
