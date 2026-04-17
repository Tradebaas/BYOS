import sys, os
from datetime import datetime, timezone
sys.path.append(os.getcwd())
from src.layer1_data.csv_parser import load_historical_1m_data
from src.layer2_theory.market_state import MarketTheoryState
from src.layer3_strategy.rule_engine import RuleEngine
from src.layer3_strategy.config_parser import ConfigParser
from src.layer3_strategy.pipeline_context import PipelineContext
from src.layer3_strategy.modules.confirmation_hold_level_trigger import ConfirmationHoldLevelTrigger

class SuperDebugTrigger(ConfirmationHoldLevelTrigger):
    def process_direction(self, context, is_bullish):
        if not is_bullish: return
        history = context.theory_state.history
        bias_window_size = self.params.get('bias_window_size', 200)
        current_idx = len(history) - 1
        blocks = self.find_blocks(history, max(0, current_idx - bias_window_size), is_bullish)
        
        active_block_1 = None
        test_idx = -1
        active_block_2 = None
        locked_until_idx = -1
        latest_valid_setup = None
        
        for b in blocks:
            if not active_block_1:
                active_block_1 = b
                continue
                
            b1_hc = active_block_1['hc_idx']
            curr_c1 = b['c1_idx']
            validation_ready = False
            
            if active_block_1 and test_idx == -1:
                was_invalidated = False
                found_test = -1
                for k in range(b1_hc + 1, curr_c1 + 1):
                    ck = history[k]
                    if is_bullish:
                        if ck.is_bearish and ck.open < active_block_1['hold'] and ck.close < active_block_1['hold']:
                            was_invalidated = True
                            print(f"[{history[current_idx].timestamp}] Inval Loop 1: {ck.timestamp}")
                            break
                        if ck.low <= active_block_1['hold'] and k > locked_until_idx:
                            found_test = k
                if was_invalidated:
                    active_block_1 = b
                    continue
                if found_test != -1:
                    test_idx = found_test
                    active_block_2 = b 
                    validation_ready = True
                    print(f"[{history[current_idx].timestamp}] Found Test! {history[test_idx].timestamp}")
                else:
                    active_block_1 = b
                    
            elif active_block_1 and test_idx != -1:
                was_invalidated = False
                for k in range(active_block_2['hc_idx'] + 1, b['c1_idx'] + 1):
                    ck = history[k]
                    if is_bullish:
                        if ck.is_bearish and ck.open < active_block_1['hold'] and ck.close < active_block_1['hold']:
                            was_invalidated = True
                            break
                if was_invalidated:
                    active_block_1 = b
                    test_idx = -1
                    active_block_2 = None
                    continue    
                active_block_2 = b 
                validation_ready = True
                print(f"[{history[current_idx].timestamp}] Validated B2! {history[b['c1_idx']].timestamp}")
                
            if validation_ready:
                hc2 = active_block_2['hc_idx']
                if hc2 > locked_until_idx:
                    entry = active_block_2['hold']
                    eval_candles = history[max(0, hc2 - 200):hc2+1]
                    midpoint = (max(ck.high for ck in eval_candles) + min(ck.low for ck in eval_candles)) / 2
                    is_valid_zone = (entry <= midpoint)
                    print(f"[{history[current_idx].timestamp}] Zone check: {is_valid_zone}")
                    if is_valid_zone:
                        entry += 1.0
                        sl = entry - 15.0
                        tp = entry + 30.0
                        locked_until_idx = self.simulate_trade_lock(history, hc2 + 1, entry, sl, tp, is_bullish, 30)
                        active_block_2['frontrun_entry'] = entry
                        latest_valid_setup = active_block_2
                        print(f"[{history[current_idx].timestamp}] Locked until: {locked_until_idx} (curr: {current_idx})")
                    active_block_1, active_block_2, test_idx = None, None, -1

        if latest_valid_setup:
            print(f"[{history[current_idx].timestamp}] FINAL check: {locked_until_idx} >= {current_idx}")
            if locked_until_idx >= current_idx:
                context.setup_candidates.append(latest_valid_setup)

candles = load_historical_1m_data('data/historical/NQ_1min.csv')
theory_state = MarketTheoryState()
trigger = SuperDebugTrigger({'bias_window_size': 200})

for i, c in enumerate(candles):
    theory_state.process_candle(c)
    if '19:00' <= c.timestamp.strftime('%H:%M') <= '19:00' and c.timestamp.strftime('%Y-%m-%d') == '2026-04-16':
        context = PipelineContext(theory_state=theory_state, timestamp=c.timestamp)
        trigger.process(context)
        print(f"Final setup candidates: {len(context.setup_candidates)}")
