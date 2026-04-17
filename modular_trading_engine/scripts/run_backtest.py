import argparse
import sys
from pathlib import Path
from datetime import datetime

# Zorg ervoor dat Python src kan vinden ongeacht van waar het script runt
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.layer1_data.csv_parser import load_historical_1m_data
from src.layer2_theory.market_state import MarketTheoryState
from src.layer3_strategy.config_parser import ConfigParser
from src.layer3_strategy.rule_engine import RuleEngine
from src.layer4_execution.data_vault import DataVault
from src.layer4_execution.simulator import BacktestSimulator

def run_backtest(data_file: Path, playbook_file: Path):
    print(f"[{datetime.now().time()}] Starting Day Trading Decrypted modular backtest...")
    print(f"[{datetime.now().time()}] Loading Dataset: {data_file.name}")
    print(f"[{datetime.now().time()}] Loading Playbook: {playbook_file.name}")
    
    # 1. Pipeline Initialization
    # Layer 1: Ingestion
    candles = load_historical_1m_data(data_file)
    print(f"[{datetime.now().time()}] Ingested {len(candles)} historical candles.")
    
    # Layer 2: Core Domain Logic
    theory_state = MarketTheoryState()
    
    # Layer 3: Rule & Strategy config
    playbook_config = ConfigParser.load_playbook(str(playbook_file))
    rule_engine = RuleEngine(playbook_config)
    
    # Layer 4: Execution Simulation & Archiving
    data_vault = DataVault()
    simulator = BacktestSimulator(vault=data_vault)
    
    print(f"[{datetime.now().time()}] Entering event loop...")
    
    # 2. Main Event Loop
    for candle in candles:
        # A. Update Theory State (Creates/Invalidates Levels)
        theory_state.process_candle(candle)
        
        # B. Strategy Logic (Do we have an Order Intent?)
        intents = rule_engine.evaluate(theory_state=theory_state, timestamp=candle.timestamp)
        
        # C. Execution Environment (Can we fill limits? Track open trades)
        for intent in intents:
            simulator.stage_order(intent)
            
        simulator.process_candle(candle)

    # 3. Print the results
    print(f"\n==============================================")
    print(f"BACKTEST REPORT: {playbook_config.strategy_id}")
    print(f"==============================================")
    
    trades = data_vault.trades
    total_trades = len(trades)
    
    if total_trades == 0:
        print("No trades were placed during this simulation.")
        return
        
    wins = [t for t in trades if t.win]
    losses = [t for t in trades if not t.win]
    
    win_rate = (len(wins) / total_trades) * 100
    
    # Calc PNL
    total_pnl_points = sum(t.pnl_points for t in trades)
    
    # Calc Max Drawdown
    max_drawdown = 0.0
    peak = 0.0
    cumulative = 0.0
    for t in trades:
        cumulative += t.pnl_points
        if cumulative > peak:
            peak = cumulative
        drawdown = peak - cumulative
        if drawdown > max_drawdown:
            max_drawdown = drawdown
            
    print(f"Total Completed Trades : {total_trades}")
    print(f"Win Rate               : {win_rate:.2f}% ({len(wins)}W / {len(losses)}L)")
    print(f"Total Capture (Points) : {total_pnl_points:.2f} PTS")
    print(f"Max Drawdown (Points)  : {max_drawdown:.2f} PTS")
    
    print("\nRecent 5 Trades:")
    for t in trades[-5:]:
        outcome = "WIN" if t.win else "LOSS"
        direction = "LONG" if t.is_bullish else "SHORT"
        print(f" [{t.entry_time.strftime('%Y-%m-%d %H:%M')}] {direction} @ {t.entry_price:.2f} => {outcome} ({t.pnl_points:+.2f} pts) | MFE: {t.mfe:.2f}, MAE: {t.mae:.2f}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Modular Core Lab Backtest Runner")
    parser.add_argument(
        '--data', 
        type=str, 
        default='data/historical/NQ_1min.csv',
        help='Path to the historical CSV file'
    )
    parser.add_argument(
        '--strategy', 
        type=str, 
        default='dtd_golden_setup',
        help='Name of the strategy container to backtest (folder name in strategies/)'
    )
    args = parser.parse_args()
    
    data_path = project_root / args.data
    playbook_path = project_root / 'strategies' / args.strategy / 'strategy_playbook.json'
    
    run_backtest(data_path, playbook_path)
