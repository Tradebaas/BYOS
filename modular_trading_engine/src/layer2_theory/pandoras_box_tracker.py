from enum import Enum
from src.layer1_data.models import Candle
from src.layer2_theory.models import TheoryLevel, LevelType
from src.layer2_theory.hard_close import is_hard_close

class PandoraState(str, Enum):
    INSIDE_PANDORA = "inside_pandora"
    ESCAPED_UP = "escaped_up"
    ESCAPED_DOWN = "escaped_down"

class ScopeBoxTracker:
    """
    Pandora's Box Tracker.
    Tracks a state of structural ambiguity where price is bounded by two 
    conflicting active levels (e.g., Support Origin vs Resistance Origin).
    """

    def __init__(self, floor_level: TheoryLevel, ceiling_level: TheoryLevel):
        """
        Initializes the Pandora's Box with a floor and ceiling.
        """
        if not floor_level.is_bullish:
            raise ValueError("Floor level must act as support (is_bullish=True).")
        if ceiling_level.is_bullish:
            raise ValueError("Ceiling level must act as resistance (is_bullish=False).")
            
        # Ensure floor is structurally below ceiling
        if floor_level.price_low >= ceiling_level.price_high:
            raise ValueError("Floor's low must be mathematically below the Ceiling's high.")
            
        self.floor_level = floor_level
        self.ceiling_level = ceiling_level
        self.state = PandoraState.INSIDE_PANDORA
        self.is_active = True
        
    def process_candle(self, candle: Candle):
        """
        Evaluates the current candle to see if we escaped Pandora's Box.
        Escaping requires a Hard Close through the back of either wall.
        """
        if not self.is_active:
            return

        # Check upward escape (Hard close through the ceiling)
        if is_hard_close(reference_price=self.ceiling_level.price_high, candle=candle, is_support=False):
            self.state = PandoraState.ESCAPED_UP
            self.is_active = False
            return
            
        # Check downward escape (Hard close through the floor)
        if is_hard_close(reference_price=self.floor_level.price_low, candle=candle, is_support=True):
            self.state = PandoraState.ESCAPED_DOWN
            self.is_active = False
            return

