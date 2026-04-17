import sys, os
sys.path.append(os.getcwd())
from src.layer1_data.csv_parser import load_historical_1m_data
candles = load_historical_1m_data('data/historical/NQ_1min.csv')
from src.layer3_strategy.modules.confirmation_hold_level_trigger import ConfirmationHoldLevelTrigger

def simulate_trade_lock(history, start_idx, entry, sl, tp, is_bullish):
    # check 30 candles max for fill
    fill_idx = -1
    for k in range(start_idx, min(start_idx + 30, len(history))):
        ck = history[k]
        if not is_bullish:
            if ck.high >= entry:
                fill_idx = k
                break
        else:
            if ck.low <= entry:
                fill_idx = k
                break
    
    if fill_idx == -1:
        # Cancelled after 30 mins
        return start_idx + 30
    
    # Filled! Track until SL or TP
    for k in range(fill_idx, len(history)):
        ck = history[k]
        if not is_bullish: # Short SL is above, TP is below
            if ck.high >= sl or ck.low <= tp:
                return k
        else:
            if ck.low <= sl or ck.high >= tp:
                return k
    
    # Still open at end of history
    return len(history)

# Simulation loop
history = candles[-1000:]
trigger = ConfirmationHoldLevelTrigger(params={})
blocks = trigger.find_blocks(history, 0, False)

locked_until_idx = -1
intents = []

active_block_1 = None
test_idx = -1
active_block_2 = None

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
             if ck.high >= active_block_1['break']:
                 was_invalidated = True
                 break
             # The test can ONLY happen after the lock expires
             if ck.high >= active_block_1['hold'] and k > locked_until_idx:
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
             if ck.high >= active_block_1['break']:
                 was_invalidated = True
                 break
         if was_invalidated:
             active_block_1 = b
             test_idx = -1
             active_block_2 = None
             continue
             
         active_block_2 = b 
         
         # Now, did this block yield an intent? We can evaluate IT at its HC!
         hc2 = active_block_2['hc_idx']
         
         # Is HC2 after our lock?
         if hc2 > locked_until_idx:
             # VALID!
             entry = active_block_2['hold']
             sl = entry + 15
             tp = entry - 30
             
             intents.append({
                 'time': history[hc2].timestamp.strftime('%H:%M'),
                 'entry': entry
             })
             
             # Calculate lock
             locked_until = simulate_trade_lock(history, hc2 + 1, entry, sl, tp, False)
             locked_until_idx = locked_until
             print(f"Issued intent at {history[hc2].timestamp.strftime('%H:%M')}. Locked until {history[min(locked_until, len(history)-1)].timestamp.strftime('%H:%M')}")
             
             # RESET completely so we seek a new Trap/Test
             active_block_1 = None
             active_block_2 = None
             test_idx = -1

print("Total specific intents triggered:", [i['time'] for i in intents])
