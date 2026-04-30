import os
import sys
import json
import pandas as pd
from datetime import datetime, timezone

_engine_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _engine_root not in sys.path:
    sys.path.insert(0, _engine_root)

from src.layer4_execution.simulator import BacktestSimulator
from src.layer4_execution.data_vault import DataVault
from src.layer3_strategy.config_parser import ConfigParser
from src.layer3_strategy.rule_engine import RuleEngine
from src.layer2_theory.market_state import MarketTheoryState
from src.layer1_data.models import Candle
from src.layer3_strategy.playbook_schema import PlaybookConfig
from src.layer3_strategy.modules.loss_cooldown_filter import LossCooldownFilter

data_path = "data/backtest/candles/NQ_1min.csv"
playbook_path = ".tmp_optimize/playbook_profile2.json"

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

with open(playbook_path, 'r') as f:
    cfg_data = json.load(f)

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

wins = 0
losses = 0
break_evens = 0

for t in vault.trades:
    if getattr(t, 'exit_reason', '') == 'take_profit':
        wins += 1
    elif getattr(t, 'exit_reason', '') == 'stop_loss' and t.pnl_points > 0:
        break_evens += 1
    elif getattr(t, 'exit_reason', '') == 'stop_loss':
        losses += 1
    else:
        if t.pnl_points > 5:
            wins += 1
        elif t.pnl_points > 0:
            break_evens += 1
        else:
            losses += 1

print(f"Total trades: {len(vault.trades)}")
print(f"Wins: {wins}")
print(f"Break Evens: {break_evens}")
print(f"Losses: {losses}")

