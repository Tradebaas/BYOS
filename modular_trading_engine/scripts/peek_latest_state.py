import sys, os
sys.path.append(os.getcwd())
from src.layer1_data.csv_parser import load_historical_1m_data
from src.layer2_theory.market_state import MarketTheoryState
from src.layer3_strategy.pipeline_context import PipelineContext
from src.layer3_strategy.modules.confirmation_hold_level_trigger import ConfirmationHoldLevelTrigger

candles = load_historical_1m_data('data/historical/NQ_1min.csv')

def peek_current_state(is_bullish):
    trigger = ConfirmationHoldLevelTrigger(params={"ttl_candles": 30, "sl_points": 10.0, "tp_points": 20.0})
    history = candles[-1000:]
    blocks = trigger.find_blocks(history, 0, is_bullish)
    
    active_block_1 = None
    test_idx = -1
    active_block_2 = None
    locked_until_idx = -1
    
    for b in blocks:
        if not active_block_1:
            active_block_1 = b
            continue
            
        b1_hc = active_block_1['hc_idx']
        curr_c1 = b['c1_idx']
        
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
                else:
                    if ck.low <= active_block_1['break']:
                        was_invalidated = True
                        break
                    if ck.is_bearish and ck.close < active_block_1['hold']:
                        was_invalidated = True
                        break
                    if ck.low <= active_block_1['hold'] and k > locked_until_idx:
                        found_test = k
                        
            if was_invalidated:
                active_block_1 = b
                continue
                
            if found_test != -1:
                test_idx = found_test
                active_block_2 = b 
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
                else:
                    if ck.low <= active_block_1['break']:
                        was_invalidated = True
                        break
                    if ck.is_bearish and ck.close < active_block_1['hold']:
                        was_invalidated = True
                        break
            if was_invalidated:
                active_block_1 = b
                test_idx = -1
                active_block_2 = None
                continue
                
            active_block_2 = b 
            
            hc2 = active_block_2['hc_idx']
            if hc2 > locked_until_idx:
                entry = active_block_2['hold']
                if not is_bullish:
                    sl = entry + 10.0
                    tp = entry - 20.0
                else:
                    sl = entry - 10.0
                    tp = entry + 20.0
                    
                locked_until_idx = trigger.simulate_trade_lock(history, hc2 + 1, entry, sl, tp, is_bullish, 30)
                active_block_1 = None
                active_block_2 = None
                test_idx = -1
                
    curr_t = history[-1].timestamp.strftime('%H:%M')
    print(f"Current Time: {curr_t} | IsBullish (Searching origin mode): {is_bullish}")
    if locked_until_idx >= len(history) - 1:
        print(f"-> SYSTEM IS LOCKED in a Simulated/Real Trade until at least index {locked_until_idx}")
    else:
        if not active_block_1:
            print("-> Hunting for a fresh Trap (Phase 1). No valid un-tested Trap currently tracked.")
        else:
            t_trap = history[active_block_1['c1_idx']].timestamp.strftime('%H:%M')
            print(f"-> Active Trap (Phase 1): Formed at {t_trap} (Hold: {active_block_1['hold']}, Break: {active_block_1['break']})")
            if test_idx == -1:
                print("-> Waiting for TEST (Phase 2).")
            else:
                t_test = history[test_idx].timestamp.strftime('%H:%M')
                t_conf = history[active_block_2['c1_idx']].timestamp.strftime('%H:%M')
                print(f"-> TEST HAPPENED at {t_test}! Currently tracking intermediate Confirmation block from {t_conf}.")
                print("-> Waiting for Hard Close or better Confirmation block!")

print("--- SHORT SCANNER ---")
peek_current_state(False)
print("--- LONG SCANNER ---")
peek_current_state(True)
