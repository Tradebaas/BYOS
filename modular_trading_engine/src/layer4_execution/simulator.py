from typing import Optional

from src.layer1_data.models import Candle
from src.layer3_strategy.models import OrderIntent
from src.layer4_execution.data_vault import DataVault, TradeRecord

class ActivePosition:
    def __init__(self, intent: OrderIntent, fill_time: float):
        self.intent = intent
        self.fill_time = fill_time
        
        # Initial bounds
        self.mfe = intent.entry_price
        self.mae = intent.entry_price

class BacktestSimulator:
    """
    Virtual Execution Engine running on M1 Candles.
    Responsible for executing Limit Orders and registering Gray Candles properly.
    """
    def __init__(self, vault: DataVault):
        self.vault = vault
        self.pending_intent: Optional[OrderIntent] = None
        self.active_pos: Optional[ActivePosition] = None
        
    def stage_order(self, intent: OrderIntent) -> None:
        """Called by Layer 3 to submit a new limit order."""
        if self.active_pos is None:
            self.pending_intent = intent
            
    def process_candle(self, candle: Candle) -> None:
        """
        The heartbeat of the backtester. Processes the new market data sequentially.
        """
        # Phase 1: Handle OPEN position (update metrics, check exits)
        if self.active_pos is not None:
            self._evaluate_active_position(candle)
            return  # If we have an active position, we don't process new entries on the same tick
            
        # Phase 2: Handle PENDING order (check for limit fills)
        if self.pending_intent is not None:
            self._evaluate_pending_order(candle)
            
    def _evaluate_pending_order(self, candle: Candle) -> None:
        intent = self.pending_intent
        is_filled = False
        
        if intent.is_bullish:
            # Bullish limit filled if market low touches or breaches the bid
            is_filled = candle.low <= intent.entry_price
        else:
            # Bearish limit filled if market high touches or breaches the ask
            is_filled = candle.high >= intent.entry_price
            
        if is_filled:
            self.active_pos = ActivePosition(intent=intent, fill_time=candle.timestamp.timestamp())
            self.pending_intent = None
            
            # CRITICAL: We just got filled inside this M1 candle. 
            # We must immediately evaluate the REST of the candle to see if we also hit SL/TP inside the entry minute.
            self._evaluate_active_position(candle)

    def _evaluate_active_position(self, candle: Candle) -> None:
        pos = self.active_pos
        intent = pos.intent
        
        # 1. Update MAE/MFE continuously based on candle extremes
        if intent.is_bullish:
            if candle.high > pos.mfe: pos.mfe = candle.high
            if candle.low < pos.mae: pos.mae = candle.low
            
            hit_sl = candle.low <= intent.stop_loss
            hit_tp = candle.high >= intent.take_profit
        else:
            if candle.low < pos.mfe: pos.mfe = candle.low
            if candle.high > pos.mae: pos.mae = candle.high
            
            hit_sl = candle.high >= intent.stop_loss
            hit_tp = candle.low <= intent.take_profit
            
        # 2. Strict CCTA constraints for Gray Candles (worst-case assumption)
        if hit_sl and hit_tp:
            # Both levels hit in a single bar. Assume Stop Loss was struck first per safety rules.
            self._close_position(candle, pos, is_win=False)
        elif hit_sl:
            self._close_position(candle, pos, is_win=False)
        elif hit_tp:
            self._close_position(candle, pos, is_win=True)

    def _close_position(self, candle: Candle, pos: ActivePosition, is_win: bool) -> None:
        intent = pos.intent
        
        # Absolute points captured/lost
        if is_win:
            pnl = abs(intent.take_profit - intent.entry_price)
        else:
            pnl = -abs(intent.entry_price - intent.stop_loss)
            
        record = TradeRecord(
            strategy_id=intent.strategy_id,
            is_bullish=intent.is_bullish,
            entry_time=intent.timestamp, # Record intent generation time
            exit_time=candle.timestamp,
            entry_price=intent.entry_price,
            stop_loss=intent.stop_loss,
            take_profit=intent.take_profit,
            mfe=pos.mfe,
            mae=pos.mae,
            win=is_win,
            pnl_points=pnl
        )
        
        self.vault.log_trade(record)
        self.active_pos = None
