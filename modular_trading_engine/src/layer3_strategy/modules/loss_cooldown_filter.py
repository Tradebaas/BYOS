from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

from src.layer3_strategy.modules.base import BaseStrategyModule
from src.layer3_strategy.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)


class LossCooldownFilter(BaseStrategyModule):
    """
    Directional Loss Cool-down Filter.
    
    After a stop-loss exit (loss), blocks new setups in the SAME direction
    for `cooldown_minutes`. The opposite direction remains unrestricted.
    
    This prevents emotional "revenge" re-entries that statistically 
    degrade win rate by ~3-5% (validated over 15 weeks / 107K candles).
    
    Config params:
        cooldown_minutes (int): Minutes to block same-direction entries after a loss.
                                Default: 30. Validated optimal via backtest Run E.
    
    State injection:
        Reads `context.last_trade_result` (injected by FleetCommander/Simulator).
        Schema: {"direction": "LONG"|"SHORT", "pnl": float, "exit_time": datetime}
    """
    # Class-level persistent state survives across pipeline evaluations.
    # Maps direction -> timestamp of last loss.
    _last_loss_time: Dict[str, datetime] = {}
    
    def process(self, context: PipelineContext) -> None:
        if not context.setup_candidates:
            return
        
        cooldown_minutes = self.params.get('cooldown_minutes', 30)
        cooldown_delta = timedelta(minutes=cooldown_minutes)
        
        # Step 1: Ingest the latest trade result if available
        pnl = context.last_trade_result
        is_bullish = context.last_trade_is_bullish
        
        if pnl is not None and pnl < 0:
            direction = "LONG" if is_bullish else "SHORT"
            LossCooldownFilter._last_loss_time[direction] = context.timestamp
            logger.info(
                f"[CooldownFilter] Registered {direction} loss at {context.timestamp}. "
                f"Blocking {direction} entries for {cooldown_minutes} min."
            )
        
        # Step 2: Filter setup candidates that are still in cool-down
        filtered = []
        for tracker in context.setup_candidates:
            level = tracker.level_data
            direction = "LONG" if level.is_bullish else "SHORT"
            
            last_loss = LossCooldownFilter._last_loss_time.get(direction)
            if last_loss is not None:
                elapsed = context.timestamp - last_loss
                if elapsed < cooldown_delta:
                    logger.debug(
                        f"[CooldownFilter] Blocking {direction} setup — "
                        f"{elapsed.total_seconds():.0f}s since last loss "
                        f"(need {cooldown_minutes * 60}s)"
                    )
                    continue  # Skip this candidate
            
            filtered.append(tracker)
        
        context.setup_candidates = filtered
