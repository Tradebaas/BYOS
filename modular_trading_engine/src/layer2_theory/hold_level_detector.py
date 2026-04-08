from typing import List, Optional
from datetime import datetime

from src.layer1_data.models import Candle
from src.layer2_theory.models import TheoryLevel, LevelType


def find_all_support_hold_levels(candles: List[Candle]) -> List[TheoryLevel]:
    """
    Scans a historical sequence of candles to find all mathematical Support Hold Levels.
    A Support Hold Level is structurally identified when a bearish (red) candle 
    is immediately followed by a bullish (green) candle. The bearish candle forms the Hold.
    """
    levels = []
    for i in range(len(candles) - 1):
        if candles[i].is_bearish and candles[i+1].is_bullish:
            levels.append(TheoryLevel(
                timestamp=candles[i].timestamp,
                level_type=LevelType.HOLD_LEVEL,
                is_bullish=True, # Acts as Support
                price_high=candles[i].high,
                price_low=candles[i].low,
                status="identified"
            ))
    return levels

def find_all_resistance_hold_levels(candles: List[Candle]) -> List[TheoryLevel]:
    """
    Scans a historical sequence of candles to find all mathematical Resistance Hold Levels.
    A Resistance Hold Level is structurally identified when a bullish (green) candle 
    is immediately followed by a bearish (red) candle. The bullish candle forms the Hold.
    """
    levels = []
    for i in range(len(candles) - 1):
        if candles[i].is_bullish and candles[i+1].is_bearish:
            levels.append(TheoryLevel(
                timestamp=candles[i].timestamp,
                level_type=LevelType.HOLD_LEVEL,
                is_bullish=False, # Acts as Resistance
                price_high=candles[i].high,
                price_low=candles[i].low,
                status="identified"
            ))
    return levels
