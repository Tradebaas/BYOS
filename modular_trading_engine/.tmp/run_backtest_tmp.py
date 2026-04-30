import os
import sys
import argparse
import pandas as pd
import logging
from datetime import datetime, timedelta, timezone

# Ensure engine root is on sys.path (works from any CWD)
_engine_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
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
    parser.add_argument("--playbook", type=str, required=True, help="Path to playbook json")
    parser.add_argument("--days", type=int, default=0, help="Aantal dagen terugkijken (default=0)")
    parser.add_argument("--start_date", type=str, default="", help="Start datum in YYYY-MM-DD")
    parser.add_argument("--end_date", type=str, default="", help="End datum in YYYY-MM-DD")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    playbook_path = args.playbook
    
    if not os.path.exists(playbook_path):
        logging.error(f"Error: Strategie playbook niet gevonden op {playbook_path}")
        sys.exit(1)
        
    logging.info(f"🚀 Initializing Backtest Engine voor '{playbook_path}'...")
    logging.info(f"⚙️ Config: {playbook_path}")
    
    now = datetime.now(timezone.utc)
    
    if args.start_date:
        start_date = pd.to_datetime(args.start_date).replace(tzinfo=timezone.utc)
        if args.end_date:
            end_date = pd.to_datetime(args.end_date).replace(tzinfo=timezone.utc)
        else:
            end_date = now
    else:
        if args.days > 0:
            start_date = now - timedelta(days=args.days)
        else:
            start_date = datetime.min.replace(tzinfo=timezone.utc)
        end_date = now
    
    data_path = "data/backtest/candles/NQ_1min.csv"
    if not os.path.exists(data_path):
        logging.error(f"Error: Historische data niet gevonden op {data_path}. Run build_data_lake.py eerst.")
        sys.exit(1)
        
    logging.info(f"📊 Laden van historische data uit {data_path} ({start_date.strftime('%Y-%m-%d')} tot {end_date.strftime('%Y-%m-%d')})...")
    df = pd.read_csv(data_path)
    df['datetime'] = pd.to_datetime(df['timestamp_ms'], unit='ms', utc=True)
    df = df[(df['datetime'] >= start_date) & (df['datetime'] <= end_date)]
    
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
            daily_stats[day_str] = {'trades': 0, 'wins': 0, 'losses': 0, 'bes': 0, 'net_pnl': 0.0}
            
        daily_stats[day_str]['trades'] += 1
        daily_stats[day_str]['net_pnl'] += (t.pnl_points * 40.0)
        
        # Determine outcome
        if t.pnl_points > 5:
            daily_stats[day_str]['wins'] += 1
        elif t.pnl_points > -5:
            daily_stats[day_str]['bes'] += 1
        else:
            daily_stats[day_str]['losses'] += 1

    monthly_stats = {}
    for day in daily_stats:
        month = day[:7] # YYYY-MM
        if month not in monthly_stats:
            monthly_stats[month] = {'trades': 0, 'wins': 0, 'bes': 0, 'losses': 0, 'net_pnl': 0.0}
        
        monthly_stats[month]['trades'] += daily_stats[day]['trades']
        monthly_stats[month]['wins'] += daily_stats[day]['wins']
        monthly_stats[month]['bes'] += daily_stats[day]['bes']
        monthly_stats[month]['losses'] += daily_stats[day]['losses']
        monthly_stats[month]['net_pnl'] += daily_stats[day]['net_pnl']

    logging.info("\n| Month | Total Trades | Wins | BEs | Losses | Win Rate | Net PnL |")
    logging.info("|---|---|---|---|---|---|---|")
    for month in sorted(monthly_stats.keys()):
        stats = monthly_stats[month]
        net = stats['net_pnl']
        color = format_color(net)
        wr = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
        logging.info(f"| {month} | {stats['trades']} | {stats['wins']} | {stats['bes']} | {stats['losses']} | {wr:.1f}% | {color} ${net:.2f} |")

    total_trades = sum(d['trades'] for d in daily_stats.values())
    total_wins = sum(d['wins'] for d in daily_stats.values())
    total_bes = sum(d['bes'] for d in daily_stats.values())
    total_losses = sum(d['losses'] for d in daily_stats.values())
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
        cumulative_pnl += (t.pnl_points * 40.0)
        if cumulative_pnl > peak:
            peak = cumulative_pnl
        drawdown = peak - cumulative_pnl
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    logging.info("\n==============================================")
    logging.info("📈 SIMULATIE RAPPORT")
    logging.info("==============================================")
    logging.info(f"Strategie:  {playbook_path}")
    logging.info(f"Config:     {playbook_path}")
    logging.info(f"Periode:    Laatste {args.days} dagen")
    logging.info("----------------------------------------------")
    logging.info(f"Totaal Aantal Trades: {total_trades}")
    logging.info(f"Wins:                 {total_wins}")
    logging.info(f"Break Evens (BE):     {total_bes}")
    logging.info(f"Losses:               {total_losses}")
    logging.info(f"Win Rate:             {win_rate:.1f}%")
    logging.info(f"Totaal Netto PnL:     {format_color(total_net)} ${total_net:.2f}")
    logging.info(f"Slechtste Dag PnL:    🔴 ${worst_day_pnl:.2f}")
    logging.info(f"Max Drawdown:         🔴 ${max_drawdown:.2f}")
    logging.info("==============================================\n")

    # Export to CSV for analysis
    data = []
    for t in sorted_trades:
        entry_time = getattr(t, 'entry_time', None)
        if not entry_time: continue
        pnl = t.pnl_points
        if pnl > 5: outcome = 'WIN'
        elif pnl > -5: outcome = 'BE'
        else: outcome = 'LOSS'
        
        is_bullish = getattr(t, 'is_bullish', True)
        exit_price = t.entry_price + pnl if is_bullish else t.entry_price - pnl

        data.append({
            'entry_time': entry_time,
            'exit_time': getattr(t, 'exit_time', None),
            'direction': 'LONG' if is_bullish else 'SHORT',
            'entry_price': t.entry_price,
            'exit_price': exit_price,
            'pnl': pnl,
            'mfe': getattr(t, 'mfe', 0.0),
            'mae': getattr(t, 'mae', 0.0),
            'outcome': outcome
        })
    df = pd.DataFrame(data)
    df.to_csv('.tmp_optimize/trades_export.csv', index=False)
    logging.info("💾 Alle trades geëxporteerd naar .tmp_optimize/trades_export.csv")

if __name__ == "__main__":
    main()
