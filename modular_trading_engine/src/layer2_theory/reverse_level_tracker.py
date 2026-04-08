from typing import Optional
from src.layer1_data.models import Candle
from src.layer2_theory.models import TheoryLevel, LevelType
from src.layer2_theory.tested_state import is_tested
from src.layer2_theory.hard_close import is_hard_close

class ReverseTracker:
    """
    State machine that tracks the lifecycle of a Hold Level over time.
    It evolves a Hold Level into a Reverse Level based on 2 or more independent hits.
    Invalidates immediately upon a Hard Close (Highlander rule).
    """

    def __init__(self, initial_level: TheoryLevel):
        """
        Initializes the tracker using a Hold Level as the starting point.
        """
        if initial_level.level_type != LevelType.HOLD_LEVEL:
            raise ValueError("ReverseTracker must start with a HOLD_LEVEL.")
        
        self.level_data = initial_level
        self.hits = 0 # Unlike Break Levels, the creation of a Hold Level does not count as a 'hit'.
        self.candles_since_last_hit = 0
        self.is_active = True
        
    def process_candle(self, candle: Candle):
        """
        Processes a single L1 continuous candle to evaluate state machine transitions.
        """
        if not self.is_active:
            return
            
        # 1. Highlander Rule: Is it a hard close?
        # A hard close refers to breaking through the absolute back of the wall.
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
            # To be an independent hit, we need separation (at least 1 candle not hitting it)
            if self.candles_since_last_hit >= 1:
                self.hits += 1
                
                # Escalate to Reverse Level on the second independent hit
                if self.hits == 2 and self.level_data.level_type == LevelType.HOLD_LEVEL:
                    self._update_level_model(level_type=LevelType.REVERSE_LEVEL, status="active")
            
            # Reset separation counter because we just touched it
            self.candles_since_last_hit = 0
        else:
            # We didn't hit it, so it counts as separation
            self.candles_since_last_hit += 1

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
