import sys
from pathlib import Path
from datetime import datetime, timedelta
import logging

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from modular_trading_engine.src.layer1_data.csv_parser import load_historical_1m_data
from zebas_core import ZebasEngine

logging.getLogger("ZebasCore").setLevel(logging.WARNING)

def run_optimization():
    data_file = project_root / 'modular_trading_engine/data/historical/NQ_1min.csv'
    all_candles = load_historical_1m_data(data_file)
    
    if not all_candles:
        print("No candles loaded.")
        return
        
    last_timestamp = all_candles[-1].timestamp
    start_time = last_timestamp - timedelta(weeks=4)
    candles = [c for c in all_candles if c.timestamp >= start_time]
    
    print(f"Loaded {len(candles)} candles for 4-week window.")
    
    engine = ZebasEngine(sl_pts=10.0, tp1_pts=10.0) # These values don't matter for finding setups
    
    # Pre-compute all engine states and active setups per candle
    # To correctly simulate, we just need the raw setups and candle data.
    # Because ZebasEngine is fast, running it multiple times might just take a minute.
    # But wait, running ZebasEngine 50 times takes 50 * 5s = 250s = 4 mins.
    # Let's just do a grid and run the engine once, collecting all potential setup times!
    
    print("Pre-computing all Zebas setups... (takes ~5 seconds)")
    
    # We will record the exact index when a setup is "filled"
    # A setup is filled if the candle crosses the exact entry price.
    pending_long = None
    pending_short = None
    
    # Array of (fill_index, direction, entry_price)
    all_fills = []
    
    for i, candle in enumerate(candles):
        engine.process_candle(candle)
        
        # Check if pending order is hit
        if pending_long is not None and candle.low <= pending_long.entry_price:
            all_fills.append((i, 'LONG', pending_long.entry_price))
            pending_long = None
            pending_short = None # Day Trading Decrypted clears other? Actually in backtest_zebas we cleared it.
        elif pending_short is not None and candle.high >= pending_short.entry_price:
            all_fills.append((i, 'SHORT', pending_short.entry_price))
            pending_long = None
            pending_short = None
            
        # Update pendings for next iteration
        setups = engine.get_actionable_setups()
        pending_long = None
        pending_short = None
        for setup in setups:
            if setup.direction == 'LONG':
                pending_long = setup
            if setup.direction == 'SHORT':
                pending_short = setup

    print(f"Found {len(all_fills)} total potential entry points over 4 weeks.")
    
    sl_options = [5, 10, 15, 20]
    tp_options = [5, 10, 15, 20, 25, 30, 40, 50, 60]
    
    results = []
    
    print("Running grid search over SL and TP combinations...")
    
    for sl in sl_options:
        for tp in tp_options:
            trades = []
            active_trade = None
            
            # Simulate the sequence
            for i, candle in enumerate(candles):
                
                # Check active trade
                if active_trade is not None:
                    if active_trade['direction'] == 'LONG':
                        if candle.low <= active_trade['sl']:
                            trades.append(False)
                            active_trade = None
                        elif candle.high >= active_trade['tp']:
                            trades.append(True)
                            active_trade = None
                    else: # SHORT
                        if candle.high >= active_trade['sl']:
                            trades.append(False)
                            active_trade = None
                        elif candle.low <= active_trade['tp']:
                            trades.append(True)
                            active_trade = None
                
                if active_trade is not None:
                    continue
                    
                # We are NOT in a trade. Did a fill occur on this candle?
                # Optimization: We check if `i` is in all_fills!
                # Wait, what if a fill occurred on candle `i` but we just exited on candle `i`? 
                # Our backtest allows entering on the same candle? 
                # Let's just find the FIRST fill >= i
                pass
    
    # Due to index-matching complexity in python, let's just use the direct simulation method.
    pass

