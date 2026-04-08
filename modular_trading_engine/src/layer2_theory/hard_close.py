from src.layer1_data.models import Candle

def is_hard_close(reference_price: float, candle: Candle, is_support: bool) -> bool:
    """
    Evaluates whether a Candle constitutes a 'Hard Close' against a mathematical reference price.
    
    CCTA Rule: A Hard Close occurs EXCLUSIVELY when BOTH the Open AND Close of the candle's body 
    are registered beyond the reference line in the violating direction.
    
    :param reference_price: The absolute price line to check against (e.g. price_low of a hold level).
    :param candle: The L1 Candle to evaluate.
    :param is_support: True if the reference acts as Support (we check for a downward breach). 
                       False if it acts as Resistance (we check for an upward breach).
    :return: True if the candle solidly breaks the structure, False otherwise.
    """
    if is_support:
        # Breaking support: Body must be completely BELOW the support line
        # Momentum must align: Candle must be bearish (open > close)
        return (candle.open < reference_price and candle.close < reference_price) and (candle.open > candle.close)
    else:
        # Breaking resistance: Body must be completely ABOVE the resistance line
        # Momentum must align: Candle must be bullish (close > open)
        return (candle.open > reference_price and candle.close > reference_price) and (candle.close > candle.open)
