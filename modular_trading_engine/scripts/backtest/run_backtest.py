import os
import sys
import argparse
import pandas as pd
import logging
from datetime import datetime, timedelta, timezone

# Ensure engine root is on sys.path (works from any CWD)
_engine_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _engine_root not in sys.path:
    sys.path.insert(0, _engine_root)
os.chdir(_engine_root)  # So relative paths like 'data/' and 'strategies/' resolve

from src.layer4_execution.simulator import BacktestSimulator
from src.layer4_execution.data_vault import DataVault
from src.layer3_strategy.config_parser import ConfigParser
from src.layer3_strategy.rule_engine import RuleEngine
from src.layer2_theory.market_state import MarketTheoryState
from src.layer1_data.models import Candle

def format_color(pnl: float) -> str:
    return "🟢" if pnl >= 0 else "🔴"

def main():
    parser = argparse.ArgumentParser(description="Offline TopstepX Simulator")
    parser.add_argument("--strategy", type=str, required=True, help="Naam van de strategie map in /strategies")
    parser.add_argument("--days", type=int, default=28, help="Aantal dagen terugkijken (default=28)")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    strategy_dir = f"strategies/{args.strategy}"
    playbook_path = f"{strategy_dir}/strategy_playbook.json"
    
    if not os.path.exists(playbook_path):
        logging.error(f"Error: Strategie playbook niet gevonden op {playbook_path}")
        sys.exit(1)
        
    logging.info(f"🚀 Initializing Backtest Engine voor '{args.strategy}'...")
    logging.info(f"⚙️ Config: {playbook_path}")
    
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=args.days)
    
    data_path = "data/backtest/candles/NQ_1min.csv"
    if not os.path.exists(data_path):
        logging.error(f"Error: Historische data niet gevonden op {data_path}. Run build_data_lake.py eerst.")
        sys.exit(1)
        
    logging.info(f"📊 Laden van historische data uit {data_path} (laatste {args.days} dagen)...")
    df = pd.read_csv(data_path)
    df['datetime'] = pd.to_datetime(df['timestamp_ms'], unit='ms', utc=True)
    df = df[(df['datetime'] >= start_date) & (df['datetime'] <= now)]
    
    logging.info(f"✅ Data geladen: {len(df)} candles.")
    logging.info("⏳ Running Fast-Forward Simulation...")
    
    # Inladen van GSD Layer architectuur
    cfg = ConfigParser.load_playbook(playbook_path)
    engine = RuleEngine(cfg)
    vault = DataVault()
    sim = BacktestSimulator(vault)
    
    state = MarketTheoryState()
    
    last_ordered_setup_price = None
    last_ordered_setup_direction = None
    last_trade_count = 0
    
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
        
        # Determine if a trade was closed in the previous cycle
        current_trade_count = len(vault.trades)
        last_trade_result = None
        last_trade_is_bullish = None
        if current_trade_count > last_trade_count:
            last_closed_trade = vault.trades[-1]
            last_trade_result = last_closed_trade.pnl_points
            last_trade_is_bullish = last_closed_trade.is_bullish
            last_trade_count = current_trade_count
            
        # 1. Manage Active Positions - skip new entries if we have a position
        if hasattr(sim, 'active_pos') and sim.active_pos is not None:
             continue
             
        # 2. Evaluate Rule Engine Intents
        intents = engine.evaluate(state, c.timestamp, last_trade_result=last_trade_result, last_trade_is_bullish=last_trade_is_bullish)
        active_intent = intents[-1] if intents else None
        current_setup_price = active_intent.entry_price if active_intent else None
        
        # 3. Check for Pending Entries
        if sim.pending_intent is not None:
            if not active_intent or current_setup_price != sim.pending_intent.entry_price:
                sim.cancel_all()
                if active_intent:
                    last_ordered_setup_price = None
            continue
            
        # 4. Place native brackets
        if active_intent:
            if active_intent.entry_price == last_ordered_setup_price and active_intent.is_bullish == last_ordered_setup_direction:
                continue
                
            sim.stage_order(active_intent)
            last_ordered_setup_price = active_intent.entry_price
            last_ordered_setup_direction = active_intent.is_bullish
            
    logging.info("\n✅ Validatie Voltooid. Analyseren van Trade Ledger...")
    daily_stats = {}
    
    for t in vault.trades:
        # Pakt de exit time of entry time voor de dag logging
        ts = getattr(t, 'exit_time', getattr(t, 'entry_time', None))
        if ts is None:
             continue
        
        day_str = ts.strftime('%Y-%m-%d')
        if day_str not in daily_stats:
            daily_stats[day_str] = {'trades': 0, 'wins': 0, 'losses': 0, 'net_pnl': 0.0}
            
        daily_stats[day_str]['trades'] += 1
        daily_stats[day_str]['net_pnl'] += (t.pnl_points * 20)
        
        # Check derived win flag
        is_win = getattr(t, 'win', t.pnl_points > 0)
        if is_win:
            daily_stats[day_str]['wins'] += 1
        else:
            daily_stats[day_str]['losses'] += 1

    logging.info("\n| Date | Total Trades | Wins | Losses | Net PnL |")
    logging.info("|---|---|---|---|---|")
    for day in sorted(daily_stats.keys()):
        stats = daily_stats[day]
        net = stats['net_pnl']
        color = format_color(net)
        logging.info(f"| {day} | {stats['trades']} | {stats['wins']} | {stats['losses']} | {color} ${net:.2f} |")

    total_trades = sum(d['trades'] for d in daily_stats.values())
    total_wins = sum(d['wins'] for d in daily_stats.values())
    total_net = sum(d['net_pnl'] for d in daily_stats.values())
    win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
    
    daily_pnls = [d['net_pnl'] for d in daily_stats.values()]
    worst_day_pnl = min(daily_pnls) if daily_pnls else 0
    
    # Calculate Max Drawdown from trade-by-trade cumulative PnL
    cumulative_pnl = 0
    peak = 0
    max_drawdown = 0
    
    sorted_trades = sorted(vault.trades, key=lambda t: getattr(t, 'exit_time', getattr(t, 'entry_time', datetime.min.replace(tzinfo=timezone.utc))))
    
    for t in sorted_trades:
        cumulative_pnl += (t.pnl_points * 20)
        if cumulative_pnl > peak:
            peak = cumulative_pnl
        drawdown = peak - cumulative_pnl
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    logging.info("\n==============================================")
    logging.info("📈 SIMULATIE RAPPORT")
    logging.info("==============================================")
    logging.info(f"Strategie:  {args.strategy}")
    logging.info(f"Config:     {playbook_path}")
    logging.info(f"Periode:    Laatste {args.days} dagen")
    logging.info("----------------------------------------------")
    logging.info(f"Totaal Aantal Trades: {total_trades}")
    logging.info(f"Win Rate:             {win_rate:.1f}%")
    logging.info(f"Totaal Netto PnL:     {format_color(total_net)} ${total_net:.2f}")
    logging.info(f"Slechtste Dag PnL:    🔴 ${worst_day_pnl:.2f}")
    logging.info(f"Max Drawdown:         🔴 ${max_drawdown:.2f}")
    logging.info("==============================================\n")

if __name__ == "__main__":
    main()
