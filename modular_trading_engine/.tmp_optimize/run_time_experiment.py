import os
import sys
import pandas as pd
import json

from src.layer1_data.models import Candle
from src.layer2_theory.market_state import MarketTheoryState
from src.layer3_strategy.playbook_schema import PlaybookConfig
from src.layer3_strategy.rule_engine import RuleEngine
from src.layer4_execution.simulator import BacktestSimulator
from src.layer4_execution.data_vault import DataVault

import sys
sys.path.append(".tmp_optimize")
from time_exit_simulator import TimeExitBacktestSimulator

def load_candles():
    print("Loading historical data...")
    df = pd.read_csv("data/historical/NQ_1min.csv")
    df['timestamp'] = pd.to_datetime(df['datetime_utc'])
    
    candles = []
    for row in df.itertuples():
        c = Candle(
            timestamp=row.timestamp,
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=row.volume
        )
        candles.append(c)
    return candles

def run_experiment():
    candles = load_candles()
    with open("strategies/dtd_golden_setup/strategy_playbook.json", "r") as f:
        config = json.load(f)

    # 1. Baseline Simulator
    print(f"\nExecuting BASELINE over {len(candles)} candidates...")
    state_base = MarketTheoryState()
    cfg_base = PlaybookConfig(**config)
    engine_base = RuleEngine(cfg_base)
    vault_base = DataVault()
    sim_base = BacktestSimulator(vault_base)
    
    for c in candles:
        state_base.process_candle(c)
        intents = engine_base.evaluate(state_base, c.timestamp)
        for intent in intents:
            sim_base.stage_order(intent)
        sim_base.process_candle(c)
        
    trades_base = vault_base.trades

    # 2. Time Exit Simulator (6 minutes)
    print(f"\nExecuting 6-MINUTE TIME EXIT over {len(candles)} candidates...")
    state_time = MarketTheoryState()
    cfg_time = PlaybookConfig(**config)
    engine_time = RuleEngine(cfg_time)
    vault_time = DataVault()
    sim_time = TimeExitBacktestSimulator(vault_time, max_duration_minutes=6)
    
    for c in candles:
        state_time.process_candle(c)
        intents = engine_time.evaluate(state_time, c.timestamp)
        for intent in intents:
            sim_time.stage_order(intent)
        sim_time.process_candle(c)

    trades_time = vault_time.trades

    # Analyze Baseline
    def analyze(trades, name):
        total = len(trades)
        wins = sum(1 for t in trades if t.pnl_points > 0)
        losses = sum(1 for t in trades if t.pnl_points <= 0)
        pnl = sum(t.pnl_points for t in trades)
        
        print(f"\n--- RESULTS: {name} ---")
        print(f"Total Trades: {total}")
        if total > 0:
            print(f"Total Wins: {wins} ({(wins/total*100):.2f}%)")
            print(f"Total Losses: {losses} ({(losses/total*100):.2f}%)")
            print(f"Net PnL (Points): {pnl:.2f}")
            avg_win = sum(t.pnl_points for t in trades if t.pnl_points > 0) / max(wins, 1)
            avg_loss = sum(t.pnl_points for t in trades if t.pnl_points <= 0) / max(losses, 1)
            print(f"Avg Win: {avg_win:.2f}")
            print(f"Avg Loss: {avg_loss:.2f}")
        
    analyze(trades_base, "BASELINE (Original Playbook)")
    analyze(trades_time, "6-MINUTE TIME EXIT SHIELD")

if __name__ == "__main__":
    run_experiment()
