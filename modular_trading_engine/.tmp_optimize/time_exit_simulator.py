from typing import Optional, Any
from src.layer1_data.models import Candle
from src.layer3_strategy.models import OrderIntent
from src.layer4_execution.data_vault import DataVault, TradeRecord
from src.layer4_execution.simulator import BacktestSimulator, ActivePosition

class TimeExitBacktestSimulator(BacktestSimulator):
    """
    Subclass that adds a strict time-based exit.
    If a trade is open for X minutes, it is closed at the current candle's close price.
    """
    def __init__(self, vault: DataVault, max_duration_minutes: int = 6):
        super().__init__(vault)
        self.max_duration_minutes = max_duration_minutes

    def _evaluate_active_position(self, candle: Candle) -> None:
        """
        Evaluates an active position against the current incoming candle.
        Closes the position if TP or SL is hit, OR if time limit is reached.
        """
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
            
        tp = intent.take_profit
        sl = pos.current_stop_loss
        
        if intent.is_bullish:
            high_breach = candle.high >= tp
            low_breach = candle.low <= sl
        else:
            high_breach = candle.high >= sl
            low_breach = candle.low <= tp

        # Handle Breakeven target trigger (if configured in base strategy)
        if intent.breakeven_trigger_price is not None and not pos.breakeven_activated:
            trigger_hit = False
            if intent.is_bullish:
                if candle.high >= intent.breakeven_trigger_price:
                    trigger_hit = True
            else:
                if candle.low <= intent.breakeven_trigger_price:
                    trigger_hit = True
                    
            if trigger_hit:
                pos.breakeven_activated = True
                sl = intent.breakeven_target_price
                pos.current_stop_loss = sl
                
        # INTRA-BAR GRANULARITY FIX
        tp_hit = False
        sl_hit = False
        
        if high_breach and low_breach:
            if candle.is_bullish:
                if intent.is_bullish:
                    sl_hit = True
                else:
                    tp_hit = True
            else:
                if intent.is_bullish:
                    tp_hit = True
                else:
                    sl_hit = True
        else:
            if intent.is_bullish:
                tp_hit = high_breach
                sl_hit = low_breach
            else:
                tp_hit = low_breach
                sl_hit = high_breach
                
        # Check Time-based Exit BEFORE intra-bar hits, or if no hit
        duration_minutes = (candle.timestamp - pos.fill_time).total_seconds() / 60.0
        time_exit = False
        
        if duration_minutes >= self.max_duration_minutes:
            # Time limit hit. If it also hit TP or SL in this candle, we might say TP/SL takes precedence,
            # but to be conservative, if it's the 6th minute and we haven't hit anything, we close at the end.
            time_exit = True
            
        if tp_hit and not time_exit:
            self._close_position_standard(candle, pos, is_win=True)
        elif sl_hit and not time_exit:
            self._close_position_standard(candle, pos, is_win=False)
        elif time_exit:
            self._close_position_time(candle, pos)

    def _close_position_standard(self, candle: Candle, pos: ActivePosition, is_win: bool) -> None:
        intent = pos.intent
        if intent.is_bullish:
            exit_price = intent.take_profit if is_win else pos.current_stop_loss
            pnl = exit_price - intent.entry_price
        else:
            exit_price = intent.take_profit if is_win else pos.current_stop_loss
            pnl = intent.entry_price - exit_price
            
        self._record(candle, pos, is_win, pnl, exit_price)

    def _close_position_time(self, candle: Candle, pos: ActivePosition) -> None:
        intent = pos.intent
        exit_price = candle.close
        if intent.is_bullish:
            pnl = exit_price - intent.entry_price
        else:
            pnl = intent.entry_price - exit_price
            
        is_win = pnl > 0
        self._record(candle, pos, is_win, pnl, exit_price, note="Time Exit")

    def _record(self, candle: Candle, pos: ActivePosition, is_win: bool, pnl: float, exit_price: float, note: str = "") -> None:
        intent = pos.intent
        record = TradeRecord(
            strategy_id=intent.strategy_id,
            is_bullish=intent.is_bullish,
            entry_time=pos.fill_time, 
            exit_time=candle.timestamp,
            entry_price=intent.entry_price,
            stop_loss=pos.current_stop_loss,
            take_profit=intent.take_profit,
            mfe=pos.mfe,
            mae=pos.mae,
            win=is_win,
            pnl_points=pnl
        )
        if note:
            # Hack to attach note, TradeRecord doesn't have a note field natively
            pass
            
        self.vault.log_trade(record)
        self.active_pos = None

