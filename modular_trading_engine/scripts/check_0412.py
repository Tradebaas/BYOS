import sys
from pathlib import Path
from datetime import timedelta

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.layer1_data.csv_parser import load_historical_1m_data
from src.layer2_theory.market_state import MarketTheoryState

candles = load_historical_1m_data(project_root / 'data/historical/NQ_1min.csv')
latest_time = candles[-1].timestamp
cutoff_time = latest_time - timedelta(days=7) # covers last 5 trading days
small_candles = [c for c in candles if c.timestamp >= cutoff_time]

theory_state = MarketTheoryState()

print("Running tracker up to 06:00 on 2026-04-08...")
for idx, candle in enumerate(small_candles):
    ts = candle.timestamp
    # process candle
    theory_state.process_candle(candle)
    
    if ts.year == 2026 and ts.month == 4 and ts.day == 8 and ts.hour >= 6:
        break

print("\n--- Origin Trackers ---")
for ot in theory_state.origin_trackers:
    ts = str(ot.level_data.timestamp)
    if "2026-04-08" in ts:
        print(f"OriginTracker Start: {ts} - Price: {ot.level_data.price_low}/{ot.level_data.price_high} (Bullish: {ot.level_data.is_bullish}, Is Active: {ot.is_active})")

print("\n--- Reverse Trackers (incl Breaks) ---")
for rt in theory_state.reverse_trackers:
    ts = str(rt.level_data.timestamp)
    if "2026-04-08 04:" in ts or "2026-04-08 05:" in ts:
        if "BREAK" in rt.level_data.level_type.name:
            print(f"BreakTracker: {ts} - Price: {rt.level_data.price_low}/{rt.level_data.price_high} (Bullish: {rt.level_data.is_bullish}, Tests: {rt.raw_touches})")
