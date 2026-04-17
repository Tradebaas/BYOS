import sys
from pathlib import Path
from datetime import timedelta
import logging

project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from modular_trading_engine.src.layer1_data.csv_parser import load_historical_1m_data
from zebas_core import ZebasEngine

logging.getLogger("ZebasCore").setLevel(logging.ERROR)

def run_topstep_simulation(config):
    data_file = project_root / 'modular_trading_engine/data/historical/NQ_1min.csv'
    all_candles = load_historical_1m_data(data_file)
    
    if not all_candles:
        return
        
    last_timestamp = all_candles[-1].timestamp
    start_time = last_timestamp - timedelta(weeks=4)
    candles = [c for c in all_candles if c.timestamp >= start_time]
    
    engine = ZebasEngine(sl_pts=config['sl_pts'], tp_pts=config['tp2_pts']) # Use base engine
    
    # Economics
    dollar_per_pt = 20.0
    contracts = 2
    
    # State
    equity = 0.0
    peak_equity = 0.0
    max_drawdown = 0.0
    
    daily_pnl = 0.0
    current_day = None
    dll_hit_days = 0
    dll_limit = -2000.0
    
    trades_executed = 0
    wins = 0
    partial_wins = 0
    losses = 0
    time_stops = 0
    
    active_trade = None
    pending_long = None
    pending_short = None
    
    for i, candle in enumerate(candles):
        # Daily reset
        day_str = candle.timestamp.strftime('%Y-%m-%d')
        if current_day != day_str:
            current_day = day_str
            daily_pnl = 0.0
            
        if daily_pnl <= dll_limit:
            # Reached DLL, stop trading for today
            if active_trade: # Close market
                active_trade = None # Simulating flattening
            continue
            
        engine.process_candle(candle)
        
        # Monitor Active Trade
        if active_trade is not None:
            trade_duration = i - active_trade['entry_idx']
            pnl_c1 = 0
            pnl_c2 = 0
            exit_trade = False
            
            # Time Stop Check
            if config['time_stop'] > 0 and trade_duration > config['time_stop'] and not active_trade['be_triggered']:
                # Market close
                if active_trade['direction'] == 'LONG':
                    exit_price = candle.close
                    pts = exit_price - active_trade['entry_price']
                else:
                    exit_price = candle.close
                    pts = active_trade['entry_price'] - exit_price
                    
                total_pnl = pts * dollar_per_pt * contracts
                equity += total_pnl
                daily_pnl += total_pnl
                trades_executed += 1
                time_stops += 1
                if pts > 0: wins += 1 
                else: losses += 1
                
                active_trade = None
                exit_trade = True
                
            if not exit_trade:
                # Price action check
                if active_trade['direction'] == 'LONG':
                    # Check SL
                    if candle.low <= active_trade['current_sl']:
                        pts_loss = active_trade['current_sl'] - active_trade['entry_price']
                        
                        if active_trade['c1_closed']:
                            # Only C2 stopped out (probably at BE)
                            total_pnl = pts_loss * dollar_per_pt
                            equity += total_pnl
                            daily_pnl += total_pnl
                            partial_wins += 1
                            trades_executed += 1
                        else:
                            # Both stopped out
                            total_pnl = pts_loss * dollar_per_pt * contracts
                            equity += total_pnl
                            daily_pnl += total_pnl
                            losses += 1
                            trades_executed += 1
                            
                        active_trade = None
                        
                    # Check TP1
                    elif not active_trade['c1_closed'] and candle.high >= active_trade['tp1_price']:
                        active_trade['c1_closed'] = True
                        pts_win = active_trade['tp1_price'] - active_trade['entry_price']
                        total_pnl = pts_win * dollar_per_pt
                        equity += total_pnl
                        daily_pnl += total_pnl
                        # Move SL to BE
                        if config['move_be']:
                            active_trade['current_sl'] = active_trade['entry_price'] + 0.25 # 1 tick BE
                            
                        # If TP1 == TP2, close everything
                        if active_trade['tp1_price'] >= active_trade['tp2_price']:
                            trades_executed += 1
                            wins += 1
                            active_trade = None
                            
                    # Check TP2
                    elif active_trade['c1_closed'] and candle.high >= active_trade['tp2_price']:
                        pts_win = active_trade['tp2_price'] - active_trade['entry_price']
                        total_pnl = pts_win * dollar_per_pt
                        equity += total_pnl
                        daily_pnl += total_pnl
                        trades_executed += 1
                        wins += 1
                        active_trade = None
                        
                else: # SHORT
                    # Check SL
                    if candle.high >= active_trade['current_sl']:
                        pts_loss = active_trade['entry_price'] - active_trade['current_sl']
                        
                        if active_trade['c1_closed']:
                            total_pnl = pts_loss * dollar_per_pt
                            equity += total_pnl
                            daily_pnl += total_pnl
                            partial_wins += 1
                            trades_executed += 1
                        else:
                            total_pnl = pts_loss * dollar_per_pt * contracts
                            equity += total_pnl
                            daily_pnl += total_pnl
                            losses += 1
                            trades_executed += 1
                            
                        active_trade = None
                        
                    # Check TP1
                    elif not active_trade['c1_closed'] and candle.low <= active_trade['tp1_price']:
                        active_trade['c1_closed'] = True
                        pts_win = active_trade['entry_price'] - active_trade['tp1_price']
                        total_pnl = pts_win * dollar_per_pt
                        equity += total_pnl
                        daily_pnl += total_pnl
                        # Move SL to BE
                        if config['move_be']:
                            active_trade['current_sl'] = active_trade['entry_price'] - 0.25
                            
                        if active_trade['tp1_price'] <= active_trade['tp2_price']:
                            trades_executed += 1
                            wins += 1
                            active_trade = None
                            
                    # Check TP2
                    elif active_trade['c1_closed'] and candle.low <= active_trade['tp2_price']:
                        pts_win = active_trade['entry_price'] - active_trade['tp2_price']
                        total_pnl = pts_win * dollar_per_pt
                        equity += total_pnl
                        daily_pnl += total_pnl
                        trades_executed += 1
                        wins += 1
                        active_trade = None
            
            # Max Drawdown calculations
            if equity > peak_equity:
                peak_equity = equity
            dd = peak_equity - equity
            if dd > max_drawdown:
                max_drawdown = dd
                
            if daily_pnl <= dll_limit:
                dll_hit_days += 1
                
            if active_trade is not None:
                continue

        # Handle Pending Limit Orders
        if pending_long is not None:
            if candle.low <= pending_long.entry_price:
                # Dynamic TP distance
                break_lvl = next((l for l in engine.breaks if not l.is_break_up and l.holdPrice == pending_long.entry_price), None)
                dynamic_tp_dist = config['tp2_pts']
                if break_lvl and config['dynamic_tp']:
                    dist = abs(break_lvl.price - break_lvl.holdPrice)
                    dynamic_tp_dist = dist if dist > config['tp1_pts'] else config['tp2_pts']

                active_trade = {
                    'direction': 'LONG',
                    'entry_price': pending_long.entry_price,
                    'current_sl': pending_long.stop_loss_price,
                    'tp1_price': pending_long.entry_price + config['tp1_pts'],
                    'tp2_price': pending_long.entry_price + dynamic_tp_dist,
                    'c1_closed': False,
                    'be_triggered': False,
                    'entry_idx': i
                }
                pending_long = None
                pending_short = None
                continue
                
        if pending_short is not None:
            if candle.high >= pending_short.entry_price:
                break_lvl = next((l for l in engine.breaks if l.is_break_up and l.holdPrice == pending_short.entry_price), None)
                dynamic_tp_dist = config['tp2_pts']
                if break_lvl and config['dynamic_tp']:
                    dist = abs(break_lvl.price - break_lvl.holdPrice)
                    dynamic_tp_dist = dist if dist > config['tp1_pts'] else config['tp2_pts']

                active_trade = {
                    'direction': 'SHORT',
                    'entry_price': pending_short.entry_price,
                    'current_sl': pending_short.stop_loss_price,
                    'tp1_price': pending_short.entry_price - config['tp1_pts'],
                    'tp2_price': pending_short.entry_price - dynamic_tp_dist,
                    'c1_closed': False,
                    'be_triggered': False,
                    'entry_idx': i
                }
                pending_long = None
                pending_short = None
                continue

        setups = engine.get_actionable_setups()
        pending_long = next((s for s in setups if s.direction == 'LONG'), None)
        pending_short = next((s for s in setups if s.direction == 'SHORT'), None)

    return {
        'Net_Profit': equity,
        'Max_Drawdown': max_drawdown,
        'Trades': trades_executed,
        'Full_Wins': wins,
        'Partial_Wins': partial_wins,
        'Losses': losses,
        'Time_Stops': time_stops,
        'DLL_Days_Hit': dll_hit_days
    }

