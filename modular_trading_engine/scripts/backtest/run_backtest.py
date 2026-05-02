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

from src.layer4_execution.backtest_engine import BacktestSession

def main():
    parser = argparse.ArgumentParser(description="Offline TopstepX Simulator (Standardized Workflow)")
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
    logging.info("⏳ Running Fast-Forward Simulation (1-by-1)...")
    
    session = BacktestSession(playbook_path=playbook_path)
    report = session.run(df)
    session.print_report(report)
    
if __name__ == "__main__":
    main()
