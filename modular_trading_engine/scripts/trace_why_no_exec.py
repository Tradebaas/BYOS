import sys, os
from datetime import datetime, timezone
sys.path.append(os.getcwd())
from src.layer1_data.csv_parser import load_historical_1m_data
from src.layer3_strategy.modules.confirmation_hold_level_trigger import ConfirmationHoldLevelTrigger

candles = load_historical_1m_data('data/historical/NQ_1min.csv')
target_time = datetime(2026, 4, 16, 19, 5, tzinfo=timezone.utc)
history = [c for c in candles if c.timestamp <= target_time]

trigger = ConfirmationHoldLevelTrigger({'bias_window_size': 200, 'ttl_candles': 30, 'sl_points': 15, 'tp_points': 30})
blocks = trigger.find_blocks(history, max(0, len(history)-200), True)

active_block_1 = None
active_block_2 = None
test_idx = -1

for b in blocks:
    b1_hc = active_block_1['hc_idx'] if active_block_1 else 0
    if active_block_1 and test_idx == -1:
        found_test = -1
        # we only care about LONG here for the 18:34/18:57 setup!
        for k in range(b1_hc + 1, b['c1_idx']):
            ck = history[k]
            if ck.low <= active_block_1['hold']: found_test = k
        if found_test != -1:
            test_idx = found_test
            active_block_2 = b 
    elif active_block_1 and test_idx != -1:
        was_invalidated = False
        for k in range(active_block_2['hc_idx'] + 1, b['c1_idx'] + 1):
            ck = history[k]
            if ck.is_bearish and ck.open < active_block_1['hold'] and ck.close < active_block_1['hold']:
                was_invalidated = True
        
        if not was_invalidated:
            active_block_2 = b
            hc2 = active_block_2['hc_idx']
            if '18:55' <= history[hc2].timestamp.strftime('%H:%M') <= '19:05':
                print(f"Valid sequence at {history[hc2].timestamp}! B1_C1: {history[active_block_1['c1_idx']].timestamp}, Test: {history[test_idx].timestamp}, B2_HC: {history[hc2].timestamp}")
        
        active_block_1, active_block_2, test_idx = None, None, -1
    else:
        active_block_1 = b

