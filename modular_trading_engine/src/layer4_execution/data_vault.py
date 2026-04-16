from pydantic import BaseModel, ConfigDict
from typing import List
from datetime import datetime

class TradeRecord(BaseModel):
    """
    Immutable representation of a uniquely concluded trade.
    Used for analytical aggregation (MAE/MFE optimization).
    """
    strategy_id: str
    is_bullish: bool
    
    entry_time: datetime
    exit_time: datetime
    
    entry_price: float
    stop_loss: float
    take_profit: float
    
    # Excursion metrics for strategy tuning
    mfe: float # Maximum Favorable Excursion (highest/lowest price reached whilst in profit)
    mae: float # Maximum Adverse Excursion (highest/lowest price reached whilst in drawdown)
    
    # Financial metrics
    win: bool
    pnl_points: float # Net points captured or lost
    
    model_config = ConfigDict(frozen=True)

class DataVault:
    """
    Storage facility for accumulating execution histories during backtesting.
    """
    def __init__(self):
        self.trades: List[TradeRecord] = []
        
    def log_trade(self, record: TradeRecord) -> None:
        """Saves a concluded trade to the vault."""
        self.trades.append(record)
        
    def generate_summary(self) -> dict:
        """Generates a high-level statistical summary."""
        total = len(self.trades)
        wins = sum(1 for t in self.trades if t.win)
        losses = total - wins
        win_rate = (wins / total * 100.0) if total > 0 else 0.0
        
        max_drawdown = 0.0
        peak = 0.0
        cumulative = 0.0
        for t in self.trades:
            cumulative += t.pnl_points
            if cumulative > peak:
                peak = cumulative
            
            drawdown = peak - cumulative
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(win_rate, 2),
            "net_pnl_points": sum(t.pnl_points for t in self.trades),
            "max_drawdown_points": max_drawdown
        }
