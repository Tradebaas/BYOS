import os
import sys
import time
import json
import itertools
import pandas as pd
from datetime import datetime, timezone
import multiprocessing as mp

_engine_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _engine_root not in sys.path:
    sys.path.insert(0, _engine_root)
os.chdir(_engine_root)

from src.layer4_execution.simulator import BacktestSimulator
from src.layer4_execution.data_vault import DataVault
from src.layer3_strategy.config_parser import ConfigParser
from src.layer3_strategy.rule_engine import RuleEngine
from src.layer2_theory.market_state import MarketTheoryState
from src.layer1_data.models import Candle
from src.layer3_strategy.modules.loss_cooldown_filter import LossCooldownFilter

data_path = "data/backtest/candles/NQ_1min.csv"
playbook_path = "strategies/dtd_golden_setup/strategy_playbook.json"

df = pd.read_csv(data_path)
df['datetime'] = pd.to_datetime(df['timestamp_ms'], unit='ms', utc=True)
start_date = pd.to_datetime("2026-04-01 00:00:00", utc=True)
end_date = pd.to_datetime("2026-04-29 23:59:59", utc=True)
df = df[(df['datetime'] >= start_date) & (df['datetime'] <= end_date)]

candles = []
for _, row in df.iterrows():
    candles.append(Candle(
        timestamp=row['datetime'],
        open=row['open'],
        high=row['high'],
        low=row['low'],
        close=row['close'],
        volume=row['volume']
    ))

def generate_combinations():
    sl_points = [10.0, 12.0, 15.0]
    tp_points = [15.0, 18.0, 20.0, 25.0]
    be_triggers = [0.4, 0.5, 0.6, 0.7, 0.8]
    be_offsets = [2, 4]
    cooldowns = [15, 20, 30]
    
    combinations = []
    for sl, tp, be_trig, be_off, cd in itertools.product(sl_points, tp_points, be_triggers, be_offsets, cooldowns):
        # Enforce logical constraints
        # No need to test combinations where BE trigger is absurdly high relative to TP
        combinations.append({
            'sl': sl,
            'tp': tp,
            'be_trig': be_trig,
            'be_off': be_off,
            'cd': cd
        })
    return combinations

def run_simulation(params):
    sl, tp, be_trig, be_off, cd = params['sl'], params['tp'], params['be_trig'], params['be_off'], params['cd']
    
    with open(playbook_path, 'r') as f:
        cfg_data = json.load(f)
        
    for mod in cfg_data['pipeline']:
        if mod['module_type'] == 'ConfirmationHoldLevelTrigger':
            mod['params']['sl_points'] = sl
            mod['params']['tp_points'] = tp
        if mod['module_type'] == 'RATLimitOrder':
            mod['params']['absolute_sl_points'] = sl
            mod['params']['absolute_tp_points'] = tp
            mod['params']['breakeven_trigger_rr'] = be_trig
            mod['params']['breakeven_offset_ticks'] = be_off
        if mod['module_type'] == 'LossCooldownFilter':
            mod['params']['cooldown_minutes'] = cd

    from src.layer3_strategy.playbook_schema import PlaybookConfig
    cfg = PlaybookConfig(**cfg_data)
    
    # We must reset the state for each worker run because class variables might be shared in some contexts
    # though in mp.Pool each process has its own memory. Safe to clear.
    LossCooldownFilter._last_loss_time.clear()
    
    engine = RuleEngine(cfg)
    vault = DataVault()
    sim = BacktestSimulator(vault)
    state = MarketTheoryState()
    
    last_ordered_setup_price = None
    last_ordered_setup_direction = None
    last_trade_count = 0
    
    for c in candles:
        sim.process_candle(c)
        state.process_candle(c)
        
        current_trade_count = len(vault.trades)
        last_trade_result = None
        last_trade_is_bullish = None
        if current_trade_count > last_trade_count:
            last_closed_trade = vault.trades[-1]
            last_trade_result = last_closed_trade.pnl_points
            last_trade_is_bullish = last_closed_trade.is_bullish
            last_trade_count = current_trade_count
            
        if hasattr(sim, 'active_pos') and sim.active_pos is not None:
             continue
             
        intents = engine.evaluate(state, c.timestamp, last_trade_result=last_trade_result, last_trade_is_bullish=last_trade_is_bullish)
        active_intent = intents[-1] if intents else None
        current_setup_price = active_intent.entry_price if active_intent else None
        
        if sim.pending_intent is not None:
            if not active_intent or current_setup_price != sim.pending_intent.entry_price:
                sim.cancel_all()
                if active_intent:
                    last_ordered_setup_price = None
            continue
            
        if active_intent:
            if active_intent.entry_price == last_ordered_setup_price and active_intent.is_bullish == last_ordered_setup_direction:
                continue
                
            sim.stage_order(active_intent)
            last_ordered_setup_price = active_intent.entry_price
            last_ordered_setup_direction = active_intent.is_bullish

    # Calculate metrics
    multiplier = 20
    balance = 50000.0
    peak_balance = 50000.0
    max_drawdown = 0.0
    wins = 0
    losses = 0
    
    sorted_trades = sorted(vault.trades, key=lambda t: getattr(t, 'exit_time', getattr(t, 'entry_time', datetime.min.replace(tzinfo=timezone.utc))))
    
    for t in sorted_trades:
        # Calculate MAE
        if t.is_bullish:
            mae_points = t.entry_price - t.mae if t.mae < t.entry_price else 0
        else:
            mae_points = t.mae - t.entry_price if t.mae > t.entry_price else 0
            
        floating_loss_usd = mae_points * multiplier
        floating_balance = balance - floating_loss_usd
        
        current_floating_drawdown = peak_balance - floating_balance
        if current_floating_drawdown > max_drawdown:
            max_drawdown = current_floating_drawdown
            
        pnl_usd = t.pnl_points * multiplier
        balance += pnl_usd
        
        if pnl_usd >= 0:
            wins += 1
        else:
            losses += 1
            
        if balance > peak_balance:
            peak_balance = balance
            
    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    pnl = balance - 50000.0
    
    return {
        'params': params,
        'total_trades': total_trades,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'pnl': pnl,
        'max_dd': max_drawdown
    }

if __name__ == '__main__':
    combos = generate_combinations()
    print(f"Starting grid search over {len(combos)} combinations...")
    t0 = time.time()
    
    # Use multiprocessing pool
    with mp.Pool(processes=mp.cpu_count()) as pool:
        results = pool.map(run_simulation, combos)
        
    t1 = time.time()
    print(f"Finished in {t1-t0:.2f} seconds.")
    
    # Filter and sort results
    # User's goals: Winrate >= 70%, PnL > 5200, Max DD < 2000
    
    # Sort primarily by PnL, then by WinRate, then lowest DD
    # Let's assign a score or just sort by PnL desc
    
    results.sort(key=lambda x: (x['pnl'], x['win_rate'], -x['max_dd']), reverse=True)
    
    # Save to a JSON file
    with open('.tmp_optimize/grid_results.json', 'w') as f:
        json.update = json.dump(results, f, indent=2)
        
    print("Top 10 results:")
    for i, r in enumerate(results[:10]):
        p = r['params']
        print(f"#{i+1} | SL: {p['sl']}, TP: {p['tp']}, BE: {p['be_trig']} (off: {p['be_off']}), CD: {p['cd']}m")
        print(f"   -> Trades: {r['total_trades']} | Win Rate: {r['win_rate']:.2f}% | PnL: ${r['pnl']:.2f} | Max DD: ${r['max_dd']:.2f}")
