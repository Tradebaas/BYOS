import os
import sys
import pandas as pd
from datetime import timedelta
import json

_engine_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _engine_root not in sys.path:
    sys.path.insert(0, _engine_root)
os.chdir(_engine_root)

from src.layer4_execution.simulator import BacktestSimulator
from src.layer4_execution.data_vault import DataVault
from src.layer3_strategy.playbook_schema import PlaybookConfig
from src.layer3_strategy.rule_engine import RuleEngine
from src.layer2_theory.market_state import MarketTheoryState
from src.layer1_data.models import Candle
from src.layer3_strategy.modules.loss_cooldown_filter import LossCooldownFilter

def run_config(name, config_path, df_data):
    # CRITICAL FIX: Reset class-level persistent state across runs!
    LossCooldownFilter._last_loss_time = {}

    with open(config_path, "r") as f:
        cfg = json.load(f)
        
    playbook = PlaybookConfig(**cfg)
    
    engine = RuleEngine(playbook)
    vault = DataVault()
    sim = BacktestSimulator(vault, commission_points_per_trade=0.0)
    state = MarketTheoryState()

    last_ordered_setup_price = None
    last_ordered_setup_direction = None
    last_trade_count = 0
    
    for _, row in df_data.iterrows():
        c = Candle(
            timestamp=row['datetime'],
            open=row['open'],
            high=row['high'],
            low=row['low'],
            close=row['close'],
            volume=row['volume']
        )
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

    total_trades = len(vault.trades)
    wins = sum(1 for t in vault.trades if getattr(t, 'win', t.pnl_points > 0))
    losses = total_trades - wins
    
    # Calculate PnL for 2 contracts ($40 per point)
    net_pnl_2_contracts = sum(t.pnl_points * 40 for t in vault.trades)
    
    print(f"[{name}]")
    print(f" - Trades: {total_trades}")
    print(f" - Wins: {wins} | Losses: {losses} | Win Rate: {((wins/total_trades)*100) if total_trades > 0 else 0:.1f}%")
    print(f" - Net PnL (2 contracts): ${net_pnl_2_contracts:,.2f}")
    print("-" * 40)

def main():
    print("Laden van data...")
    df = pd.read_csv("data/backtest/candles/NQ_1min.csv")
    df['datetime'] = pd.to_datetime(df['timestamp_ms'], unit='ms', utc=True)
    
    max_date = df['datetime'].max()
    min_date_28 = max_date - timedelta(days=28)
    df_28_days = df[df['datetime'] >= min_date_28].copy()
    
    print(f"Data range ALL: {df['datetime'].min()} to {max_date} ({len(df)} candles)")
    print(f"Data range 28D: {min_date_28} to {max_date} ({len(df_28_days)} candles)")
    print("=" * 40)
    
    configs = [
        ("Eerste Optie 2 (playbook_yesterday)", ".tmp_optimize/playbook_yesterday.json"),
        ("Profiel 2 (profile2)", ".tmp/comparison/profile2.json"),
        ("Live Config (dtd_golden_setup)", "strategies/dtd_golden_setup/strategy_playbook.json")
    ]
    
    print("=== BACKTEST LAATSTE 28 DAGEN ===")
    for name, path in configs:
        if os.path.exists(path):
            run_config(name, path, df_28_days)
        else:
            print(f"[{name}] Bestand niet gevonden: {path}")
            
    print("\n=== BACKTEST OVER ALLE DATA ===")
    for name, path in configs:
        if os.path.exists(path):
            run_config(name, path, df)
        else:
            print(f"[{name}] Bestand niet gevonden: {path}")

if __name__ == '__main__':
    main()
