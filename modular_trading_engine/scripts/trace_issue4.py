import sys, os
sys.path.append(os.getcwd())
from src.layer1_data.csv_parser import load_historical_1m_data
from src.layer2_theory.market_state import MarketTheoryState

candles = load_historical_1m_data('data/historical/NQ_1min.csv')
theory_state = MarketTheoryState()

for i, c in enumerate(candles):
    theory_state.process_candle(c)
    if c.timestamp.strftime('%H:%M') == '17:35' and c.timestamp.strftime('%Y-%m-%d') == '2026-04-13':
        print(f"Time: {c.timestamp}")
        for ot in theory_state.origin_trackers:
            print(f"Tracker: {ot.level_data.timestamp} {ot.level_data.level_type} Bullish:{ot.level_data.is_bullish} Active:{ot.is_active} Tests:{ot.test_count} Break:{ot.level_data.price_high}")
        break
