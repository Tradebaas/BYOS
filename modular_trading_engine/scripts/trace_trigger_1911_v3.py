import sys, os
sys.path.append(os.getcwd())
from src.layer1_data.csv_parser import load_historical_1m_data
from src.layer2_theory.market_state import MarketTheoryState
from src.layer3_strategy.pipeline_context import PipelineContext
from src.layer3_strategy.modules.confirmation_hold_level_trigger import ConfirmationHoldLevelTrigger

candles = load_historical_1m_data('data/historical/NQ_1min.csv')
theory_state = MarketTheoryState()
trigger = ConfirmationHoldLevelTrigger(params={})

for i, c in enumerate(candles):
    theory_state.process_candle(c)
    if c.timestamp.strftime('%H:%M') == '19:11' and c.timestamp.strftime('%Y-%m-%d') == '2026-04-13':
        context = PipelineContext(theory_state=theory_state, timestamp=c.timestamp)
        context.active_polarity_is_bullish = False # SHORT
        
        bias_window_size = 200
        history = context.theory_state.history
        current_idx = len(history) - 1
        start_idx = max(0, current_idx - bias_window_size)
        
        blocks = trigger.find_blocks(history, start_idx, False)
        
        active_block_1 = None
        test_idx = -1
        active_block_2 = None
        
        for b in blocks:
             hc = history[b["hc_idx"]].timestamp.strftime('%H:%M')
             c1 = history[b["c1_idx"]].timestamp.strftime('%H:%M')
             print(f"Processing Block: Hold={b['hold']} HC={hc} C1={c1}")
             
             if not active_block_1:
                 active_block_1 = b
                 print(f"  -> Assigned active_block_1 = {b['hold']}")
                 continue
                 
             if active_block_1 and test_idx == -1:
                 b1_hc = active_block_1['hc_idx']
                 curr_c1 = b['c1_idx']
                 was_invalidated = False
                 found_test = -1
                 for k in range(b1_hc + 1, curr_c1 + 1):
                     ck = history[k]
                     if ck.high >= active_block_1['break']:
                         was_invalidated = True
                         print(f"  -> Invalidated at {ck.timestamp.strftime('%H:%M')} (H:{ck.high} >= Brk:{active_block_1['break']})")
                         break
                     if ck.high >= active_block_1['hold']:
                         found_test = k
                         print(f"  -> Found test at {ck.timestamp.strftime('%H:%M')} (H:{ck.high} >= Hold:{active_block_1['hold']})")
                 if was_invalidated:
                     active_block_1 = b
                     print(f"  -> Reset active_block_1 = {b['hold']}")
                     continue
                 if found_test != -1:
                     test_idx = found_test
                     active_block_2 = b
                     print(f"  -> Test acquired! active_block_2 = {b['hold']}")
                 else:
                     active_block_1 = b
                     print(f"  -> No test. Moved active_block_1 = {b['hold']}")
                     
             elif active_block_1 and test_idx != -1:
                 was_invalidated = False
                 for k in range(active_block_2['hc_idx'] + 1, b['c1_idx'] + 1):
                     ck = history[k]
                     if ck.high >= active_block_1['break']:
                         was_invalidated = True
                         print(f"  -> Invalidated while forming B2 at {ck.timestamp.strftime('%H:%M')} (H:{ck.high} >= Brk:{active_block_1['break']})")
                         break
                 if was_invalidated:
                     active_block_1 = b
                     test_idx = -1
                     active_block_2 = None
                     print(f"  -> Reset from B2 state. active_block_1 = {b['hold']}")
                     continue
                 active_block_2 = b
                 print(f"  -> Updated active_block_2 = {b['hold']}")

        print(f"FINAL: B1={active_block_1['hold'] if active_block_1 else None}  Test={test_idx} B2={active_block_2['hold'] if active_block_2 else None}")
        break
