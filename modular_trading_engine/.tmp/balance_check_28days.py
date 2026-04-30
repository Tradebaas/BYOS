import os
import sys
import pandas as pd
from datetime import datetime, timedelta, timezone

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
from src.layer3_strategy.modules.loss_cooldown_filter import LossCooldownFilter

def run_simulation(playbook_path, data_path, start_date_str, end_date_str):
    df = pd.read_csv(data_path)
    df['datetime'] = pd.to_datetime(df['timestamp_ms'], unit='ms', utc=True)
    
    start_date = pd.to_datetime(start_date_str, utc=True)
    end_date = pd.to_datetime(end_date_str, utc=True)
    df = df[(df['datetime'] >= start_date) & (df['datetime'] <= end_date)]

    LossCooldownFilter._last_loss_time.clear()

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

    multiplier = 20  # 1 NQ contract = $20 per point
    balance = 50000.0
    peak_balance = 50000.0
    max_drawdown = 0.0
    
    wins = 0
    losses = 0
    
    sorted_trades = sorted(vault.trades, key=lambda t: getattr(t, 'exit_time', getattr(t, 'entry_time', datetime.min.replace(tzinfo=timezone.utc))))
    
    print("=====================================================================================================")
    print(f"{'Exit Time (UTC)':<20} | {'Type':<6} | {'Entry':<8} | {'Exit':<8} | {'MAE (pts)':<10} | {'PnL (pts)':<10} | {'PnL ($)':<8} | {'Balance':<10}")
    print("-----------------------------------------------------------------------------------------------------")
    
    for t in sorted_trades:
        exit_price = getattr(t, 'exit_price', None)
        if exit_price is None:
            if t.is_bullish:
                exit_price = t.entry_price + t.pnl_points
            else:
                exit_price = t.entry_price - t.pnl_points
                
        # Calculate maximum floating drawdown using MAE
        if t.is_bullish:
            mae_points = t.entry_price - t.mae if t.mae < t.entry_price else 0
        else:
            mae_points = t.mae - t.entry_price if t.mae > t.entry_price else 0
            
        floating_loss_usd = mae_points * multiplier
        floating_balance = balance - floating_loss_usd
        
        current_floating_drawdown = peak_balance - floating_balance
        if current_floating_drawdown > max_drawdown:
            max_drawdown = current_floating_drawdown
            
        pnl_usd = t.pnl_points * multiplier
        balance += pnl_usd
        
        if pnl_usd >= 0:
            wins += 1
        else:
            losses += 1
        
        # After trade is closed, check if new peak is reached
        if balance > peak_balance:
            peak_balance = balance
            
        direction = "LONG" if t.is_bullish else "SHORT"
        exit_time_str = t.exit_time.strftime('%Y-%m-%d %H:%M')
        
        print(f"{exit_time_str:<20} | {direction:<6} | {t.entry_price:<8.2f} | {exit_price:<8.2f} | {mae_points:<10.2f} | {t.pnl_points:<10.2f} | {pnl_usd:<8.2f} | {balance:<10.2f}")
        
    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    
    print("=====================================================================================================")
    print(f"Total Trades: {total_trades}")
    print(f"Wins (incl. Break-Even): {wins}")
    print(f"Losses: {losses}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Start Saldo: $50000.00")
    print(f"Eind Saldo: ${balance:.2f}")
    print(f"Totale PnL: ${(balance - 50000.00):.2f}")
    print(f"Max Floating Drawdown vanaf peak: ${max_drawdown:.2f}")

if __name__ == '__main__':
    data_path = "data/backtest/candles/NQ_1min.csv"
    playbook = ".tmp/strategy_playbook_12_fixed.json"
    start_date = "2026-04-01 00:00:00"
    end_date = "2026-04-29 23:59:59"
    run_simulation(playbook, data_path, start_date, end_date)
