"""
Trailing TP Multi-Variant Backtest
===================================
Runs the BASELINE + 5 trailing TP variants over identical historical data.
Outputs a comparison table at the end.

ZERO production code modified — everything lives in .tmp_optimize/
"""
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

sys.path.append(".tmp_optimize")
from trailing_tp_simulator import TrailingTPSimulator


def load_candles():
    print("Loading historical data...")
    df = pd.read_csv("data/historical/NQ_1min.csv")
    df['timestamp'] = pd.to_datetime(df['datetime_utc'])
    candles = []
    for row in df.itertuples():
        c = Candle(
            timestamp=row.timestamp,
            open=row.open, high=row.high,
            low=row.low, close=row.close,
            volume=row.volume
        )
        candles.append(c)
    print(f"  → Loaded {len(candles)} candles ({df['timestamp'].min()} to {df['timestamp'].max()})")
    return candles


def run_single(candles, config, simulator_factory, label):
    """Run a single backtest variant and return stats dict."""
    state = MarketTheoryState()
    cfg = PlaybookConfig(**config)
    engine = RuleEngine(cfg)
    vault = DataVault()
    sim = simulator_factory(vault)
    
    for c in candles:
        state.process_candle(c)
        intents = engine.evaluate(state, c.timestamp)
        for intent in intents:
            sim.stage_order(intent)
        sim.process_candle(c)
    
    trades = vault.trades
    total = len(trades)
    if total == 0:
        return {"label": label, "trades": 0, "wins": 0, "wr": 0, "losses": 0,
                "pnl": 0, "avg_win": 0, "avg_loss": 0, "max_win": 0, "max_loss": 0,
                "profit_factor": 0}
    
    wins = [t for t in trades if t.pnl_points > 0]
    losses = [t for t in trades if t.pnl_points <= 0]
    pnl = sum(t.pnl_points for t in trades)
    
    gross_win = sum(t.pnl_points for t in wins) if wins else 0
    gross_loss = abs(sum(t.pnl_points for t in losses)) if losses else 0.001
    
    return {
        "label": label,
        "trades": total,
        "wins": len(wins),
        "wr": len(wins) / total * 100,
        "losses": len(losses),
        "pnl": pnl,
        "avg_win": gross_win / max(len(wins), 1),
        "avg_loss": -sum(t.pnl_points for t in losses) / max(len(losses), 1),
        "max_win": max(t.pnl_points for t in trades),
        "max_loss": min(t.pnl_points for t in trades),
        "profit_factor": gross_win / gross_loss,
    }


def main():
    candles = load_candles()
    with open("strategies/dtd_golden_setup/strategy_playbook.json", "r") as f:
        config = json.load(f)
    
    # Define all variants
    variants = [
        ("BASELINE (12pt SL/TP)", lambda v: BacktestSimulator(v)),
        ("A) Trail: Act@6pt, Dist=4pt", lambda v: TrailingTPSimulator(v, activation_points=6.0, trail_distance=4.0)),
        ("B) Trail: Act@8pt, Dist=4pt", lambda v: TrailingTPSimulator(v, activation_points=8.0, trail_distance=4.0)),
        ("C) Trail: Act@6pt, Dist=6pt", lambda v: TrailingTPSimulator(v, activation_points=6.0, trail_distance=6.0)),
        ("D) Trail: Act@4pt, Dist=3pt", lambda v: TrailingTPSimulator(v, activation_points=4.0, trail_distance=3.0)),
        ("E) Hybrid: TP@12 + BE@6pt", lambda v: TrailingTPSimulator(v, activation_points=6.0, trail_distance=6.0, keep_original_tp=True)),
    ]
    
    results = []
    for label, factory in variants:
        print(f"\n{'='*60}")
        print(f"  Running: {label}")
        print(f"{'='*60}")
        r = run_single(candles, config, factory, label)
        results.append(r)
        print(f"  → {r['trades']} trades | WR: {r['wr']:.1f}% | PnL: {r['pnl']:.1f}pts | PF: {r['profit_factor']:.2f}")
    
    # Print comparison table
    print("\n")
    print("=" * 120)
    print("  TRAILING TP BACKTEST COMPARISON TABLE")
    print("=" * 120)
    print(f"{'Variant':<35} {'Trades':>7} {'Wins':>6} {'WR%':>7} {'PnL(pts)':>10} {'AvgWin':>8} {'AvgLoss':>9} {'MaxWin':>8} {'MaxLoss':>9} {'PF':>6}")
    print("-" * 120)
    
    baseline_pnl = results[0]["pnl"] if results else 0
    
    for r in results:
        delta = r["pnl"] - baseline_pnl
        delta_str = f"({'+' if delta >= 0 else ''}{delta:.0f})" if r["label"] != results[0]["label"] else ""
        print(f"{r['label']:<35} {r['trades']:>7} {r['wins']:>6} {r['wr']:>6.1f}% {r['pnl']:>9.1f} {r['avg_win']:>8.2f} {r['avg_loss']:>8.2f}  {r['max_win']:>7.2f} {r['max_loss']:>8.2f}  {r['profit_factor']:>5.2f}  {delta_str}")
    
    print("-" * 120)
    print(f"\n  Baseline PnL: {baseline_pnl:.1f} pts")
    
    # Find best variant
    best = max(results, key=lambda x: x["pnl"])
    print(f"  Best Variant: {best['label']} → {best['pnl']:.1f} pts (Δ {best['pnl'] - baseline_pnl:+.1f})")
    
    # Extra: Distribution analysis for the best trailing variant (excluding baseline)
    trailing_results = [r for r in results if r["label"] != results[0]["label"]]
    if trailing_results:
        best_trail = max(trailing_results, key=lambda x: x["pnl"])
        print(f"  Best Trail:   {best_trail['label']} → {best_trail['pnl']:.1f} pts (Δ {best_trail['pnl'] - baseline_pnl:+.1f})")
        
        worse = sum(1 for r in trailing_results if r["pnl"] < baseline_pnl)
        better = sum(1 for r in trailing_results if r["pnl"] > baseline_pnl)
        print(f"  Variants beating baseline: {better}/{len(trailing_results)}")
        print(f"  Variants worse than baseline: {worse}/{len(trailing_results)}")


if __name__ == "__main__":
    main()
