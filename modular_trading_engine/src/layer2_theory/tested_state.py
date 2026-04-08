from src.layer1_data.models import Candle
from src.layer2_theory.models import TheoryLevel

def is_tested(level: TheoryLevel, candle: Candle) -> bool:
    """
    Evaluates if a Candle has mathematically 'hit' the TheoryLevel.
    This uses absolute zero-tolerance limits (<= or >=). Front-running variables are NOT allowed here.
    
    :param level: The immutable structure against which we test.
    :param candle: The L1 Candle.
    :return: True if the extreme of the candle reaches the boundary of the zone.
    """
    if level.is_bullish:
        # For structural support, the "front" of the wall is the highest point of the zone
        return candle.low <= level.price_high
    else:
        # For generic resistance, the "front" of the wall is the lowest point
        return candle.high >= level.price_low

def is_deep_dive(level: TheoryLevel, candle: Candle) -> bool:
    """
    Determines if a Candle wick pierces through the absolute BACK of the theoretical zone.
    (This function does not check for Hard Close, it solely checks the wick's reach).
    
    :return: True if the extreme wick goes further than the absolute end of the structure.
    """
    if level.is_bullish:
        # Deep dive into support: candle wicks lower than the absolute lowest point of the support
        return candle.low < level.price_low
    else:
        # Deep dive into resistance: candle wicks higher than the absolute highest point of resistance
        return candle.high > level.price_high
