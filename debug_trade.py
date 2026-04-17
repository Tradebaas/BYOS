import sys, os
sys.path.append(os.path.abspath('.'))
from modular_trading_engine.src.layer1_data.csv_parser import load_historical_1m_data
candles = load_historical_1m_data('modular_trading_engine/data/historical/NQ_1min.csv')

for i in range(len(candles)):
    if "2026-04-13 05:43:00" in str(candles[i].timestamp):
        print(f"Candle index: {i}")
        # manual inspect around index 90840 or so
        
        c = candles[i]
        get_pd = lambda c_idx: (max(x.high for x in candles[c_idx-500:c_idx]) + min(x.low for x in candles[c_idx-500:c_idx])) / 2
        
        eq = get_pd(i)
        print(f"Eq: {eq}, Close prev: {candles[i-1].close}")
        if candles[i-1].close >= eq:
            print("PREMIUM at 05:43")
        else:
            print("DISCOUNT at 05:43")
