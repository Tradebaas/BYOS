import sys, os
from datetime import datetime, timezone
sys.path.append(os.getcwd())
from src.layer1_data.csv_parser import load_historical_1m_data
from src.layer3_strategy.modules.confirmation_hold_level_trigger import ConfirmationHoldLevelTrigger

candles = load_historical_1m_data('data/historical/NQ_1min.csv')
target_time = datetime(2026, 4, 16, 19, 5, tzinfo=timezone.utc)
history = [c for c in candles if c.timestamp <= target_time]

trigger = ConfirmationHoldLevelTrigger({'bias_window_size': 200})
start_idx = max(0, len(history) - 200)

print("--- SHORT ---")
s_intents = trigger.evaluate_short(None, history, start_idx, len(history)-1)
    
print("--- LONG ---")
l_intents = trigger.evaluate_long(None, history, start_idx, len(history)-1)

