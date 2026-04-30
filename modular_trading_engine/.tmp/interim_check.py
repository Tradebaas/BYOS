import os
import sys
import json
import pandas as pd
from datetime import datetime, timedelta, timezone
import copy

_engine_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _engine_root not in sys.path:
    sys.path.insert(0, _engine_root)
os.chdir(_engine_root)

from src.layer4_execution.simulator import BacktestSimulator
from src.layer4_execution.data_vault import DataVault
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

    multiplier = 40.0
    total_trades = len(vault.trades)
    wins = sum(1 for t in vault.trades if t.pnl_points > 0)
    net_pnl = sum(t.pnl_points * multiplier for t in vault.trades)
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    
    return {
        'params': params,
        'trades': total_trades,
        'win_rate': round(win_rate, 1),
        'net_pnl': round(net_pnl, 2)
    }

combos = [
    {'sl': 10.0, 'tp': 12.0, 'be_trig': 0.4, 'cd': 15, 'bw': 300, 'ttl': 10, 'lunch_kz': True},
    {'sl': 15.0, 'tp': 30.0, 'be_trig': 0.8, 'cd': 30, 'bw': 600, 'ttl': 20, 'lunch_kz': False},
    {'sl': 12.0, 'tp': 20.0, 'be_trig': 999.0, 'cd': 20, 'bw': 300, 'ttl': 15, 'lunch_kz': True}
]

print("Running interim check on 3 distinct profiles...")
for c in combos:
    res = run_simulation(c)
    print(json.dumps(res, indent=2))
