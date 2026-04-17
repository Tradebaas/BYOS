import sys
import os

sys.path.append(os.path.abspath('.'))
from modular_trading_engine.src.layer1_data.csv_parser import load_historical_1m_data

candles = load_historical_1m_data('modular_trading_engine/data/historical/NQ_1min.csv')

def get_pd(c_idx, c_list):
    window = c_list[c_idx-500:c_idx]
    max_h = max(c.high for c in window)
    min_l = min(c.low for c in window)
    eq = (max_h + min_l) / 2
    return eq, max_h, min_l

for i, c in enumerate(candles):
    if "05:43:00+00:00" in str(c.timestamp) and "2026-04-13" in str(c.timestamp):
        eq, max_h, min_l = get_pd(i, candles)
        print(f"Time: {c.timestamp}")
        print(f"Close: {candles[i-1].close}")
        print(f"Max High (last 500): {max_h}")
        print(f"Min Low (last 500): {min_l}")
        print(f"Equilibrium: {eq}")
        print(f"PD Status: {'PREMIUM' if candles[i-1].close >= eq else 'DISCOUNT'}")
