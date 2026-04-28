"""
Trade Reconciliation: Live CSV vs Backtest Variant D
=====================================================
For each live trade in trades_export (3).csv, find the closest matching
backtest trade by:
  - Direction (Long/Short)
  - Entry price (within 2pt tolerance)
  - Entry time (within 5-minute tolerance)

Then compare outcomes (Win/Loss, PnL, exit price).
"""
import os
import sys
import csv
import json
import pandas as pd
from datetime import datetime, timedelta

from src.layer1_data.models import Candle
from src.layer2_theory.market_state import MarketTheoryState
from src.layer3_strategy.playbook_schema import PlaybookConfig
from src.layer3_strategy.rule_engine import RuleEngine
from src.layer4_execution.data_vault import DataVault, TradeRecord

sys.path.append(".tmp_optimize")
from trailing_tp_simulator import TrailingTPSimulator


def load_live_trades():
    """Parse the live trades CSV."""
    trades = []
    csv_path = os.path.join(os.path.dirname(__file__), "..", "..", "trades_export (3).csv")
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip empty rows
            id_val = row.get("Id", "").strip()
            if not id_val:
                continue
            # Parse timestamps — they are in +02:00 timezone
            entered = row["EnteredAt"].strip()
            exited = row["ExitedAt"].strip()
            
            # Parse with timezone
            from dateutil import parser as dtparser
            entry_time = dtparser.parse(entered)
            exit_time = dtparser.parse(exited)
            
            # Convert to UTC for comparison with backtest (which uses UTC candle timestamps)
            entry_utc = entry_time.astimezone(tz=None).replace(tzinfo=None) if entry_time.tzinfo else entry_time
            # Actually let's convert to UTC properly
            import pytz
            entry_utc = entry_time.astimezone(pytz.utc).replace(tzinfo=None)
            exit_utc = exit_time.astimezone(pytz.utc).replace(tzinfo=None)
            
            entry_price = float(row["EntryPrice"])
            exit_price = float(row["ExitPrice"])
            pnl = float(row["PnL"])
            direction = row["Type"].strip()
            is_bullish = direction == "Long"
            is_win = pnl > 0
            
            trades.append({
                "id": row["Id"],
                "entry_time": entry_utc,
                "exit_time": exit_utc,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "pnl": pnl,
                "direction": direction,
                "is_bullish": is_bullish,
                "is_win": is_win,
                "pnl_pts": pnl / 20.0,  # NQ: $20 per point
            })
    return trades


def run_variant_d_backtest():
    """Run Variant D and return all trade records."""
    print("Running Variant D backtest (Act@4pt, Trail=3pt)...")
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
    
    with open("strategies/dtd_golden_setup/strategy_playbook.json", "r") as f:
        config = json.load(f)
    
    state = MarketTheoryState()
    cfg = PlaybookConfig(**config)
    engine = RuleEngine(cfg)
    vault = DataVault()
    sim = TrailingTPSimulator(vault, activation_points=4.0, trail_distance=3.0)
    
    for c in candles:
        state.process_candle(c)
        intents = engine.evaluate(state, c.timestamp)
        for intent in intents:
            sim.stage_order(intent)
        sim.process_candle(c)
    
    print(f"  → Backtest produced {len(vault.trades)} trades")
    return vault.trades


def find_best_match(live_trade, bt_trades, time_tolerance_min=5, price_tolerance=2.0):
    """Find the best matching backtest trade for a given live trade."""
    best = None
    best_score = float('inf')
    
    for bt in bt_trades:
        # Direction must match
        if live_trade["is_bullish"] != bt.is_bullish:
            continue
        
        # Time check
        time_diff = abs((live_trade["entry_time"] - bt.entry_time).total_seconds())
        if time_diff > time_tolerance_min * 60:
            continue
        
        # Price check
        price_diff = abs(live_trade["entry_price"] - bt.entry_price)
        if price_diff > price_tolerance:
            continue
        
        # Score: lower is better (weighted time + price)
        score = time_diff / 60.0 + price_diff
        if score < best_score:
            best_score = score
            best = bt
    
    return best, best_score


