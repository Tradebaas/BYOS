from datetime import datetime
from typing import List
from src.layer1_data.models import Candle
from src.layer2_theory.models import TheoryLevel, LevelType
from src.layer2_theory.hard_close import is_hard_close

class RangeTrendTracker:
    """
    A Hold Level hit multiple times while satisfying Break Level criteria.
    It functions very similarly to a Reverse Level, but requires that the original Hold Level
    also meets the structural requirements of a Break Level (e.g. formed by 2 consecutive candles).
    For simplicity in Layer 2, we track it as a specialized level that escalates on multiple hits.
    """
    
    def __init__(self, initial_level: TheoryLevel):
        self.level_data = initial_level
        self.hits = 0
        self.candles_since_last_hit = 1  # Start at > 0 so first hit registers
        self.is_active = True
        
    def process_candle(self, candle: Candle):
        """
        Processes candle for hard closes and hits. Similar mechanics to other horizontal trackers.
        """
        if not self.is_active:
            return

        back_of_wall = self.level_data.price_low if self.level_data.is_bullish else self.level_data.price_high
        
        if is_hard_close(reference_price=back_of_wall, candle=candle, is_support=self.level_data.is_bullish):
            self.is_active = False
            return
            
        # Check hits
        hit_occurred = False
        if self.level_data.is_bullish and candle.low <= self.level_data.price_high and candle.low >= self.level_data.price_low:
            hit_occurred = True
        elif not self.level_data.is_bullish and candle.high >= self.level_data.price_low and candle.high <= self.level_data.price_high:
            hit_occurred = True
            
        if hit_occurred:
            if self.candles_since_last_hit >= 1:
                self.hits += 1
            self.candles_since_last_hit = 0
        else:
            self.candles_since_last_hit += 1

class TrendLineTracker:
    """
    Diagonal levels connecting two or more points (timestamp, price).
    Calculates the slope (price change per second) and tracks if price violates the diagonal line.
    """
    
    def __init__(self, point1: tuple[datetime, float], point2: tuple[datetime, float], is_support: bool):
        """
        :param point1: (timestamp_datetime, price)
        :param point2: (timestamp_datetime, price)
        :param is_support: True if the diagonal line represents support (bottom), False if resistance (top)
        """
        if point2[0] <= point1[0]:
            raise ValueError("Point 2 must occur after Point 1 chronologically.")
            
        self.point1 = point1
        self.point2 = point2
        self.is_support = is_support
        
        # Calculate slope: units of price per second
        time_delta_seconds = (point2[0] - point1[0]).total_seconds()
        self.slope = (point2[1] - point1[1]) / time_delta_seconds
        self.is_active = True

    def get_price_at_timestamp(self, timestamp: datetime) -> float:
        """
        Calculates the theoretical price of the diagonal trendline at a specific timestamp.
        """
        time_diff_secs = (timestamp - self.point1[0]).total_seconds()
        return self.point1[1] + (self.slope * time_diff_secs)

    def process_candle(self, candle: Candle):
        """
        Evaluates if the candle hard-closes beyond the diagonal line.
        """
        if not self.is_active:
            return
            
        # Evaluate the line's price at the candle's close time
        current_line_price = self.get_price_at_timestamp(candle.timestamp)
        
        # Diagonal Hard Close logic:
        # We approximate the standard rule. Since the line is diagonal, we check if both Open and Close
        # violate the line at their respective approximated locations or simply at the candle's close.
        # For L2 simplicity, we evaluate against the line's price at `candle.timestamp`.
        
        if is_hard_close(reference_price=current_line_price, candle=candle, is_support=self.is_support):
            self.is_active = False
            return
