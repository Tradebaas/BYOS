import os
import sys
import json
import pandas as pd
from typing import List, Any

# Core framework
from src.layer2_theory.market_state import MarketTheoryState
from src.layer1_data.models import Candle
from src.layer3_strategy.config_parser import ConfigParser
from src.layer3_strategy.rule_engine import RuleEngine
from src.layer4_execution.simulator import BacktestSimulator
from src.layer4_execution.data_vault import DataVault

from src.layer3_strategy.modules import confirmation_hold_level_trigger

def run_backtest_with_engine(engine, df):
    state = MarketTheoryState()
    vault = DataVault()
    sim = BacktestSimulator(vault)
    
    last_ordered_setup_price = None
    last_ordered_setup_direction = None
    
    old_stdout = sys.stdout
    sys.stdout = open(os.devnull, 'w')
    
    for i, row in df.iterrows():
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
        
        if hasattr(sim, 'active_pos') and sim.active_pos is not None:
            continue
            
        intents = engine.evaluate(state, c.timestamp)
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
            
    sys.stdout = old_stdout
    return vault.trades


def run_analysis():
    print("Loading data...")
    df = pd.read_csv("data/historical/NQ_1min.csv")
    df['datetime'] = pd.to_datetime(df['timestamp_ms'], unit='ms', utc=True)
    df = df.tail(27366)
    
    ttl = 15
    with open("strategies/dtd_golden_setup/strategy_playbook.json", "r") as f:
        data = json.load(f)
    for m in data['pipeline']:
        if m['module_type'] == 'ConfirmationHoldLevelTrigger':
            m['params']['ttl_candles'] = ttl
        if m['module_type'] == 'TTLTimeout':
            m['params']['max_age_minutes'] = ttl
            
    from src.layer3_strategy.playbook_schema import PlaybookConfig
    
    # Run Baseline
    print("Running Baseline...")
    import importlib
    importlib.reload(confirmation_hold_level_trigger)
    cfg1 = PlaybookConfig(**data)
    engine_baseline = RuleEngine(cfg1)
    baseline_trades = run_backtest_with_engine(engine_baseline, df)
    
    # Define Custom Patch
    original_cls = confirmation_hold_level_trigger.ConfirmationHoldLevelTrigger

    class CustomConfirmationHoldLevelTrigger(original_cls):
        def find_blocks(self, history: List[Any], start_idx: int, is_bullish: bool):
            blocks = []
            end_idx = len(history)
            for i in range(start_idx, end_idx - 2):
                c1 = history[i]
                c1_bull = c1.is_bullish
                c1_bear = c1.is_bearish
                if not is_bullish:
                    if not c1_bull: continue
                    c2 = history[i+1]
                    if not c2.is_bearish: continue
                    c3 = history[i+2]
                    if not c3.is_bearish: continue
                    hard_close_idx = -1
                    for j in range(i+2, min(i+15, end_idx)):
                        cj = history[j]
                        if cj.is_bearish and cj.open < c1.low and cj.close < c1.low:
                            hard_close_idx = j
                            break
                        if cj.high >= c2.high: break
                    if hard_close_idx != -1:
                        block_candles = history[i:hard_close_idx+1]
                        blocks.append({
                            'type': 'short', 'hold_front': c1.low, 'hold_back': c1.high,
                            'hold_entry': c1.open, 'break': c2.high, 'c1_idx': i, 'hc_idx': hard_close_idx,
                            'max_high': max(c.high for c in block_candles), 'min_low': min(c.low for c in block_candles)
                        })
                else:
                    if not c1_bear: continue
                    c2 = history[i+1]
                    if not c2.is_bullish: continue
                    c3 = history[i+2]
                    if not c3.is_bullish: continue
                    hard_close_idx = -1
                    for j in range(i+2, min(i+15, end_idx)):
                        cj = history[j]
                        if cj.is_bullish and cj.open > c1.high and cj.close > c1.high:
                            hard_close_idx = j
                            break
                        if cj.low <= c2.low: break
                    if hard_close_idx != -1:
                        block_candles = history[i:hard_close_idx+1]
                        blocks.append({
                            'type': 'long', 'hold_front': c1.high, 'hold_back': c1.low,
                            'hold_entry': c1.open, 'break': c2.low, 'c1_idx': i, 'hc_idx': hard_close_idx,
                            'max_high': max(c.high for c in block_candles), 'min_low': min(c.low for c in block_candles)
                        })
            return blocks

        def process_direction(self, context: PipelineContext, is_bullish: bool) -> None:
            history = context.theory_state.history
            if not history: return
            bias_window_size = self.params.get('bias_window_size', 200)
            current_idx = len(history) - 1
            start_idx = max(0, current_idx - bias_window_size)
            ttl_candles = self.params.get('ttl_candles', 30)
            sl_points = self.params.get('sl_points', 15.0)
            tp_points = self.params.get('tp_points', 30.0)
            blocks = self.find_blocks(history, start_idx, is_bullish)
            if not blocks: return
            active_anchors = []
            locked_until_idx = -1
            latest_valid_setup = None
            for b in blocks:
                b['last_checked_idx'] = b['hc_idx']
                surviving_anchors = []
                confirmed_setups = []
                for anchor in active_anchors:
                    was_invalidated = False
                    found_test = -1
                    for k in range(anchor['last_checked_idx'] + 1, b['c1_idx'] + 1):
                        ck = history[k]
                        if not is_bullish:
                            if ck.is_bullish and ck.open > anchor['hold_entry'] and ck.close > anchor['hold_entry']:
                                was_invalidated = True; break
                            if ck.high >= anchor['max_high']:
                                was_invalidated = True; break
                            if ck.high >= anchor['hold_front'] and k > locked_until_idx:
                                found_test = k
                        else:
                            if ck.is_bearish and ck.open < anchor['hold_entry'] and ck.close < anchor['hold_entry']:
                                was_invalidated = True; break
                            if ck.low <= anchor['min_low']:
                                was_invalidated = True; break
                            if ck.low <= anchor['hold_front'] and k > locked_until_idx:
                                found_test = k
                    if was_invalidated: continue
                    if found_test != -1: confirmed_setups.append({'anchor': anchor, 'b2': b})
                    else:
                        anchor['last_checked_idx'] = b['c1_idx']
                        surviving_anchors.append(anchor)
                handled_as_execution = False
                if confirmed_setups:
                    handled_as_execution = True
                    if is_bullish: best_setup = min(confirmed_setups, key=lambda s: s['anchor']['hold_entry'])
                    else: best_setup = max(confirmed_setups, key=lambda s: s['anchor']['hold_entry'])
                    b2 = best_setup['b2']
                    hc2 = b2['hc_idx']
                    if hc2 > locked_until_idx:
                        entry = b2['hold_entry']
                        pd_window_size = self.params.get('premium_discount_window_size', bias_window_size)
                        is_valid_zone = False
                        if pd_window_size == 0: is_valid_zone = True
                        else:
                            eval_start_idx = max(0, hc2 - pd_window_size)
                            eval_candles = history[eval_start_idx:hc2+1]
                            range_high = max(ck.high for ck in eval_candles)
                            range_low = min(ck.low for ck in eval_candles)
                            midpoint = (range_high + range_low) / 2
                            if not is_bullish:
                                if entry >= midpoint: is_valid_zone = True
                            else:
                                if entry <= midpoint: is_valid_zone = True
                        if is_valid_zone:
                            sim_frontrun = self.params.get('sim_frontrun_points', 1.0)
                            if not is_bullish: sim_entry = entry - sim_frontrun; sl = sim_entry + sl_points; tp = sim_entry - tp_points
                            else: sim_entry = entry + sim_frontrun; sl = sim_entry - sl_points; tp = sim_entry + tp_points
                            locked_until_idx = self.simulate_trade_lock(history, hc2 + 1, sim_entry, sl, tp, is_bullish, ttl_candles)
                            latest_valid_setup = b2
                if not handled_as_execution: surviving_anchors.append(b)
                active_anchors = surviving_anchors
            if latest_valid_setup:
                if locked_until_idx >= current_idx:
                    from src.layer2_theory.models import TheoryLevel, LevelType
                    level_data = TheoryLevel(
                        timestamp=history[latest_valid_setup['hc_idx']].timestamp,
                        level_type=LevelType.HOLD_LEVEL,
                        is_bullish=is_bullish,
                        price_high=latest_valid_setup['break'], 
                        price_low=latest_valid_setup['break'],
                        price_open=latest_valid_setup['hold_entry'],
                        status="identified_hl2"
                    )
                    context.setup_candidates.append(confirmation_hold_level_trigger.RetroScannerTracker(level_data))

    from src.layer3_strategy.pipeline_context import PipelineContext
    confirmation_hold_level_trigger.ConfirmationHoldLevelTrigger = CustomConfirmationHoldLevelTrigger
    
    # Run Filtered
    print("Running Filtered...")
    cfg2 = PlaybookConfig(**data)
    engine_filtered = RuleEngine(cfg2)
    filtered_trades = run_backtest_with_engine(engine_filtered, df)
    
    b_times = {t.entry_time: t for t in baseline_trades}
    f_times = {t.entry_time: t for t in filtered_trades}
    
    print("\n--- DIFFERENCE ANALYSIS ---")
    skipped_in_filtered = set(b_times.keys()) - set(f_times.keys())
    new_in_filtered = set(f_times.keys()) - set(b_times.keys())
    
    print(f"Baseline total trades: {len(baseline_trades)}")
    print(f"Filtered total trades: {len(filtered_trades)}")
    
    print("\n--- TRADES SKIPPED (Avoided bad limit locks due to filter) ---")
    for k in sorted(list(skipped_in_filtered))[:5]:
        t = b_times[k]
        print(f"Avoided: {t.entry_time} | Bullish: {t.is_bullish} | PnL: {t.pnl_points} (Win: {t.win})")
        
    print("\n--- TRADES NEWLY CAPTURED (Because system was free at that time) ---")
    for k in sorted(list(new_in_filtered))[:5]:
        t = f_times[k]
        print(f"Captured: {t.entry_time} | Bullish: {t.is_bullish} | PnL: {t.pnl_points} (Win: {t.win})")

if __name__ == "__main__":
    run_analysis()
