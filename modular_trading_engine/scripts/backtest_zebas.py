import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from modular_trading_engine.src.layer1_data.csv_parser import load_historical_1m_data
from zebas_core import ZebasEngine

# Disable spammy Zebas logger
logging.getLogger("ZebasCore").setLevel(logging.WARNING)

def run_zebas_backtest():
    data_file = project_root / 'modular_trading_engine/data/historical/NQ_1min.csv'
    all_candles = load_historical_1m_data(data_file)
    
    if not all_candles:
        print("No candles loaded.")
        return
        
    last_timestamp = all_candles[-1].timestamp
    start_time = last_timestamp - timedelta(days=14)
    candles = [c for c in all_candles if c.timestamp >= start_time]
    
    print(f"Loaded {len(candles)} candles for 14-day window (from {candles[0].timestamp} to {candles[-1].timestamp})")
    
    engine = ZebasEngine(sl_pts=10.0, tp1_pts=20.0)
    
    trades = []
    active_trade = None
    
    pending_long = None
    pending_short = None
    
    for i, candle in enumerate(candles):
        # Update Engine - Give it the candle directly. The engine takes an object with .open, .high, .low, .close, .is_bullish, .is_bearish, .timestamp
        # Our Candle object from csv_parser has all this except is_bullish?
        # Let's check csv_parser.py's Candle model if it has 'is_bullish' and 'is_bearish' attributes.
        engine.process_candle(candle)
        
        # Check Execution Context for active trade
        if active_trade is not None:
            if active_trade['direction'] == 'LONG':
                if candle.low <= active_trade['sl']:
                    active_trade['exit_price'] = active_trade['sl']
                    active_trade['exit_time'] = candle.timestamp
                    active_trade['win'] = False
                    trades.append(active_trade)
                    active_trade = None
                elif candle.high >= active_trade['tp']:
                    active_trade['exit_price'] = active_trade['tp']
                    active_trade['exit_time'] = candle.timestamp
                    active_trade['win'] = True
                    trades.append(active_trade)
                    active_trade = None
            else: # SHORT
                if candle.high >= active_trade['sl']:
                    active_trade['exit_price'] = active_trade['sl']
                    active_trade['exit_time'] = candle.timestamp
                    active_trade['win'] = False
                    trades.append(active_trade)
                    active_trade = None
                elif candle.low <= active_trade['tp']:
                    active_trade['exit_price'] = active_trade['tp']
                    active_trade['exit_time'] = candle.timestamp
                    active_trade['win'] = True
                    trades.append(active_trade)
                    active_trade = None
                    
            if active_trade is not None:
                continue

        # Handle Pending Limit Orders (hit logic)
        if pending_long is not None:
            if candle.low <= pending_long.entry_price: # Fill LONG
                break_lvl = None
                for lvl in engine.breaks:
                    if lvl.is_break_up == False and lvl.holdPrice == pending_long.entry_price:
                        break_lvl = lvl
                        break
                
                # ZebasEngine keeps appending to its own internal copy, which gets out of sync with enumerate if we crop the candles list. 
                # Wait, ZebasEngine stores `self.candles = []` and appends every candle it processes. So the index in engine.candles matches enumerate(candles).
                break_time = engine.candles[break_lvl.creation_bar_idx].timestamp if break_lvl else "Unknown"
                test1_time = engine.candles[break_lvl.test1Bar].timestamp if break_lvl and break_lvl.test1Bar else "Unknown"
                origin_time = engine.candles[break_lvl.originBar].timestamp if break_lvl and break_lvl.originBar else "Unknown"
                hold_time = engine.candles[break_lvl.holdBar].timestamp if break_lvl and break_lvl.holdBar else "Unknown"

                active_trade = {
                    'direction': 'LONG',
                    'entry_time': candle.timestamp,
                    'entry_price': pending_long.entry_price,
                    'sl': pending_long.stop_loss_price,
                    'tp': pending_long.tp1_price,
                    'break_time': break_time,
                    'test1_time': test1_time,
                    'origin_time': origin_time,
                    'hold_time': hold_time,
                }
                pending_long = None
                pending_short = None
                continue
                
        if pending_short is not None:
            if candle.high >= pending_short.entry_price: # Fill SHORT
                break_lvl = None
                for lvl in engine.breaks:
                    if lvl.is_break_up == True and lvl.holdPrice == pending_short.entry_price:
                        break_lvl = lvl
                        break

                break_time = engine.candles[break_lvl.creation_bar_idx].timestamp if break_lvl else "Unknown"
                test1_time = engine.candles[break_lvl.test1Bar].timestamp if break_lvl and break_lvl.test1Bar else "Unknown"
                origin_time = engine.candles[break_lvl.originBar].timestamp if break_lvl and break_lvl.originBar else "Unknown"
                hold_time = engine.candles[break_lvl.holdBar].timestamp if break_lvl and break_lvl.holdBar else "Unknown"

                active_trade = {
                    'direction': 'SHORT',
                    'entry_time': candle.timestamp,
                    'entry_price': pending_short.entry_price,
                    'sl': pending_short.stop_loss_price,
                    'tp': pending_short.tp1_price,
                    'break_time': break_time,
                    'test1_time': test1_time,
                    'origin_time': origin_time,
                    'hold_time': hold_time,
                }
                pending_long = None
                pending_short = None
                continue

        # Update pendings for next iteration
        setups = engine.get_actionable_setups()
        new_pending_long = None
        new_pending_short = None
        for setup in setups:
            if setup.direction == 'LONG':
                new_pending_long = setup
            if setup.direction == 'SHORT':
                new_pending_short = setup
                
        pending_long = new_pending_long
        pending_short = new_pending_short

    # Print Report
    print(f"\n==============================================")
    print(f"BACKTEST REPORT ZEBAS_CORE.PY (4 WEKEN)")
    print(f"==============================================")
    print(f"Total Completed Trades: {len(trades)}")
    
    wins = [t for t in trades if t['win']]
    losses = [t for t in trades if not t['win']]
    if trades:
        print(f"Win Rate: {(len(wins)/len(trades))*100:.2f}% ({len(wins)}W / {len(losses)}L)")
        
    print("\nLAATSTE 3 TRADES:")
    for i, t in enumerate(trades[-3:]):
        outcome = "WIN" if t['win'] else "LOSS"
        # Avoid index out of bounds error theoretically possible
        idx = len(trades) - 3 + i if len(trades) >= 3 else i
        print(f"\nTrade {idx+1}:")
        print(f"  Direction:   {t['direction']}")
        print(f"  Tijd Break:  {t['break_time']}")
        print(f"  Tijd Test 1: {t.get('test1_time', 'Unknown')}")
        print(f"  Tijd Test 2 (Origin): {t['origin_time']}")
        print(f"  Tijd Hold:   {t['hold_time']}")
        print(f"  Entry Tijd:  {t['entry_time']}")
        print(f"  Entry Price: {t['entry_price']:.2f}")
        print(f"  SL Hit/TP:   {outcome}")

if __name__ == '__main__':
    run_zebas_backtest()
