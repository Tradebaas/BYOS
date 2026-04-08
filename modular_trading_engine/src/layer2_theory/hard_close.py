from src.layer1_data.models import Candle

def is_hard_close(reference_price: float, candle: Candle, is_support: bool) -> bool:
    """
    Evaluates whether a Candle breaks a mathematical reference price to INVALIDATE a wall.
    
    CCTA Rule: Invalidation occurs when the CLOSING price of a momentum candle 
    penetrates and settles beyond the reference line.
    
    :param reference_price: The absolute price line to check against (e.g. price_low of a hold level).
    :param candle: The L1 Candle to evaluate.
    :param is_support: True if the reference acts as Support (we check for a downward breach). 
                       False if it acts as Resistance (we check for an upward breach).
    :return: True if the candle solidly breaks the structure, False otherwise.
    """
    if is_support:
        # Breaking support: Body CLOSE must be completely BELOW the support line
        # Momentum must align: Candle must be bearish
        return candle.close < reference_price and candle.is_bearish
    else:
        # Breaking resistance: Body CLOSE must be completely ABOVE the resistance line
        # Momentum must align: Candle must be bullish
        return candle.close > reference_price and candle.is_bullish
