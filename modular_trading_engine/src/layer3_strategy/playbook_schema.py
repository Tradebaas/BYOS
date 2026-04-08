from pydantic import BaseModel, ConfigDict

class PlaybookConfig(BaseModel):
    """
    JSON-serializable configuration dictating exactly how Theory translates to Execution.
    This represents the 'Setup Rules' for a given asset.
    """
    strategy_id: str
    
    # Theory Filtering Rules
    max_level_tests_allowed: int   # Prevents taking signals on overused levels
    
    # Asset Math
    tick_size: float               # Example: 0.25 (NQ) or 0.5 (ES)
    
    # Order Padding (Tactics)
    entry_frontrun_ticks: int      # Ticks added to pull entry closer to current price
    stop_loss_padding_ticks: int   # Ticks padding behind the absolute boundary
    take_profit_rr: float          # Risk/Reward multiplier for TP calculation (e.g., 2.0)
    
    model_config = ConfigDict(frozen=True)
