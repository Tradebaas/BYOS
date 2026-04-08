from src.layer1_data.models import Candle
from src.layer2_theory.models import TheoryLevel
from src.layer2_theory.hard_close import is_hard_close

def detect_deep_dive(level: TheoryLevel, candle: Candle) -> bool:
    """
    Evaluates whether a Candle performs a 'Deep Dive' on a given TheoryLevel.
    
    A Deep Dive occurs when price pierces the structural back of the wall (the extreme),
    but fails to create a valid Hard Close. This signals a harsh test or stop-hunt,
    but the level statistically remains valid.
    
    :param level: The active TheoryLevel being evaluated.
    :param candle: The L1 Candle to test.
    :return: True if a Deep Dive event occurred, False otherwise.
    """
    
    if level.is_bullish:
        # Support Level: The back of the wall is the absolute low (price_low)
        reference_price = level.price_low
        
        # Did it pierce the level?
        pierced = candle.low < reference_price
        
    else:
        # Resistance Level: The back of the wall is the absolute high (price_high)
        reference_price = level.price_high
        
        # Did it pierce the level?
        pierced = candle.high > reference_price
        
    if not pierced:
        return False
        
    # It pierced! Now verify it did NOT Hard Close.
    # If it is a Hard Close, it is an invalidation, NOT a Deep Dive.
    hard_closed = is_hard_close(reference_price, candle, is_support=level.is_bullish)
    
    return not hard_closed
