from enum import Enum
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class LevelType(str, Enum):
    HOLD_LEVEL = "hold_level"
    BREAK_LEVEL = "break_level"
    ORIGIN_LEVEL = "origin_level"
    REVERSE_LEVEL = "reverse_level"
    TREND_LINE = "trend_line"

class TheoryLevel(BaseModel):
    """
    Immutable representation of a mathematical structure in Layer 2.
    It represents a "wall" in the market (e.g., Hold Level, Break Level).
    Does NOT contain strategy variables like 'has_been_tested_for_trade'.
    """
    model_config = ConfigDict(frozen=True)
    
    timestamp: datetime
    level_type: LevelType
    is_bullish: bool  # True means structural support (green wall). False means resistance (red wall).
    
    # Mathematical boundaries of the structure (e.g. wick and body extremes)
    price_high: float = Field(..., ge=0.0) 
    price_low: float = Field(..., ge=0.0)
    price_open: float = Field(0.0, ge=0.0) # The open of the candidate forming the level
    
    # e.g., 'identified', 'active', 'invalidated'. We recreate objects when status changes.
    status: str
