from typing import Optional, Any

from src.layer1_data.models import Candle
from src.layer3_strategy.models import OrderIntent
from src.layer4_execution.data_vault import DataVault, TradeRecord

class ActivePosition:
    def __init__(self, intent: OrderIntent, fill_time: Any):
        self.intent = intent
        self.fill_time = fill_time
        
        # Initial bounds
        self.mfe = intent.entry_price
        self.mae = intent.entry_price
        
        # Trade Management State
        self.current_stop_loss = intent.stop_loss
        self.breakeven_activated = False

class BacktestSimulator:
    """
    Virtual Execution Engine running on M1 Candles.
    Responsible for executing Limit Orders and registering Gray Candles properly.
    """
    def __init__(self, vault: DataVault, commission_per_contract: float = 7.60, position_size: int = 1):
        self.vault = vault
        self.commission_per_contract = commission_per_contract
        self.position_size = position_size
        self.pending_intent: Optional[OrderIntent] = None
        self.active_pos: Optional[ActivePosition] = None
        
        # Parity with LiveFleetCommander lock
        self.last_ordered_setup_price: Optional[float] = None
        self.last_ordered_setup_direction: Optional[bool] = None
        
    def cancel_all(self) -> None:
        """Simulate a CancelAll operation (e.g. tracking TTL timeout or rules shift)"""
        self.pending_intent = None
        self.last_ordered_setup_price = None
        self.last_ordered_setup_direction = None
        
    def stage_order(self, intent: OrderIntent) -> None:
        """Called by Layer 3 to submit a new limit order."""
        if self.active_pos is None:
            # Replicate live order lock to prevent multiple trades on the identical setup
            if intent.entry_price == getattr(self, "last_ordered_setup_price", None) and \
               intent.is_bullish == getattr(self, "last_ordered_setup_direction", None):
                return
                
            self.pending_intent = intent
            self.last_ordered_setup_price = intent.entry_price
            self.last_ordered_setup_direction = intent.is_bullish
            
    def process_candle(self, candle: Candle) -> None:
        """
        The heartbeat of the backtester. Processes the new market data sequentially.
        """
        # Phase 1: Handle OPEN position (update metrics, check exits)
        if self.active_pos is not None:
            self._evaluate_active_position(candle)
            return  # If we have an active position, we don't process new entries on the same tick
            
        # Phase 2: Handle PENDING order (check for limit fills or expiration)
        if self.pending_intent is not None:
            # Check for TTL Expiration (20 candles/minutes)
            ttl_candles = (candle.timestamp - self.pending_intent.timestamp).total_seconds() / 60.0
            if ttl_candles > 20:
                # Expire the pending intent
                self.pending_intent = None
            else:
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
            self.active_pos = ActivePosition(intent=intent, fill_time=candle.timestamp)
            self.pending_intent = None
            
            # CRITICAL: We just got filled inside this M1 candle. 
            # We must NOT use the full candle low/high for TP/SL because part of that candle happened BEFORE we got filled.
            # E.g. a Short Limit is filled at the high. If the candle is bullish, the low happened BEFORE the fill.
            
            # Construct a synthetic 'remainder' candle based on polarity
            remainder_high = candle.high
            remainder_low = candle.low
            
            if candle.is_bullish:
                if intent.is_bullish:
                    # Long limit filled at Low. Remainder path is Low -> High -> Close
                    remainder_low = intent.entry_price
                else:
                    # Short limit filled at High. Remainder path is High -> Close
                    remainder_low = min(intent.entry_price, candle.close)
            else:
                if intent.is_bullish:
                    # Long limit filled at Low. Remainder path is Low -> Close
                    remainder_high = max(intent.entry_price, candle.close)
                else:
                    # Short limit filled at High. Remainder path is High -> Low -> Close
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
        """
        Evaluates an active position against the current incoming candle.
        Closes the position if TP or SL is hit.
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

        # Handle Breakeven target trigger
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
                
        # PESSIMISTIC INTRA-BAR RULE:
        # If BOTH extremes were breached in the exact same 1-min candle, we assume the WORST CASE scenario:
        # Stop Loss is always hit before Take Profit. 
        # This completely eliminates look-ahead bias and creates absolute certainty in backtest win rates.
        tp_hit = False
        sl_hit = False
        same_candle_conflict = False
        
        if high_breach and low_breach:
            same_candle_conflict = True
            sl_hit = True
            tp_hit = False
        else:
            if intent.is_bullish:
                tp_hit = high_breach
                sl_hit = low_breach
            else:
                tp_hit = low_breach
                sl_hit = high_breach
                
        if tp_hit:
            self._close_position(candle, pos, is_win=True, same_candle_conflict=same_candle_conflict)
        elif sl_hit:
            self._close_position(candle, pos, is_win=False, same_candle_conflict=same_candle_conflict)

    def _close_position(self, candle: Candle, pos: ActivePosition, is_win: bool, same_candle_conflict: bool = False) -> None:
        intent = pos.intent
        
        # Dynamic PNL calculation supporting trailing/breakeven stops
        if intent.is_bullish:
            exit_price = intent.take_profit if is_win else pos.current_stop_loss
            pnl = exit_price - intent.entry_price
        else:
            exit_price = intent.take_profit if is_win else pos.current_stop_loss
            pnl = intent.entry_price - exit_price
            
        record = TradeRecord(
            strategy_id=intent.strategy_id,
            is_bullish=intent.is_bullish,
            entry_time=pos.fill_time, # Record ACTUAL broker fill time 
            exit_time=candle.timestamp,
            entry_price=intent.entry_price,
            stop_loss=pos.current_stop_loss,
            take_profit=intent.take_profit,
            mfe=pos.mfe,
            mae=pos.mae,
            win=is_win,
            pnl_points=pnl,
            same_candle_conflict=same_candle_conflict,
            commission_usd=(self.commission_per_contract * self.position_size)
        )
        
        self.vault.log_trade(record)
        self.active_pos = None
