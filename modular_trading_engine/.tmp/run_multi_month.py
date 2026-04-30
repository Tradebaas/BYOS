import os
import sys
import argparse
import pandas as pd
import logging
from datetime import datetime, timezone

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

def format_color(pnl: float) -> str:
    return "🟢" if pnl >= 0 else "🔴"

def run_backtest_for_month(playbook_path: str, df_month: pd.DataFrame, commission: float) -> dict:
    cfg = ConfigParser.load_playbook(playbook_path)
    engine = RuleEngine(cfg)
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
            
    # Calculate stats
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

def main():
    parser = argparse.ArgumentParser(description="Multi-Month Backtest Runner")
    parser.add_argument("--playbook", type=str, required=True, help="Path to playbook json")
    parser.add_argument("--commission", type=float, default=0.2, help="Commission per trade in points")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    data_path = "data/backtest/candles/NQ_1min.csv"
    if not os.path.exists(data_path):
        logging.error(f"Error: {data_path} not found.")
        sys.exit(1)
        
    logging.info(f"Loading full data from {data_path}...")
    df = pd.read_csv(data_path)
    df['datetime'] = pd.to_datetime(df['timestamp_ms'], unit='ms', utc=True)
    
    months = [1, 2, 3, 4]
    month_names = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr"}
    
    total_net_pnl = 0.0
    total_trades = 0
    total_conflicts = 0
    monthly_pnls = []
    
    logging.info(f"\n==============================================")
    logging.info(f"📅 MULTI-MONTH ROBUSTNESS REPORT")
    logging.info(f"Playbook: {args.playbook}")
    logging.info(f"Commission (Points): {args.commission}")
    logging.info(f"==============================================\n")
    logging.info("| Month | Trades | Wins | Losses | Conflicts | Net PnL |")
    logging.info("|-------|--------|------|--------|-----------|---------|")
    
    for m in months:
        df_month = df[df['datetime'].dt.month == m]
        if df_month.empty:
            continue
            
        stats = run_backtest_for_month(args.playbook, df_month, args.commission)
        
        m_name = month_names[m]
        tr = stats['trades']
        w = stats['wins']
        l = stats['losses']
        conf = stats['conflict_count']
        net = stats['net_pnl']
        
        total_trades += tr
        total_conflicts += conf
        total_net_pnl += net
        monthly_pnls.append(net)
        
        logging.info(f"| {m_name:5} | {tr:6} | {w:4} | {l:6} | {conf:9} | {format_color(net)} ${net:7.2f} |")
        
    logging.info(f"------------------------------------------------------------------")
    logging.info(f"| TOTAL | {total_trades:6} |      |        | {total_conflicts:9} | {format_color(total_net_pnl)} ${total_net_pnl:7.2f} |")
    
    import numpy as np
    std_dev = np.std(monthly_pnls) if monthly_pnls else 0
    conflict_rate = (total_conflicts / total_trades * 100) if total_trades > 0 else 0
    
    logging.info(f"\n📊 CONSISTENCY & RELIABILITY")
    logging.info(f"Intra-Candle Conflict Rate: {conflict_rate:.1f}%")
    logging.info(f"Monthly PnL Standard Deviation: ${std_dev:.2f}")
    if conflict_rate > 5:
        logging.warning("⚠️ WARNING: Conflict Rate is very high! Strategy parameters are too tight for 1-minute bars.")

if __name__ == "__main__":
    main()
