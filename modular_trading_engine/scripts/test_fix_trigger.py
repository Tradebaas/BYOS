import sys, os
sys.path.append(os.getcwd())
from src.layer1_data.csv_parser import load_historical_1m_data
candles = load_historical_1m_data('data/historical/NQ_1min.csv')

def find_blocks(history, start_idx, is_bullish):
    blocks = []
    end_idx = len(history)
    for i in range(start_idx, end_idx - 2):
        c1 = history[i]
        c1_bull = c1.is_bullish
        c1_bear = c1.is_bearish
        if not is_bullish:
            if not c1_bull: continue
            c2 = history[i+1]
            if not c2.is_bearish: continue
            hard_close_idx = -1
            for j in range(i+2, min(i+15, end_idx)):
                cj = history[j]
                if cj.open < c1.low and cj.close < c1.low:
                    hard_close_idx = j
                    break
                if cj.high >= c2.high:
                    break
            if hard_close_idx != -1:
                blocks.append({'type': 'short','hold': c1.open,'break': c2.high,'c1_idx': i,'hc_idx': hard_close_idx})
    return blocks

history = candles[-1000:]
is_bullish = False
blocks = find_blocks(history, 0, is_bullish)

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
    
    # Track if we successfully processed a validation block this iteration
    validation_ready = False
    
    if active_block_1 and test_idx == -1:
        was_invalidated = False
        found_test = -1
        for k in range(b1_hc + 1, curr_c1 + 1):
            ck = history[k]
            if not is_bullish:
                if ck.high >= active_block_1['break']:
                    was_invalidated = True
                    break
                if ck.is_bullish and ck.close > active_block_1['hold']:
                    was_invalidated = True
                    break
                if ck.high >= active_block_1['hold'] and k > locked_until_idx:
                    found_test = k
        if was_invalidated:
            active_block_1 = b
            continue
            
        if found_test != -1:
            test_idx = found_test
            active_block_2 = b
            validation_ready = True
        else:
            active_block_1 = b
            
    elif active_block_1 and test_idx != -1:
        was_invalidated = False
        for k in range(active_block_2['hc_idx'] + 1, b['c1_idx'] + 1):
            ck = history[k]
            if not is_bullish:
                if ck.high >= active_block_1['break']:
                    was_invalidated = True
                    break
                if ck.is_bullish and ck.close > active_block_1['hold']:
                    was_invalidated = True
                    break
        if was_invalidated:
            active_block_1 = b
            test_idx = -1
            active_block_2 = None
            continue
            
        active_block_2 = b 
        validation_ready = True
        
    # Evaluate Validation Execution 
    if validation_ready:
        hc2 = active_block_2['hc_idx']
        if hc2 > locked_until_idx:
            # IT'S VALID! Lock it in.
            print(f"[{history[-1].timestamp.strftime('%H:%M')}] TRIGGERED: Trap={active_block_1['hold']} Test={history[test_idx].timestamp.strftime('%H:%M')} Validation={active_block_2['hold']} (HC={history[hc2].timestamp.strftime('%H:%M')})")
            locked_until_idx = hc2 + 30 # fake lock for print
            latest_valid_setup = active_block_2
            active_block_1 = None
            active_block_2 = None
            test_idx = -1

