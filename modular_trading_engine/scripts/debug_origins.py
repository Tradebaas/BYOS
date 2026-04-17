import sys
from pathlib import Path
from datetime import timedelta

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.layer1_data.csv_parser import load_historical_1m_data
from src.layer2_theory.market_state import MarketTheoryState

candles = load_historical_1m_data(project_root / 'data/historical/NQ_1min.csv')
latest_time = candles[-1].timestamp
cutoff_time = latest_time - timedelta(days=28)
small_candles = [c for c in candles if c.timestamp >= cutoff_time]

theory_state = MarketTheoryState()

for candle in small_candles:
    theory_state.process_candle(candle)
    
print("--- ORIGIN LEVELS ---")
for ot in theory_state.origin_trackers:
    dir = "LONG" if ot.level_data.is_bullish else "SHORT"
    print(f"[{dir}] Created: {ot.level_data.timestamp} | Tests: {ot.test_count} | Active: {ot.is_active}")
