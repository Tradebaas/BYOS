import sys, os
sys.path.append(os.path.abspath('.'))
from modular_trading_engine.src.layer1_data.csv_parser import load_historical_1m_data
candles = load_historical_1m_data('modular_trading_engine/data/historical/NQ_1min.csv')

target_ts = "2024-03-01 05:34"

for i in range(500, len(candles)):
    ts_str = str(candles[i].timestamp)
    if target_ts in ts_str:
        window = candles[i-500:i]
        eq = (max(c.high for c in window) + min(c.low for c in window)) / 2
        close_val = candles[i-1].close
        print("At", ts_str)
        print("Max:", max(c.high for c in window))
        print("Min:", min(c.low for c in window))
        print("EQ:", eq)
        print("Close:", close_val)
        print("PD:", "PREMIUM" if close_val >= eq else "DISCOUNT")
        break
