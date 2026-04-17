import sys, os
sys.path.append(os.getcwd())
from src.layer1_data.csv_parser import load_historical_1m_data
from src.layer2_theory.market_state import MarketTheoryState

candles = load_historical_1m_data('data/historical/NQ_1min.csv')
theory_state = MarketTheoryState()

for c in candles:
    theory_state.process_candle(c)
    if c.timestamp.strftime('%Y-%m-%d') == '2026-04-16' and '18:30' <= c.timestamp.strftime('%H:%M') <= '19:00':
        for idx, tr in enumerate(theory_state.origin_trackers):
            if tr.is_active:
                for t in tr.test_history:
                    if t[0].strftime('%Y-%m-%d') == '2026-04-16' and '18:30' <= t[0].strftime('%H:%M') <= '19:00':
                        print(f"[{c.timestamp}] Tracker {tr.level_data.timestamp} TESTED at {t}")