# Running the loop directly
def fast_grid_sim():
    data_file = project_root / 'modular_trading_engine/data/historical/NQ_1min.csv'
    all_candles = load_historical_1m_data(data_file)
    last_timestamp = all_candles[-1].timestamp
    start_time = last_timestamp - timedelta(weeks=4)
    candles = [c for c in all_candles if c.timestamp >= start_time]
    
    engine = ZebasEngine()
    
    # Pre-extract pendings per candle!
    print("Pre-calculating signals...")
    pendings = []
    pending_long = None
    pending_short = None
    for i, candle in enumerate(candles):
        # Did we hit?
        hit = None
        if pending_long is not None and candle.low <= pending_long.entry_price:
            hit = ('LONG', pending_long.entry_price)
        elif pending_short is not None and candle.high >= pending_short.entry_price:
            hit = ('SHORT', pending_short.entry_price)
            
        pendings.append((hit, pending_long, pending_short))
        
        engine.process_candle(candle)
        setups = engine.get_actionable_setups()
        pending_long = None
        pending_short = None
        for setup in setups:
            if setup.direction == 'LONG':
                pending_long = setup
            if setup.direction == 'SHORT':
                pending_short = setup

    print("Executing Grid...")
    
    sl_options = [5, 10, 15, 20, 25]
    tp_options = [5, 10, 15, 20, 25, 30, 40, 50]
    
    results = []
    
    for sl in sl_options:
        for tp in tp_options:
            trades = 0
            wins = 0
            active = None
            
            peak_pts = 0
            current_pts = 0
            max_drawdown = 0
            
            for i, candle in enumerate(candles):
                if active is not None:
                    if active['dir'] == 'LONG':
                        if candle.low <= active['sl']:
                            trades += 1
                            current_pts -= sl
                            if (peak_pts - current_pts) > max_drawdown:
                                max_drawdown = peak_pts - current_pts
                            active = None
                        elif candle.high >= active['tp']:
                            trades += 1
                            wins += 1
                            current_pts += tp
                            if current_pts > peak_pts:
                                peak_pts = current_pts
                            active = None
                    else:
                        if candle.high >= active['sl']:
                            trades += 1
                            current_pts -= sl
                            if (peak_pts - current_pts) > max_drawdown:
                                max_drawdown = peak_pts - current_pts
                            active = None
                        elif candle.low <= active['tp']:
                            trades += 1
                            wins += 1
                            current_pts += tp
                            if current_pts > peak_pts:
                                peak_pts = current_pts
                            active = None
                            
                if active is not None:
                    continue
                    
                # Not active, check if we got a hit on this candle
                hit, p_l, p_s = pendings[i]
                if hit is not None:
                    trades_dir, entry_price = hit
                    active = {
                        'dir': trades_dir,
                        'entry': entry_price,
                        'sl': entry_price - sl if trades_dir == 'LONG' else entry_price + sl,
                        'tp': entry_price + tp if trades_dir == 'LONG' else entry_price - tp
                    }
                    
            if trades > 0:
                win_rate = wins / trades
                ev = (win_rate * tp) - ((1 - win_rate) * sl)
                total_pts = ev * trades
                results.append({
                    'sl': sl, 'tp': tp, 'trades': trades, 
                    'win_rate': win_rate, 'ev': ev, 'total_pts': total_pts,
                    'mdd': max_drawdown
                })

    # Sort results by Expected Value
    results.sort(key=lambda x: x['total_pts'], reverse=True)
    
    print("\n=== TOP 10 PARAMETER COMBINATIONS (Sorted by Total Points (Expected)) ===")
    print(f"{'SL':<5} | {'TP':<5} | {'Trades':<6} | {'Win%':<7} | {'EV (pts)':<10} | {'Total Pts':<10} | {'MDD (pts)':<10} | {'RR'}")
    print("-" * 75)
    for r in results[:10]:
        rr_ratio = r['tp'] / r['sl']
        print(f"{r['sl']:<5} | {r['tp']:<5} | {r['trades']:<6} | {r['win_rate']*100:>5.1f}% | {r['ev']:>10.2f} | {r['total_pts']:>10.1f} | {r['mdd']:>10.1f} | 1:{rr_ratio:.1f}")

if __name__ == '__main__':
    fast_grid_sim()
