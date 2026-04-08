from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, computed_field


class Candle(BaseModel):
    """
    Immutable representation of a single OHLCV price unit (Candlestick).
    Layer 1 entity that supplies the mathematical boundaries for Layer 2.
    """
    model_config = ConfigDict(frozen=True)

    # Core data fields
    timestamp: datetime
    open: float = Field(..., ge=0.0)
    high: float = Field(..., ge=0.0)
    low: float = Field(..., ge=0.0)
    close: float = Field(..., ge=0.0)
    volume: float = Field(0.0, ge=0.0)

    # Derived state descriptors
    @computed_field
    def is_bullish(self) -> bool:
        return self.close > self.open

    @computed_field
    def is_bearish(self) -> bool:
        return self.close < self.open

    @computed_field
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @computed_field
    def top_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @computed_field
    def bottom_wick(self) -> float:
        return min(self.open, self.close) - self.low
