import sys
import time
from pathlib import Path
from datetime import timedelta
import logging

project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from modular_trading_engine.src.layer1_data.csv_parser import load_historical_1m_data
from zebas_core import ZebasEngine
import itertools

logging.getLogger("ZebasCore").setLevel(logging.ERROR)

def run_multi_simulation(candles):
    sl_list = [10, 15, 20, 30]
    tp_scales = [1.5, 2.0, 3.0, 4.0]
    be_options = [True, False]
    
    # Generate all variations
    configs = []
    for sl, scale2, use_be in itertools.product(sl_list, tp_scales, be_options):
        # We enforce exactly $600 risk per trade
        # Risk = contract_size * sl * 20 => contract_size = 600 / (sl * 20)
        contract_size = 600.0 / (sl * 20.0)
        
        for scale1 in [0.5, 1.0, 1.5]: # TP1 points
            tp1 = sl * scale1
            tp2 = sl * scale2
            if tp1 > tp2: continue
            
            configs.append({
                'id': len(configs),
                'sl': sl, 'tp1': tp1, 'tp2': tp2, 'be': use_be, 'contracts': contract_size,
                
                # State
                'equity': 0.0,
                'peak_equity': 0.0,
                'max_drawdown': 0.0,
                'daily_pnl': 0.0,
                'dll_hit_days': 0,
                'active_trade': None,
                'trades_executed': 0,
                'wins': 0,
                'losses': 0
            })
            
    print(f"Running sweep with {len(configs)} configurations in parallel...")
    
    engine = ZebasEngine(sl_pts=20.0, tp1_pts=20.0) # SL/TP here don't matter, we override in execution
    dollar_per_pt = 20.0
    dll_limit = -2000.0
    
    current_day = None
    
    start_time = time.time()
    
    for i, candle in enumerate(candles):
        day_str = candle.timestamp.strftime('%Y-%m-%d')
        if current_day != day_str:
            current_day = day_str
            for c in configs:
                c['daily_pnl'] = 0.0
                
        engine.process_candle(candle)
        setups = engine.get_actionable_setups()
        base_pending_long = next((s for s in setups if s.direction == 'LONG'), None)
        base_pending_short = next((s for s in setups if s.direction == 'SHORT'), None)
        
        for c in configs:
            if c['daily_pnl'] <= dll_limit:
                if c['active_trade'] is not None:
                    c['active_trade'] = None
                continue
                
            at = c['active_trade']
            if at is not None:
                # Resolve active trade
                trade_ended = False
                
                if at['direction'] == 'LONG':
                    # SL Hit
                    if candle.low <= at['current_sl']:
                        pts_loss = at['current_sl'] - at['entry_price']
                        mult = 0.5 if at['c1_closed'] else 1.0
                        total = pts_loss * dollar_per_pt * c['contracts'] * mult
                        c['equity'] += total; c['daily_pnl'] += total
                        c['trades_executed'] += 1; c['losses'] += 1
                        trade_ended = True
                        
                    # TP1 Hit
                    elif not at['c1_closed'] and candle.high >= at['tp1_price']:
                        pts_win = at['tp1_price'] - at['entry_price']
                        total = pts_win * dollar_per_pt * c['contracts'] * 0.5
                        c['equity'] += total; c['daily_pnl'] += total
                        at['c1_closed'] = True
                        if c['be']:
                            at['current_sl'] = at['entry_price'] + 0.25 # BE
                        if at['tp1_price'] >= at['tp2_price']:
                            c['trades_executed'] += 1; c['wins'] += 1
                            trade_ended = True
                            
                    # TP2 Hit
                    elif at['c1_closed'] and candle.high >= at['tp2_price']:
                        pts_win = at['tp2_price'] - at['entry_price']
                        total = pts_win * dollar_per_pt * c['contracts'] * 0.5
                        c['equity'] += total; c['daily_pnl'] += total
                        c['trades_executed'] += 1; c['wins'] += 1
                        trade_ended = True
                        
                else: # SHORT
                    # SL Hit
                    if candle.high >= at['current_sl']:
                        pts_loss = at['entry_price'] - at['current_sl']
                        mult = 0.5 if at['c1_closed'] else 1.0
                        total = pts_loss * dollar_per_pt * c['contracts'] * mult
                        c['equity'] += total; c['daily_pnl'] += total
                        c['trades_executed'] += 1; c['losses'] += 1
                        trade_ended = True
                        
                    # TP1 Hit
                    elif not at['c1_closed'] and candle.low <= at['tp1_price']:
                        pts_win = at['entry_price'] - at['tp1_price']
                        total = pts_win * dollar_per_pt * c['contracts'] * 0.5
                        c['equity'] += total; c['daily_pnl'] += total
                        at['c1_closed'] = True
                        if c['be']:
                            at['current_sl'] = at['entry_price'] - 0.25
                        if at['tp1_price'] <= at['tp2_price']:
                            c['trades_executed'] += 1; c['wins'] += 1
                            trade_ended = True
                            
                    # TP2 Hit
                    elif at['c1_closed'] and candle.low <= at['tp2_price']:
                        pts_win = at['entry_price'] - at['tp2_price']
                        total = pts_win * dollar_per_pt * c['contracts'] * 0.5
                        c['equity'] += total; c['daily_pnl'] += total
                        c['trades_executed'] += 1; c['wins'] += 1
                        trade_ended = True
                
                if trade_ended:
                    c['active_trade'] = None
                    # Update equity stats
                    if c['equity'] > c['peak_equity']:
                        c['peak_equity'] = c['equity']
                    dd = c['peak_equity'] - c['equity']
                    if dd > c['max_drawdown']:
                        c['max_drawdown'] = dd
                        
                    if c['daily_pnl'] <= dll_limit:
                        c['dll_hit_days'] += 1
                        
            else:
                # Handle pending entry logic
                # We assume standard limit order mechanics: 
                # If price drops to entry_price, we buy.
                if base_pending_long is not None and candle.low <= base_pending_long.entry_price:
                    c['active_trade'] = {
                        'direction': 'LONG',
                        'entry_price': base_pending_long.entry_price,
                        'current_sl': base_pending_long.entry_price - c['sl'],
                        'tp1_price': base_pending_long.entry_price + c['tp1'],
                        'tp2_price': base_pending_long.entry_price + c['tp2'],
                        'c1_closed': False
                    }
                elif base_pending_short is not None and candle.high >= base_pending_short.entry_price:
                    c['active_trade'] = {
                        'direction': 'SHORT',
                        'entry_price': base_pending_short.entry_price,
                        'current_sl': base_pending_short.entry_price + c['sl'],
                        'tp1_price': base_pending_short.entry_price - c['tp1'],
                        'tp2_price': base_pending_short.entry_price - c['tp2'],
                        'c1_closed': False
                    }

    print(f"Simulation completed in {time.time() - start_time:.2f} seconds.")
    
    # Filter and sorts
    valid_configs = [c for c in configs if c['trades_executed'] > 10 and c['equity'] > 0 and c['max_drawdown'] < 3000]
    valid_configs.sort(key=lambda x: x['equity'], reverse=True)
    
    print("\n" + "="*95)
    print(" TOP 10 CONFIGURATIONS (Sorted by Net Profit) - normalized to $600 Risk ".center(95, "="))
    print("SL (pts) | TP1 (pts) | TP2 (pts) | Move BE | Contracts | Net Profit | Max Drawdown | Trades | DLL Hits")
    print("-" * 95)
    for r in valid_configs[:10]:
        be_str = " YES " if r['be'] else " NO  "
        print(f"{r['sl']:8.1f} | {r['tp1']:9.1f} | {r['tp2']:9.1f} | {be_str} | {r['contracts']:9.1f} | " +
              f"${r['equity']:9.2f} | ${r['max_drawdown']:11.2f} | {r['trades_executed']:6} | {r['dll_hit_days']:8}")
    print("="*95 + "\n")
    
    # Optionally sort by profit factor or min drawdown
    valid_configs.sort(key=lambda x: x['max_drawdown'])
    print(" TOP 5 SAFEST CONFIGURATIONS (Least Drawdown, Profitable) ".center(95, "="))
    for r in valid_configs[:5]:
        be_str = " YES " if r['be'] else " NO  "
        print(f"{r['sl']:8.1f} | {r['tp1']:9.1f} | {r['tp2']:9.1f} | {be_str} | {r['contracts']:9.1f} | " +
              f"${r['equity']:9.2f} | ${r['max_drawdown']:11.2f} | {r['trades_executed']:6} | {r['dll_hit_days']:8}")

if __name__ == '__main__':
    data_file = project_root / 'modular_trading_engine/data/historical/NQ_1min.csv'
    all_candles = load_historical_1m_data(data_file)
    last_ts = all_candles[-1].timestamp
    # Focus on the last 4 weeks as requested by user previously
    four_weeks_candles = [c for c in all_candles if c.timestamp >= last_ts - timedelta(weeks=4)]
    
    run_multi_simulation(four_weeks_candles)
