from pydantic import BaseModel, ConfigDict
from datetime import datetime

class OrderIntent(BaseModel):
    """
    The immutable order intent produced by the Strategy Layer.
    Passed to Layer 4 (Execution) to place pure limit OCO orders.
    Contains keiharde (hardcoded) un-ambiguous execution coordinates.
    """
    timestamp: datetime    # Time the setup was evaluated
    is_bullish: bool       # True for Buy Limit, False for Sell Limit
    entry_price: float     # The exact limit order entry price
    stop_loss: float       # Exact absolute stop-loss price
    take_profit: float     # Exact absolute take-profit price
    
    # Metadata for execution and tracking
    strategy_id: str
    theory_reference_ts: float # Epoch of the TheoryLevel that triggered this
    
    model_config = ConfigDict(frozen=True)
