import os
import sys
import pandas as pd
import logging
from datetime import datetime, timedelta, timezone

_engine_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _engine_root not in sys.path:
    sys.path.insert(0, _engine_root)
os.chdir(_engine_root)

from src.layer4_execution.simulator import BacktestSimulator, ActivePosition
from src.layer4_execution.data_vault import DataVault, TradeRecord
from src.layer3_strategy.config_parser import ConfigParser
from src.layer3_strategy.rule_engine import RuleEngine
from src.layer2_theory.market_state import MarketTheoryState
from src.layer1_data.models import Candle

class SteppingSimulator(BacktestSimulator):
    def _evaluate_active_position(self, candle: Candle) -> None:
        pos = self.active_pos
        if not pos:
            return
            
        intent = pos.intent
        
        # 1. Update MAE/MFE continuously based on candle extremes
        if intent.is_bullish:
            if candle.high > pos.mfe: pos.mfe = candle.high
            if candle.low < pos.mae: pos.mae = candle.low
        else:
            if candle.low < pos.mfe: pos.mfe = candle.low
            if candle.high > pos.mae: pos.mae = candle.high
            
        # STEPPING TRAIL LOGIC
        # Step size: 6 NQ points
        STEP_POINTS = 6.0
        
        # Compute maximum profit reached
        if intent.is_bullish:
            max_profit = pos.mfe - intent.entry_price
            step = int(max_profit // STEP_POINTS)
            if step >= 1:
                # at step=1 (+6), SL = entry + 0*6 = entry (breakeven)
                # at step=2 (+12), SL = entry + 1*6 = +6
                new_sl = intent.entry_price + (step - 1) * STEP_POINTS
                if pos.current_stop_loss is None or new_sl > pos.current_stop_loss:
                    pos.current_stop_loss = new_sl
        else:
            max_profit = intent.entry_price - pos.mfe
            step = int(max_profit // STEP_POINTS)
            if step >= 1:
                new_sl = intent.entry_price - (step - 1) * STEP_POINTS
                if pos.current_stop_loss is None or new_sl < pos.current_stop_loss:
                    pos.current_stop_loss = new_sl

        # OVERRIDE: TP is always entry + 80 points
        if intent.is_bullish:
            tp = intent.entry_price + 80.0
        else:
            tp = intent.entry_price - 80.0
            
        sl = pos.current_stop_loss
        
        if intent.is_bullish:
            high_breach = candle.high >= tp
            low_breach = candle.low <= sl
        else:
            high_breach = candle.high >= sl
            low_breach = candle.low <= tp

        # Intra-bar check
        tp_hit = False
        sl_hit = False
        
        if high_breach and low_breach:
            if candle.is_bullish:
                if intent.is_bullish: sl_hit = True
                else: tp_hit = True
            else:
                if intent.is_bullish: tp_hit = True
                else: sl_hit = True
        else:
            if intent.is_bullish:
                tp_hit = high_breach
                sl_hit = low_breach
            else:
                tp_hit = low_breach
                sl_hit = high_breach
                
        if tp_hit:
            self._close_position_custom(candle, pos, tp, True)
        elif sl_hit:
            self._close_position_custom(candle, pos, sl, False)

    def _close_position_custom(self, candle: Candle, pos: ActivePosition, exit_price: float, is_win: bool) -> None:
        intent = pos.intent
        
        if intent.is_bullish:
            pnl = exit_price - intent.entry_price
        else:
            pnl = intent.entry_price - exit_price
            
        # Hardcode the record since we override exit_price
        record = TradeRecord(
            strategy_id=intent.strategy_id,
            is_bullish=intent.is_bullish,
            entry_time=pos.fill_time, 
            exit_time=candle.timestamp,
            entry_price=intent.entry_price,
            stop_loss=pos.current_stop_loss,
            take_profit=exit_price if is_win else intent.take_profit, # log actual exit
            mfe=pos.mfe,
            mae=pos.mae,
            win=(pnl > 0),
            pnl_points=pnl
        )
        
        self.vault.log_trade(record)
        self.active_pos = None

def format_color(pnl: float) -> str:
    return "🟢" if pnl >= 0 else "🔴"

def run_stepping_backtest():
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    strategy_dir = "strategies/dtd_golden_setup"
    playbook_path = f"{strategy_dir}/strategy_playbook.json"
    
    if not os.path.exists(playbook_path):
        logging.error(f"Playbook not found: {playbook_path}")
        return
        
    logging.info(f"Running Stepping Trailing Backtest for {strategy_dir}")
    
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=28)
    data_path = "data/backtest/candles/NQ_1min.csv"
    
    df = pd.read_csv(data_path)
    df['datetime'] = pd.to_datetime(df['timestamp_ms'], unit='ms', utc=True)
    df = df[(df['datetime'] >= start_date) & (df['datetime'] <= now)]
    
    cfg = ConfigParser.load_playbook(playbook_path)
    engine = RuleEngine(cfg)
    vault = DataVault()
    sim = SteppingSimulator(vault)
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
            
    # Calculate stats
    daily_stats = {}
    
    for t in vault.trades:
        ts = getattr(t, 'exit_time', getattr(t, 'entry_time', None))
        if ts is None: continue
        
        day_str = ts.strftime('%Y-%m-%d')
        if day_str not in daily_stats:
            daily_stats[day_str] = {'trades': 0, 'wins': 0, 'losses': 0, 'net_pnl': 0.0}
            
        daily_stats[day_str]['trades'] += 1
        daily_stats[day_str]['net_pnl'] += (t.pnl_points * 20)
        
        if t.pnl_points > 0:
            daily_stats[day_str]['wins'] += 1
        else:
            daily_stats[day_str]['losses'] += 1

    logging.info("\n| Date | Total Trades | Wins | Losses | Net PnL |")
    logging.info("|---|---|---|---|---|")
    for day in sorted(daily_stats.keys()):
        stats = daily_stats[day]
        net = stats['net_pnl']
        logging.info(f"| {day} | {stats['trades']} | {stats['wins']} | {stats['losses']} | {format_color(net)} ${net:.2f} |")

    total_trades = sum(d['trades'] for d in daily_stats.values())
    total_wins = sum(d['wins'] for d in daily_stats.values())
    total_net = sum(d['net_pnl'] for d in daily_stats.values())
    win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
    
    cumulative_pnl = 0
    peak = 0
    max_drawdown = 0
    
    for t in sorted(vault.trades, key=lambda x: getattr(x, 'exit_time', x.entry_time)):
        cumulative_pnl += (t.pnl_points * 20)
        if cumulative_pnl > peak:
            peak = cumulative_pnl
        drawdown = peak - cumulative_pnl
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    logging.info("\n==============================================")
    logging.info("📈 SIMULATIE RAPPORT - STEPPING TRAILING")
    logging.info("==============================================")
    logging.info(f"Totaal Aantal Trades: {total_trades}")
    logging.info(f"Win Rate:             {win_rate:.1f}%")
    logging.info(f"Totaal Netto PnL:     {format_color(total_net)} ${total_net:.2f}")
    logging.info(f"Max Drawdown:         🔴 ${max_drawdown:.2f}")
    logging.info("==============================================\n")

if __name__ == '__main__':
    run_stepping_backtest()
