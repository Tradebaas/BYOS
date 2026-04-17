import sys, os
sys.path.append(os.path.abspath('.'))
from modular_trading_engine.src.layer1_data.csv_parser import load_historical_1m_data
candles = load_historical_1m_data('modular_trading_engine/data/historical/NQ_1min.csv')

def get_pd(idx, c_list):
    window = c_list[idx-500:idx]
    max_h = max(c.high for c in window)
    min_l = min(c.low for c in window)
    return (max_h + min_l) / 2

for i, c in enumerate(candles):
    ts_str = str(c.timestamp)
    if ts_str.startswith("2026-04-13 05:43:00"):
        eq = get_pd(i, candles)
        print(f"Trigger Hold (05:43): Close={candles[i-1].close:.2f}, Eq={eq:.2f} -> {('PREMIUM' if candles[i-1].close >= eq else 'DISCOUNT')}")
    if ts_str.startswith("2026-04-13 05:52:00"):
        eq = get_pd(i, candles)
        print(f"Limit Execution (05:52): Close={candles[i-1].close:.2f}, Eq={eq:.2f} -> {('PREMIUM' if candles[i-1].close >= eq else 'DISCOUNT')}")
