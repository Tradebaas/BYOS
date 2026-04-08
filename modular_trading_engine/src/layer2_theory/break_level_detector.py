from typing import List

from src.layer1_data.models import Candle
from src.layer2_theory.models import TheoryLevel, LevelType


def find_all_top_side_break_levels(candles: List[Candle]) -> List[TheoryLevel]:
    """
    Scans a historical sequence of candles to find all mathematical Top Side Break Levels.
    A Top Side Break Level is formed at the peak of a move, identified by a bullish (green)
    candle followed by two consecutive bearish (red) candles.
    
    The level is marked at the high wick of the first bearish candle in the sequence.
    It acts mathematically as a resistance wall (is_bullish=False), which price must
    test from below to attempt breaking upward.
    """
    levels = []
    # We need a window of 3 candles: i-1, i, i+1
    for i in range(1, len(candles) - 1):
        if candles[i-1].is_bullish and candles[i].is_bearish and candles[i+1].is_bearish:
            levels.append(TheoryLevel(
                timestamp=candles[i].timestamp,
                level_type=LevelType.BREAK_LEVEL,
                is_bullish=False,  # Acts as a resistance wall
                price_high=candles[i].high,
                price_low=candles[i].high,  # A break level is a precise line
                status="identified"
            ))
    return levels


def find_all_bottom_side_break_levels(candles: List[Candle]) -> List[TheoryLevel]:
    """
    Scans a historical sequence of candles to find all mathematical Bottom Side Break Levels.
    A Bottom Side Break Level is formed at the bottom of a move, identified by a bearish (red)
    candle followed by two consecutive bullish (green) candles.
    
    The level is marked at the low wick of the first bullish candle in the sequence.
    It acts mathematically as a support wall (is_bullish=True), which price must
    test from above to attempt breaking downward.
    """
    levels = []
    # We need a window of 3 candles: i-1, i, i+1
    for i in range(1, len(candles) - 1):
        if candles[i-1].is_bearish and candles[i].is_bullish and candles[i+1].is_bullish:
            levels.append(TheoryLevel(
                timestamp=candles[i].timestamp,
                level_type=LevelType.BREAK_LEVEL,
                is_bullish=True,  # Acts as a support wall
                price_high=candles[i].low,
                price_low=candles[i].low,  # A break level is a precise line
                status="identified"
            ))
    return levels
