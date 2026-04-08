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
        
        self.is_separated = False
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
            
        # 2. Test Rule: Does the candle test the level?
        hit_occurred = is_tested(self.level_data, candle)
        
        if hit_occurred:
            # To be an independent hit, we MUST have achieved separation via a detached opposite-color candle first.
            if getattr(self, 'is_separated', False):
                self.test_count += 1
                
                # Determine hit price based on support/resistance
                hit_price = candle.low if self.level_data.is_bullish else candle.high
                self.test_history.append((candle.timestamp, hit_price))
                
                # Escalate to Origin Level on exactly the SECOND independent test
                # According to theoretical blueprints: A Break Level tested twice becomes an Origin Level.
                if self.test_count == 2 and self.level_data.level_type == LevelType.BREAK_LEVEL:
                    self._update_level_model(level_type=LevelType.ORIGIN_LEVEL, status="active")
            
            # Reset separation because we just touched it
            self.is_separated = False
        else:
            # We didn't hit it. Check if this candle achieves separation.
            # Separation is strictly defined as an opposite-color candle fully detached from the level.
            if self.level_data.is_bullish:
                # Support Level: Needs a BEARISH candle completely ABOVE the level
                if candle.is_bearish and candle.low > self.level_data.price_low:
                    self.is_separated = True
            else:
                # Resistance Level: Needs a BULLISH candle completely BELOW the level
                if candle.is_bullish and candle.high < self.level_data.price_high:
                    self.is_separated = True

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
