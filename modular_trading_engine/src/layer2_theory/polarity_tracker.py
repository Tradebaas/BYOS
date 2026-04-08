from enum import Enum
from src.layer1_data.models import Candle
from src.layer2_theory.models import TheoryLevel, LevelType
from src.layer2_theory.hard_close import is_hard_close

class PolarityState(str, Enum):
    UNKNOWN = "unknown"
    ABOVE_POLARITY = "above_polarity"
    BELOW_POLARITY = "below_polarity"
    BROKEN = "broken"

class PolarityTracker:
    """
    Tracks the polarization of the chart relative to a confirmed polarity-generating level.
    Only Origin Levels and Reverse Levels generate Polarity.
    """

    def __init__(self, polarity_level: TheoryLevel):
        """
        Initializes the tracker using an Origin Level or Reverse Level.
        """
        if polarity_level.level_type not in (LevelType.ORIGIN_LEVEL, LevelType.REVERSE_LEVEL):
            raise ValueError("PolarityTracker requires an ORIGIN_LEVEL or REVERSE_LEVEL.")
        
        self.level_data = polarity_level
        self.state = PolarityState.UNKNOWN
        self.is_active = True
        
    def process_candle(self, candle: Candle):
        """
        Processes a candle to update polarity state or detect a polarity break.
        """
        if not self.is_active:
            return

        is_support = self.level_data.is_bullish
        back_of_wall = self.level_data.price_low if is_support else self.level_data.price_high
        
        # 1. Check if the Polarity is broken (Hard Close)
        if is_hard_close(reference_price=back_of_wall, candle=candle, is_support=is_support):
            self.state = PolarityState.BROKEN
            self.is_active = False
            return
            
        # 2. Determine Zone
        # If it's acting as support and hasn't broken, price is generally above polarity
        # If it's acting as resistance and hasn't broken, price is generally below polarity
        
        if is_support:
            # Bullish Level = Support = We expect price to be ABOVE this polarity.
            # Technically, price might wick below it, but as long as it isn't broken, it's holding above.
            self.state = PolarityState.ABOVE_POLARITY
        else:
            # Bearish Level = Resistance = We expect price to be BELOW this polarity.
            self.state = PolarityState.BELOW_POLARITY

