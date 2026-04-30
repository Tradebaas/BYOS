import os
import sys
import json
import itertools
import pandas as pd
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed

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

def run_backtest_for_month(cfg: dict, df_month: pd.DataFrame, commission: float) -> dict:
    playbook = PlaybookConfig(**cfg)
    engine = RuleEngine(playbook)
    vault = DataVault()
    sim = BacktestSimulator(vault, commission_points_per_trade=commission)
    state = MarketTheoryState()
    
    last_ordered_setup_price = None
    last_ordered_setup_direction = None
    last_trade_count = 0
    
    for _, row in df_month.iterrows():
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
    net_pnl = sum(t.pnl_points * 20 for t in vault.trades)
    
    return {
        "trades": total_trades,
        "wins": wins,
        "losses": losses,
        "net_pnl": net_pnl,
        "conflict_count": sim.intra_candle_conflict_count
    }

def evaluate_params(params_tuple, df, commission):
    bias, prem, sl_tp, be_rr = params_tuple
    
    cfg = {
        "strategy_id": f"GridSearch_{bias}_{prem}_{sl_tp}_{be_rr}",
        "pipeline": [
            {
                "module_type": "ConfirmationHoldLevelTrigger",
                "params": {
                    "bias_window_size": bias,
                    "premium_discount_window_size": prem,
                    "ttl_candles": 15,
                    "sl_points": float(sl_tp),
                    "tp_points": float(sl_tp),
                    "sim_frontrun_points": 3.0
                }
            },
            {
                "module_type": "KillzoneFilter",
                "params": {
                    "start_hour": 0,
                    "start_minute": 0,
                    "end_hour": 23,
                    "end_minute": 59,
                    "timezone": "America/New_York",
                    "exclude_windows": [
                        {"start_hour": 9, "start_minute": 20, "end_hour": 9, "end_minute": 40},
                        {"start_hour": 15, "start_minute": 49, "end_hour": 18, "end_minute": 0}
                    ]
                }
            },
            {
                "module_type": "TTLTimeout",
                "params": {"max_candles_open": 15}
            },
            {
                "module_type": "RATLimitOrder",
                "params": {
                    "tick_size": 0.25,
                    "entry_frontrun_ticks": 12,
                    "stop_loss_padding_ticks": 0,
                    "absolute_sl_points": float(sl_tp),
                    "absolute_tp_points": float(sl_tp),
                    "breakeven_trigger_rr": be_rr,
                    "breakeven_offset_ticks": 0
                }
            }
        ]
    }
    
    months = [1, 2, 3, 4]
    total_trades = 0
    total_net = 0
    total_conflicts = 0
    pnls = []
    
    for m in months:
        df_month = df[df['datetime'].dt.month == m]
        if df_month.empty:
            continue
        stats = run_backtest_for_month(cfg, df_month, commission)
        total_trades += stats['trades']
        total_net += stats['net_pnl']
        total_conflicts += stats['conflict_count']
        pnls.append(stats['net_pnl'])
        
    import numpy as np
    std_dev = np.std(pnls) if pnls else 0
    min_pnl = min(pnls) if pnls else 0
    conflict_rate = (total_conflicts / total_trades) if total_trades > 0 else 1.0
    
    return {
        "params": params_tuple,
        "total_trades": total_trades,
        "net_pnl": total_net,
        "min_monthly_pnl": min_pnl,
        "std_dev": std_dev,
        "conflict_rate": conflict_rate
    }

def main():
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    data_path = "data/backtest/candles/NQ_1min.csv"
    df = pd.read_csv(data_path)
    df['datetime'] = pd.to_datetime(df['timestamp_ms'], unit='ms', utc=True)
    
    grid = {
        "bias": [200, 300, 400],
        "prem": [100, 150, 200],
        "sl_tp": [10, 12, 15],
        "be_rr": [None, 0.5]
    }
    
    keys, values = zip(*grid.items())
    combinations = list(itertools.product(*values))
    
    logging.info(f"Starting grid search over {len(combinations)} combinations...")
    
    results = []
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = {executor.submit(evaluate_params, c, df, 0.2): c for c in combinations}
        for future in as_completed(futures):
            res = future.result()
            results.append(res)
            logging.info(f"Evaluated {res['params']} -> Trades: {res['total_trades']}, PnL: ${res['net_pnl']:.2f}, Min Month: ${res['min_monthly_pnl']:.2f}")

    # Sort results prioritizing consistency: minimum monthly PnL > 0, then total net PnL, then lowest conflict rate
    valid_results = [r for r in results if r['conflict_rate'] <= 0.05 and r['total_trades'] >= 100]
    if not valid_results:
        valid_results = results  # Fallback
        
    sorted_res = sorted(valid_results, key=lambda x: (x['min_monthly_pnl'], x['net_pnl']), reverse=True)
    
    logging.info("\nTOP 5 ROBUST STRATEGIES:")
    logging.info("| Bias | Prem | SL/TP | BE_RR | Trades | Net PnL | Min Month PnL | Conflict Rate |")
    logging.info("|------|------|-------|-------|--------|---------|---------------|---------------|")
    for r in sorted_res[:5]:
        b, p, st, be = r['params']
        logging.info(f"| {b:4} | {p:4} | {st:5} | {str(be):5} | {r['total_trades']:6} | ${r['net_pnl']:7.2f} | ${r['min_monthly_pnl']:13.2f} | {r['conflict_rate']*100:12.1f}% |")

if __name__ == "__main__":
    main()