configs = [
    {"name": "1. Baseline (SL20/TP40) No Adjustments", "sl_pts": 20, "tp1_pts": 40, "tp2_pts": 40, "move_be": False, "time_stop": 0, "dynamic_tp": False},
    {"name": "2. Baseline + Breakeven @ 20pts", "sl_pts": 20, "tp1_pts": 20, "tp2_pts": 40, "move_be": True, "time_stop": 0, "dynamic_tp": False},
    {"name": "3. Aggressive Scalp/BE (SL20/TP1:15/TP2:40 + BE)", "sl_pts": 20, "tp1_pts": 15, "tp2_pts": 40, "move_be": True, "time_stop": 0, "dynamic_tp": False},
    {"name": "4. Aggressive Scalp/BE + TimeStop 15m", "sl_pts": 20, "tp1_pts": 15, "tp2_pts": 40, "move_be": True, "time_stop": 15, "dynamic_tp": False},
    {"name": "5. Dynamic TP to Origin Level (SL20/TP1:15 + BE + TimeStop)", "sl_pts": 20, "tp1_pts": 15, "tp2_pts": 40, "move_be": True, "time_stop": 15, "dynamic_tp": True},
    {"name": "6. Deep Buffer (SL30) / Scalp TP1:15 + BE + Dynamic TP", "sl_pts": 30, "tp1_pts": 15, "tp2_pts": 50, "move_be": True, "time_stop": 20, "dynamic_tp": True},
    {"name": "7. 100K Guardian (SL15/TP1:15+BE/TP2:Dynamic)", "sl_pts": 15, "tp1_pts": 15, "tp2_pts": 40, "move_be": True, "time_stop": 15, "dynamic_tp": True},
]

print("Starting TopStep Simulations (2 Contracts)...")
for c in configs:
    res = run_topstep_simulation(c)
    print(f"\n{c['name']}")
    print(f"Net Profit:   ${res['Net_Profit']:.2f}")
    print(f"Max Drawdown: ${res['Max_Drawdown']:.2f}")
    print(f"Trades: {res['Trades']} (Full Wins: {res['Full_Wins']}, BE/Partials: {res['Partial_Wins']}, Losses: {res['Losses']}, Time Stops: {res['Time_Stops']})")
    print(f"DLL Hits (Days Fails): {res['DLL_Days_Hit']}")

