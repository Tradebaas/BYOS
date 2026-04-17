import sys, os
from datetime import datetime
sys.path.append(os.getcwd())
from src.layer1_data.csv_parser import load_historical_1m_data
from src.layer2_theory.market_state import MarketTheoryState
from src.layer3_strategy.modules.confirmation_hold_level_trigger import ConfirmationHoldLevelTrigger
from src.layer3_strategy.pipeline_context import PipelineContext

class ExposeTrigger(ConfirmationHoldLevelTrigger):
    def process_direction(self, context, is_bullish):
        super().process_direction(context, is_bullish)
        # Re-fetch from context
        
candles = load_historical_1m_data('data/historical/NQ_1min.csv')
theory_state = MarketTheoryState()
trigger = ConfirmationHoldLevelTrigger({'bias_window_size': 200, 'ttl_candles': 30, 'sl_points': 15, 'tp_points': 30})

for i, c in enumerate(candles):
    theory_state.process_candle(c)
    if '19:00' <= c.timestamp.strftime('%H:%M') <= '19:00' and c.timestamp.strftime('%Y-%m-%d') == '2026-04-16':
        history = theory_state.history
        # mock process_direction to print
        for b_dir in [True, False]:
            blocks = trigger.find_blocks(history, max(0, len(history)-200), b_dir)
            active_block_1, active_block_2, test_idx = None, None, -1
            latest_valid_setup = None
            locked_until_idx = -1
            
            for b in blocks:
                b1_hc = active_block_1['hc_idx'] if active_block_1 else 0
                if active_block_1 and test_idx == -1:
                    found_test = -1
                    for k in range(b1_hc + 1, b['c1_idx']):
                        ck = history[k]
                        if not b_dir and ck.high >= active_block_1['hold'] and k > locked_until_idx: found_test = k
                        elif b_dir and ck.low <= active_block_1['hold'] and k > locked_until_idx: found_test = k
                    if found_test != -1: test_idx = found_test; active_block_2 = b 
                elif active_block_1 and test_idx != -1:
                    was_inval = False
                    for k in range(active_block_2['hc_idx'] + 1, b['c1_idx'] + 1):
                        ck = history[k]
                        if not b_dir and ck.is_bullish and ck.open > active_block_1['hold'] and ck.close > active_block_1['hold']: was_inval = True
                        elif b_dir and ck.is_bearish and ck.open < active_block_1['hold'] and ck.close < active_block_1['hold']: was_inval = True
                    
                    if not was_inval:
                        active_block_2 = b 
                        hc2 = active_block_2['hc_idx']
                        entry = active_block_2['hold']
                        
                        eval_start = max(0, hc2 - 200)
                        midpoint = (max(ck.high for ck in history[eval_start:hc2+1]) + min(ck.low for ck in history[eval_start:hc2+1])) / 2
                        is_valid = (not b_dir and entry >= midpoint) or (b_dir and entry <= midpoint)
                        
                        if is_valid:
                            entry_calc = entry - 1.0 if not b_dir else entry + 1.0
                            sl = entry_calc + 15 if not b_dir else entry_calc - 15
                            tp = entry_calc - 30 if not b_dir else entry_calc + 30
                            
                            locked_until_idx = trigger.simulate_trade_lock(history, hc2 + 1, entry_calc, sl, tp, b_dir, 30)
                            print(f"{'LONG' if b_dir else 'SHORT'} hc2: {hc2}, curr: {len(history)-1}, locked_until: {locked_until_idx}")
                            latest_valid_setup = True
                    active_block_1, active_block_2, test_idx = None, None, -1
                else: active_block_1 = b
