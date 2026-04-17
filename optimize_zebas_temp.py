import sys
from pathlib import Path
from datetime import timedelta

project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from modular_trading_engine.src.layer1_data.csv_parser import load_historical_1m_data
from zebas_core import ZebasEngine
import logging

logging.getLogger("ZebasCore").setLevel(logging.ERROR)

def run_optimization():
    data_file = project_root / 'modular_trading_engine/data/historical/NQ_1min.csv'
    all_candles = load_historical_1m_data(data_file)
    
    if not all_candles:
        print("No candles loaded.")
        return
        
    last_timestamp = all_candles[-1].timestamp
    start_time = last_timestamp - timedelta(weeks=4)
    candles = [c for c in all_candles if c.timestamp >= start_time]
    
    print(f"Loaded {len(candles)} candles. Starting Optimization Loop...")
    
    sl_options = [5, 10, 15, 20, 25, 30]
    tp_options = [10, 20, 30, 40, 50, 60, 80]
    
    best_win_rate = 0.0
    best_params = None
    results = []
    
    for sl in sl_options:
        for tp in tp_options:
            engine = ZebasEngine(sl_pts=sl, tp_pts=tp)
            trades = []
            active_trade = None
            pending_long = None
            pending_short = None
            
            for candle in candles:
                engine.process_candle(candle)
                
                if active_trade is not None:
                    if active_trade['direction'] == 'LONG':
                        if candle.low <= active_trade['sl']:
                            active_trade['win'] = False
                            trades.append(active_trade)
                            active_trade = None
                        elif candle.high >= active_trade['tp']:
                            active_trade['win'] = True
                            trades.append(active_trade)
                            active_trade = None
                    else: # SHORT
                        if candle.high >= active_trade['sl']:
                            active_trade['win'] = False
                            trades.append(active_trade)
                            active_trade = None
                        elif candle.low <= active_trade['tp']:
                            active_trade['win'] = True
                            trades.append(active_trade)
                            active_trade = None
                            
                    if active_trade is not None:
                        continue

                # Pending
                if pending_long is not None:
                    if candle.low <= pending_long.entry_price:
                        active_trade = {
                            'direction': 'LONG',
                            'sl': pending_long.stop_loss_price,
                            'tp': pending_long.take_profit_price,
                        }
                        pending_long = None
                        pending_short = None
                        continue
                        
                if pending_short is not None:
                    if candle.high >= pending_short.entry_price:
                        active_trade = {
                            'direction': 'SHORT',
                            'sl': pending_short.stop_loss_price,
                            'tp': pending_short.take_profit_price,
                        }
                        pending_long = None
                        pending_short = None
                        continue

                setups = engine.get_actionable_setups()
                pending_long = next((s for s in setups if s.direction == 'LONG'), None)
                pending_short = next((s for s in setups if s.direction == 'SHORT'), None)

            if len(trades) < 20: 
                # Ignore sets with too few trades to be statistically significant
                continue
                
            wins = sum(1 for t in trades if t['win'])
            win_rate = (wins / len(trades)) * 100
            
            results.append({
                'sl': sl, 'tp': tp, 'trades': len(trades), 'win_rate': win_rate
            })
            
            print(f"SL: {sl:2} | TP: {tp:2} | Trades: {len(trades):3} | Win Rate: {win_rate:5.2f}%")
            
            if win_rate > best_win_rate:
                best_win_rate = win_rate
                best_params = (sl, tp)

    print("\n================== TOP 5 CONFIGS ==================")
    results.sort(key=lambda x: x['win_rate'], reverse=True)
    for r in results[:5]:
         print(f"SL: {r['sl']:2} | TP: {r['tp']:2} | Trades: {r['trades']:3} | Win Rate: {r['win_rate']:5.2f}%")

if __name__ == '__main__':
    run_optimization()
