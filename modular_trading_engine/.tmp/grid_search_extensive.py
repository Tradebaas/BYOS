import os
import sys
import time
import json
import itertools
import pandas as pd
from datetime import datetime, timedelta, timezone
import multiprocessing as mp
import copy

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

days = 28
now = datetime.now(timezone.utc)
start_date = now - timedelta(days=days)

df = pd.read_csv(data_path)
df['datetime'] = pd.to_datetime(df['timestamp_ms'], unit='ms', utc=True)
df = df[(df['datetime'] >= start_date) & (df['datetime'] <= now)]

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

with open(playbook_path, 'r') as f:
    base_cfg_data = json.load(f)

def generate_combinations():
    sl_points = [10.0, 12.0, 15.0]
    tp_points = [12.0, 15.0, 20.0, 30.0]
    be_triggers = [0.4, 0.5, 0.8, 999.0]
    cooldowns = [15, 20, 30]
    bias_windows = [300, 600]
    ttls = [10, 15, 20]
    has_lunch_killzone = [True, False]
    
    combinations = []
    for sl, tp, be_trig, cd, bw, ttl, lunch_kz in itertools.product(sl_points, tp_points, be_triggers, cooldowns, bias_windows, ttls, has_lunch_killzone):
        combinations.append({
            'sl': sl,
            'tp': tp,
            'be_trig': be_trig,
            'cd': cd,
            'bw': bw,
            'ttl': ttl,
            'lunch_kz': lunch_kz
        })
    return combinations

def run_simulation(params):
    sl = params['sl']
    tp = params['tp']
    be_trig = params['be_trig']
    cd = params['cd']
    bw = params['bw']
    ttl = params['ttl']
    lunch_kz = params['lunch_kz']
    
    cfg_data = copy.deepcopy(base_cfg_data)
    
    pipeline = []
    for mod in cfg_data['pipeline']:
        if mod['module_type'] == 'ConfirmationHoldLevelTrigger':
            mod['params']['sl_points'] = sl
            mod['params']['tp_points'] = tp
            mod['params']['bias_window_size'] = bw
            mod['params']['ttl_candles'] = ttl
        elif mod['module_type'] == 'RATLimitOrder':
            mod['params']['absolute_sl_points'] = sl
            mod['params']['absolute_tp_points'] = tp
            mod['params']['breakeven_trigger_rr'] = be_trig
        elif mod['module_type'] == 'LossCooldownFilter':
            mod['params']['cooldown_minutes'] = cd
        elif mod['module_type'] == 'TTLTimeout':
            mod['params']['max_candles_open'] = ttl
        elif mod['module_type'] == 'KillzoneFilter':
            if not lunch_kz:
                new_exclude = []
                for kw in mod['params']['exclude_windows']:
                    if kw['start_hour'] == 12 and kw['end_hour'] == 13:
                        continue
                    new_exclude.append(kw)
                mod['params']['exclude_windows'] = new_exclude
                
        pipeline.append(mod)
        
    cfg_data['pipeline'] = pipeline

    from src.layer3_strategy.playbook_schema import PlaybookConfig
    cfg = PlaybookConfig(**cfg_data)
    
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

    starting_balance = 150000.0
    multiplier = 40.0 # 2 NQ per trade
    
    daily_stats = {}
    
    for t in vault.trades:
        ts = getattr(t, 'exit_time', getattr(t, 'entry_time', None))
        if ts is None:
             continue
        
        day_str = ts.strftime('%Y-%m-%d')
        if day_str not in daily_stats:
            daily_stats[day_str] = {'trades': 0, 'wins': 0, 'losses': 0, 'net_pnl': 0.0}
            
        daily_stats[day_str]['trades'] += 1
        daily_stats[day_str]['net_pnl'] += (t.pnl_points * multiplier)
        
        is_win = getattr(t, 'win', t.pnl_points > 0)
        if is_win:
            daily_stats[day_str]['wins'] += 1
        else:
            daily_stats[day_str]['losses'] += 1

    sorted_days = sorted(daily_stats.keys())
    
    current_balance = starting_balance
    account_progression = []
    
    for day in sorted_days:
        stats = daily_stats[day]
        net = stats['net_pnl']
        current_balance += net
        account_progression.append({
            'date': day,
            'pnl': net,
            'balance': current_balance,
            'trades': stats['trades']
        })
        
    total_trades = sum(d['trades'] for d in daily_stats.values())
    total_wins = sum(d['wins'] for d in daily_stats.values())
    total_net = sum(d['net_pnl'] for d in daily_stats.values())
    win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
    
    daily_pnls = [(day, daily_stats[day]['net_pnl']) for day in sorted_days]
    daily_pnls_sorted = sorted(daily_pnls, key=lambda x: x[1])
    
    worst_5 = daily_pnls_sorted[:5]
    best_5 = daily_pnls_sorted[-5:]
    best_5.reverse()

    return {
        'params': params,
        'total_trades': total_trades,
        'win_rate': win_rate,
        'total_net': total_net,
        'end_balance': current_balance,
        'best_5': best_5,
        'worst_5': worst_5,
        'daily_stats': account_progression
    }

if __name__ == '__main__':
    combos = generate_combinations()
    print(f"Starting grid search over {len(combos)} combinations...")
    t0 = time.time()
    
    with mp.Pool(processes=mp.cpu_count()) as pool:
        results = pool.map(run_simulation, combos)
        
    t1 = time.time()
    print(f"Finished in {t1-t0:.2f} seconds.")
    
    results.sort(key=lambda x: x['total_net'], reverse=True)
    
    top_5 = results[:5]
    
    with open('.tmp_optimize/grid_results_extensive.json', 'w') as f:
        json.dump(top_5, f, indent=2)
        
    print("Top 5 results saved to .tmp_optimize/grid_results_extensive.json")
