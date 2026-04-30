import os
import sys
import json
import pandas as pd
from datetime import timedelta
from pathlib import Path

_engine_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _engine_root not in sys.path:
    sys.path.insert(0, _engine_root)
os.chdir(_engine_root)

from src.layer1_data.models import Candle
from scripts.live.run_live_bot_smc import SMCTheoryState, SMCRuleEngine

def load_data():
    df = pd.read_csv("data/backtest/candles/NQ_1min.csv")
    df['datetime_utc'] = pd.to_datetime(df['datetime_utc'])
    df = df.sort_values('datetime_utc').reset_index(drop=True)
    return df

def run_backtest():
    # Load Playbook
    playbook_path = Path(_engine_root) / "strategies" / "smc_holy_grail" / "strategy_playbook.json"
    with open(playbook_path, "r") as f:
        playbook_config = json.load(f)
        
    print(f"Playbook loaded. Setup: {playbook_config['pipeline'][0]['params']['setup_type']}")

    theory_state = SMCTheoryState(playbook_config)
    rule_engine = SMCRuleEngine(playbook_config)
    
    # We also need to emulate the account manager limits
    max_trades_per_day = playbook_config['pipeline'][0]['params'].get('max_trades_per_day', 999)
    print(f"Max trades per day: {max_trades_per_day}")
    
    df = load_data()
    print(f"Loaded {len(df)} candles.")
    
    in_trade = False
    trade_dir = 0
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0
    
    total_trades = 0
    winning_trades = 0
    losing_trades = 0
    dubious_trades = 0
    pnl = 0.0
    max_dd = 0.0
    peak_pnl = 0.0
    
    current_day = -1
    trades_today = 0
    
    for idx, row in df.iterrows():
        # Build Candle
        c = Candle(
            timestamp=row['datetime_utc'],
            open=row['open'],
            high=row['high'],
            low=row['low'],
            close=row['close'],
            volume=row['volume']
        )
        
        day = c.timestamp.day
        if day != current_day:
            current_day = day
            trades_today = 0
            
        theory_state.process_candle(c)
        
        if in_trade:
            hit_tp = False
            hit_sl = False
            
            if trade_dir == 1:
                if c.high >= tp_price: hit_tp = True
                if c.low <= sl_price: hit_sl = True
            else:
                if c.low <= tp_price: hit_tp = True
                if c.high >= sl_price: hit_sl = True
                
            if hit_tp and hit_sl:
                dubious_trades += 1
                hit_tp = False
                hit_sl = True
                
            if hit_sl:
                losing_trades += 1
                loss_pts = entry_price - sl_price if trade_dir == 1 else sl_price - entry_price
                pnl -= (loss_pts * 20.0)
                in_trade = False
                theory_state.bullish_sweep_active = False 
                theory_state.bearish_sweep_active = False
                
            elif hit_tp:
                winning_trades += 1
                win_pts = tp_price - entry_price if trade_dir == 1 else entry_price - tp_price
                pnl += (win_pts * 20.0)
                in_trade = False
                theory_state.bullish_sweep_active = False 
                theory_state.bearish_sweep_active = False
                
            if pnl > peak_pnl:
                peak_pnl = pnl
            current_dd = peak_pnl - pnl
            if current_dd > max_dd:
                max_dd = current_dd
                
            continue

        if trades_today >= max_trades_per_day:
            continue
            
        if not in_trade:
            intents = rule_engine.evaluate(theory_state, c.timestamp)
            if intents:
                # We have an active Limit Order intent
                active_intent = intents[-1]
                
                # Check if this candle fills the limit order
                if active_intent.is_bullish:
                    if c.low <= active_intent.entry_price:
                        in_trade = True
                        trade_dir = 1
                        # The entry price is exactly our limit price (or slightly better, but we take the limit price)
                        entry_price = active_intent.entry_price
                        sl_price = active_intent.stop_loss
                        tp_price = active_intent.take_profit
                        trades_today += 1
                        total_trades += 1
                        # Clear FVGs to emulate what SMCAccountManager does upon fill
                        theory_state.active_bullish_fvg = None
                        theory_state.active_bearish_fvg = None
                else:
                    if c.high >= active_intent.entry_price:
                        in_trade = True
                        trade_dir = -1
                        entry_price = active_intent.entry_price
                        sl_price = active_intent.stop_loss
                        tp_price = active_intent.take_profit
                        trades_today += 1
                        total_trades += 1
                        # Clear FVGs
                        theory_state.active_bullish_fvg = None
                        theory_state.active_bearish_fvg = None

    winrate = (winning_trades / (winning_trades + losing_trades) * 100) if (winning_trades + losing_trades) > 0 else 0
    print("\nLive Flow Backtest Parity Check Results:")
    print("-" * 40)
    print(f"Total Trades: {total_trades}")
    print(f"Wins:         {winning_trades}")
    print(f"Losses:       {losing_trades}")
    print(f"Dubious:      {dubious_trades}")
    print(f"Winrate:      {winrate:.2f}%")
    print(f"PnL:          ${pnl:.2f}")
    print(f"Max DD:       ${max_dd:.2f}")
    print("-" * 40)

if __name__ == "__main__":
    run_backtest()
