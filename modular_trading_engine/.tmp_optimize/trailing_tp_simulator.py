"""
Trailing Take-Profit Simulator Variants
========================================
All variants inherit from BacktestSimulator and override _evaluate_active_position.

Strategy: Once price moves X points in our favor (the "activation threshold"),
we start trailing the stop-loss behind price at a distance of Y points.
The original TP is REMOVED — we let the market run and the trailing stop catches us.

Variants tested:
  A) Activate at 6pt MFE, trail at 4pt distance   (conservative)
  B) Activate at 8pt MFE, trail at 4pt distance   (moderate)  
  C) Activate at 6pt MFE, trail at 6pt distance   (loose trail)
  D) Activate at 4pt MFE, trail at 3pt distance   (aggressive scalp)
  E) Hybrid: Keep 12pt TP, but move SL to BE at 6pt MFE (breakeven shield only)
"""

from typing import Optional, Any
from src.layer1_data.models import Candle
from src.layer3_strategy.models import OrderIntent
from src.layer4_execution.data_vault import DataVault, TradeRecord
from src.layer4_execution.simulator import BacktestSimulator, ActivePosition


class TrailingActivePosition(ActivePosition):
    """Extended position tracker with trailing stop state."""
    def __init__(self, intent: OrderIntent, fill_time: Any):
        super().__init__(intent, fill_time)
        self.trailing_activated = False
        self.trailing_stop = None  # The dynamic trailing stop price


class TrailingTPSimulator(BacktestSimulator):
    """
    Trailing Take-Profit Simulator.
    
    Once MFE reaches `activation_points` from entry, the original TP is disabled
    and a trailing stop is placed `trail_distance` points behind the current best price.
    The trailing stop ratchets — it only moves in the favorable direction, never backwards.
    """
    def __init__(self, vault: DataVault, activation_points: float = 6.0, 
                 trail_distance: float = 4.0, keep_original_tp: bool = False):
        super().__init__(vault)
        self.activation_points = activation_points
        self.trail_distance = trail_distance
        self.keep_original_tp = keep_original_tp  # If True, original TP stays active (hybrid mode)
    
    def _evaluate_pending_order(self, candle: Candle) -> None:
        """Override to create TrailingActivePosition instead of ActivePosition."""
        intent = self.pending_intent
        is_filled = False
        
        if intent.is_bullish:
            is_filled = candle.low <= intent.entry_price
        else:
            is_filled = candle.high >= intent.entry_price
            
        if is_filled:
            self.active_pos = TrailingActivePosition(intent=intent, fill_time=candle.timestamp)
            self.pending_intent = None
            
            remainder_high = candle.high
            remainder_low = candle.low
            
            if candle.is_bullish:
                if intent.is_bullish:
                    remainder_low = intent.entry_price
                else:
                    remainder_low = min(intent.entry_price, candle.close)
            else:
                if intent.is_bullish:
                    remainder_high = max(intent.entry_price, candle.close)
                else:
                    remainder_high = intent.entry_price
                    
            remainder_candle = Candle(
                timestamp=candle.timestamp,
                open=intent.entry_price,
                high=remainder_high,
                low=remainder_low,
                close=candle.close,
                volume=0
            )                    
            self._evaluate_active_position(remainder_candle)
    
    def _evaluate_active_position(self, candle: Candle) -> None:
        pos = self.active_pos
        if not pos:
            return
            
        intent = pos.intent
        
        # 1. Update MAE/MFE
        if intent.is_bullish:
            if candle.high > pos.mfe: pos.mfe = candle.high
            if candle.low < pos.mae: pos.mae = candle.low
        else:
            if candle.low < pos.mfe: pos.mfe = candle.low
            if candle.high > pos.mae: pos.mae = candle.high
        
        # 2. Calculate current MFE distance from entry
        if intent.is_bullish:
            mfe_distance = pos.mfe - intent.entry_price
        else:
            mfe_distance = intent.entry_price - pos.mfe
            
        # 3. Check trailing activation
        if hasattr(pos, 'trailing_activated') and not pos.trailing_activated:
            if mfe_distance >= self.activation_points:
                pos.trailing_activated = True
                # Set initial trailing stop
                if intent.is_bullish:
                    pos.trailing_stop = pos.mfe - self.trail_distance
                else:
                    pos.trailing_stop = pos.mfe + self.trail_distance
        
        # 4. Update trailing stop (ratchet only in favorable direction)
        if hasattr(pos, 'trailing_activated') and pos.trailing_activated:
            if intent.is_bullish:
                new_trail = pos.mfe - self.trail_distance
                if pos.trailing_stop is None or new_trail > pos.trailing_stop:
                    pos.trailing_stop = new_trail
            else:
                new_trail = pos.mfe + self.trail_distance
                if pos.trailing_stop is None or new_trail < pos.trailing_stop:
                    pos.trailing_stop = new_trail
        
        # 5. Determine exit conditions
        sl = pos.current_stop_loss  # Original SL
        tp = intent.take_profit      # Original TP
        
        # If trailing is active, use trailing stop instead of original SL
        if hasattr(pos, 'trailing_activated') and pos.trailing_activated:
            sl = pos.trailing_stop
            if not self.keep_original_tp:
                tp = None  # Remove TP, let trail catch it
        
        # Evaluate hits
        tp_hit = False
        sl_hit = False
        
        if tp is not None:
            if intent.is_bullish:
                high_breach = candle.high >= tp
                low_breach = candle.low <= sl
            else:
                high_breach = candle.high >= sl
                low_breach = candle.low <= tp
                
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
        else:
            # No TP — only check SL (trailing stop)
            if intent.is_bullish:
                sl_hit = candle.low <= sl
            else:
                sl_hit = candle.high >= sl
        
        if tp_hit:
            self._close_trailing(candle, pos, exit_price=intent.take_profit)
        elif sl_hit:
            self._close_trailing(candle, pos, exit_price=sl)
    
    def _close_trailing(self, candle: Candle, pos, exit_price: float) -> None:
        intent = pos.intent
        if intent.is_bullish:
            pnl = exit_price - intent.entry_price
        else:
            pnl = intent.entry_price - exit_price
            
        is_win = pnl > 0
        
        record = TradeRecord(
            strategy_id=intent.strategy_id,
            is_bullish=intent.is_bullish,
            entry_time=pos.fill_time,
            exit_time=candle.timestamp,
            entry_price=intent.entry_price,
            stop_loss=exit_price,
            take_profit=intent.take_profit,
            mfe=pos.mfe,
            mae=pos.mae,
            win=is_win,
            pnl_points=pnl
        )
        self.vault.log_trade(record)
        self.active_pos = None