def main():
    live_trades = load_live_trades()
    print(f"Loaded {len(live_trades)} live trades from CSV")
    print(f"  Date range: {live_trades[0]['entry_time']} → {live_trades[-1]['entry_time']}")
    print()
    
    bt_trades = run_variant_d_backtest()
    print()
    
    # Filter backtest trades to the same date range as live trades
    min_date = live_trades[0]["entry_time"] - timedelta(hours=1)
    max_date = live_trades[-1]["entry_time"] + timedelta(hours=1)
    bt_in_range = [t for t in bt_trades if min_date <= t.entry_time <= max_date]
    print(f"Backtest trades in live date range: {len(bt_in_range)}")
    print()
    
    # Match each live trade
    print("=" * 160)
    print(f"{'#':>3} {'Live Entry Time':<22} {'Dir':>5} {'Live EP':>10} {'BT EP':>10} {'ΔPrice':>7} {'ΔTime':>7} {'Live PnL':>10} {'BT PnL':>10} {'Live':>5} {'BT':>5} {'Match':>8}")
    print("-" * 160)
    
    matched = 0
    same_outcome = 0
    missed = 0
    live_only = 0
    
    used_bt = set()  # Track which BT trades have been used
    
    for i, lt in enumerate(live_trades):
        # Find match (excluding already-used BT trades)
        available_bt = [t for j, t in enumerate(bt_in_range) if j not in used_bt]
        match, score = find_best_match(lt, available_bt)
        
        if match:
            # Mark this BT trade as used
            bt_idx = bt_in_range.index(match)
            used_bt.add(bt_idx)
            
            matched += 1
            price_diff = lt["entry_price"] - match.entry_price
            time_diff = (lt["entry_time"] - match.entry_time).total_seconds() / 60.0
            
            live_result = "WIN" if lt["is_win"] else "LOSS"
            bt_result = "WIN" if match.win else "LOSS"
            outcome_match = "✅" if live_result == bt_result else "❌"
            
            if live_result == bt_result:
                same_outcome += 1
            
            print(f"{i+1:>3} {str(lt['entry_time']):<22} {lt['direction']:>5} {lt['entry_price']:>10.2f} {match.entry_price:>10.2f} {price_diff:>+7.2f} {time_diff:>+6.1f}m {lt['pnl_pts']:>+9.1f}pt {match.pnl_points:>+9.1f}pt {live_result:>5} {bt_result:>5} {outcome_match:>5}")
        else:
            missed += 1
            live_result = "WIN" if lt["is_win"] else "LOSS"
            print(f"{i+1:>3} {str(lt['entry_time']):<22} {lt['direction']:>5} {lt['entry_price']:>10.2f} {'---':>10} {'---':>7} {'---':>7} {lt['pnl_pts']:>+9.1f}pt {'---':>10} {live_result:>5} {'---':>5} {'MISS':>5}")
    
    # Summary
    print("-" * 160)
    print()
    print("=" * 80)
    print("  RECONCILIATION SUMMARY")
    print("=" * 80)
    print(f"  Live trades:           {len(live_trades)}")
    print(f"  BT trades (in range):  {len(bt_in_range)}")
    print(f"  Matched:               {matched}/{len(live_trades)} ({matched/len(live_trades)*100:.0f}%)")
    print(f"  Missed (no BT match):  {missed}")
    print(f"  Same outcome (W/L):    {same_outcome}/{matched} ({same_outcome/max(matched,1)*100:.0f}%)")
    print(f"  Different outcome:     {matched - same_outcome}/{matched}")
    print()
    
    # PnL comparison  
    live_pnl = sum(t["pnl_pts"] for t in live_trades)
    bt_pnl = sum(t.pnl_points for t in bt_in_range)
    print(f"  Live PnL (total):      {live_pnl:+.1f} pts")
    print(f"  BT PnL (in range):     {bt_pnl:+.1f} pts")
    print(f"  Δ PnL:                 {bt_pnl - live_pnl:+.1f} pts")
    print()
    
    # Extra: BT trades NOT in live (backtest-only signals)
    bt_only = len(bt_in_range) - matched
    print(f"  BT-only trades:        {bt_only} (signals the engine saw but live didn't trade)")


if __name__ == "__main__":
    main()
