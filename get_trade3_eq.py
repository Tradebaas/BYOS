import sys, os
sys.path.append(os.path.abspath('.'))
from modular_trading_engine.src.layer1_data.csv_parser import load_historical_1m_data
candles = load_historical_1m_data('modular_trading_engine/data/historical/NQ_1min.csv')

for i in range(500, len(candles)):
    c = candles[i]
    if "05:34:00" in str(c.timestamp):
        window = candles[i-500:i]
        h_max = max(w.high for w in window)
        l_min = min(w.low for w in window)
        eq = (h_max + l_min) / 2
        print(f"Time: {c.timestamp}")
        print(f"500-min Window [ {window[0].timestamp} TO {window[-1].timestamp} ]")
        print(f"Max High: {h_max}")
        print(f"Min Low: {l_min}")
        print(f"Equilibrium: {eq}")
        print(f"Close at triggering candle (-1): {candles[i-1].close}")
        print(f"Close at current candle (0): {c.close}")
        print("PD:", "PREMIUM" if candles[i-1].close >= eq else "DISCOUNT")
        break
