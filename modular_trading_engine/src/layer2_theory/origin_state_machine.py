from typing import Optional
from src.layer1_data.models import Candle
from src.layer2_theory.models import TheoryLevel, LevelType
from src.layer2_theory.tested_state import is_tested
from src.layer2_theory.hard_close import is_hard_close

class OriginTracker:
    """
    State machine that tracks the lifecycle of a level over time.
    It evolves a Break Level into an Origin Level based on independent hits,
    and invalidates it immediately upon a Hard Close (Highlander rule).
    """

    def __init__(self, initial_level: TheoryLevel):
        """
        Initializes the tracker using a Break Level as the starting point.
        """
        if initial_level.level_type != LevelType.BREAK_LEVEL:
            raise ValueError("OriginTracker must start with a BREAK_LEVEL.")
        
        self.level_data = initial_level
        # The formulation of the break level itself is NOT a test.
        self.test_count = 0  
        self.test_history = [] # Store as (timestamp, string representation of hit price)
        
        self.waiting_opposite = True
        self.waiting_retest = False
        
        self.is_converted = False
        self.is_active = True
        
    def process_candle(self, candle: Candle):
        """
        Processes a single L1 continuous candle to evaluate state machine transitions.
        """
        if not self.is_active:
            # Once invalidated by a hard close, the level is "dead" as structural polarity.
            return
            
        # 1. Highlander Rule: Is it a hard close?
        back_of_wall = self.level_data.price_low if self.level_data.is_bullish else self.level_data.price_high
        
        if is_hard_close(
            reference_price=back_of_wall,
            candle=candle,
            is_support=self.level_data.is_bullish
        ):
            self.is_active = False
            self._update_level_model(status="invalidated")
            return
            
        # Determine basic candle properties
        green = candle.is_bullish
        red = candle.is_bearish
        
        # We need historical context to check red[1] and green[1].
        # Assuming the caller doesn't pass history directly, we can maintain the last candle's color.
        prev_green = getattr(self, '_prev_green', False)
        prev_red = getattr(self, '_prev_red', False)
        
        # Structure Reset (Pine logic)
        # if (is_break_up and red and red[1]) or (not is_break_up and green and green[1])
        is_break_up = not self.level_data.is_bullish  # Bearish = is_break_up
        
        if (is_break_up and red and prev_red) or (not is_break_up and green and prev_green):
            self.waiting_opposite = True
            self.waiting_retest = False
            
        if self.waiting_opposite:
            if is_break_up and green:
                self.waiting_opposite = False
                self.waiting_retest = True
            elif not is_break_up and red:
                self.waiting_opposite = False
                self.waiting_retest = True
                
        # Touch detection
        hit_occurred = is_tested(self.level_data, candle)
        if self.waiting_retest and hit_occurred:
            valid_close = green if is_break_up else red
            if valid_close:
                self.test_count += 1
                self.waiting_retest = False
                
                # Determine hit price
                hit_price = candle.high if is_break_up else candle.low
                self.test_history.append((candle.timestamp, hit_price))
                
                # Escalate to Origin
                if self.test_count == 2 and self.level_data.level_type == LevelType.BREAK_LEVEL:
                    self._update_level_model(level_type=LevelType.ORIGIN_LEVEL, status="active")
                    
        # Store for next iteration
        self._prev_green = green
        self._prev_red = red

    def _update_level_model(self, level_type: Optional[LevelType] = None, status: Optional[str] = None):
        """
        Helper to recreate the immutable TheoryLevel with updated attributes.
        """
        kwargs = self.level_data.model_dump()
        if level_type:
            kwargs["level_type"] = level_type
        if status:
            kwargs["status"] = status
            
        self.level_data = TheoryLevel(**kwargs)
