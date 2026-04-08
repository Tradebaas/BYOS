from datetime import datetime
from typing import Optional

from src.layer2_theory.models import TheoryLevel
from src.layer3_strategy.models import OrderIntent
from src.layer3_strategy.playbook_schema import PlaybookConfig

def evaluate_setup(
    level: TheoryLevel,
    config: PlaybookConfig,
    test_count: int,
    current_timestamp: datetime
) -> Optional[OrderIntent]:
    """
    Evaluates a theoretical setup against a Playbook configuration to design a pure limit order.
    
    :param level: The underlying wiskundige (mathematical) TheoryLevel.
    :param config: The Playbook parameters detailing ticks and margin.
    :param test_count: How many times this level was previously tested.
    :param current_timestamp: The time of evaluation.
    :return: A strict OrderIntent with absolute prices, or None if the setup is rejected.
    """
    # Defensive programming: filter based on playbook exhaustion rules
    if test_count > config.max_level_tests_allowed:
        return None
        
    tick = config.tick_size
    front = config.entry_frontrun_ticks
    pad = config.stop_loss_padding_ticks
    rr = config.take_profit_rr
    
    if level.is_bullish:
        # LONG SETUP (Support)
        # Front-run pushes the entry higher up toward current price
        entry_price = level.price_high + (front * tick)
        
        # Stop loss is padded completely strictly below the rear of the structural support
        stop_loss = level.price_low - (pad * tick)
        
        risk = entry_price - stop_loss
        
        # If risk is zero or negative due to weird edge cases, block trade
        if risk <= 0:
            return None
            
        take_profit = entry_price + (risk * rr)
        
    else:
        # SHORT SETUP (Resistance)
        # Front-run pulls the entry lower down toward current price
        entry_price = level.price_low - (front * tick)
        
        # Stop loss is padded completely strictly above the rear of the structural resistance
        stop_loss = level.price_high + (pad * tick)
        
        risk = stop_loss - entry_price
        
        if risk <= 0:
            return None
            
        take_profit = entry_price - (risk * rr)
    
    return OrderIntent(
        timestamp=current_timestamp,
        is_bullish=level.is_bullish,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        strategy_id=config.strategy_id,
        theory_reference_ts=level.timestamp.timestamp()
    )
