import sys, os
sys.path.append(os.getcwd())
from src.layer1_data.csv_parser import load_historical_1m_data
from src.layer2_theory.market_state import MarketTheoryState
from src.layer3_strategy.pipeline_context import PipelineContext
from src.layer3_strategy.modules.confirmation_hold_level_trigger import ConfirmationHoldLevelTrigger

candles = load_historical_1m_data('data/historical/NQ_1min.csv')

history = candles[-1000:]
trigger = ConfirmationHoldLevelTrigger(params={})

blocks = trigger.find_blocks(history, 0, False)

active_block_1 = None
test_idx = -1
active_block_2 = None

for b in blocks:
    if not active_block_1:
        active_block_1 = b
        print(f"Set b1 to {b['hold']} (C1 {history[b['c1_idx']].timestamp.strftime('%H:%M')})")
        continue
        
    hc_b1 = history[active_block_1['hc_idx']].timestamp.strftime('%H:%M')
    c1_b = history[b['c1_idx']].timestamp.strftime('%H:%M')
    
    if active_block_1 and test_idx == -1:
        b1_hc = active_block_1['hc_idx']
        curr_c1 = b['c1_idx']
        
        was_invalidated = False
        found_test = -1
        
        for k in range(b1_hc + 1, curr_c1 + 1):
            ck = history[k]
            if ck.high >= active_block_1['break']:
                was_invalidated = True
                break
            if ck.high >= active_block_1['hold']:
                found_test = k
                
        if was_invalidated:
            print(f"Invalidated! Setting b1 to {b['hold']} {c1_b}")
            active_block_1 = b
            continue
            
        if found_test != -1:
            print(f"Test found at {history[found_test].timestamp.strftime('%H:%M')}. Set b2 to {b['hold']} {c1_b}")
            test_idx = found_test
            active_block_2 = b 
        else:
            print(f"No test. Setting b1 to {b['hold']} {c1_b}")
            active_block_1 = b 
            
    elif active_block_1 and test_idx != -1:
        was_invalidated = False
        for k in range(active_block_2['hc_idx'] + 1, b['c1_idx'] + 1):
            ck = history[k]
            if ck.high >= active_block_1['break']:
                was_invalidated = True
                break
        if was_invalidated:
            print(f"Invalidated while tested! Setting b1 to {b['hold']} {c1_b}")
            active_block_1 = b
            test_idx = -1
            active_block_2 = None
            continue
            
        print(f"Updating b2 to {b['hold']} {c1_b}")
        active_block_2 = b

print(f"Final b1={active_block_1['hold'] if active_block_1 else None}")
print(f"Final test={history[test_idx].timestamp.strftime('%H:%M') if test_idx != -1 else None}")
print(f"Final b2={active_block_2['hold'] if active_block_2 else None}")
