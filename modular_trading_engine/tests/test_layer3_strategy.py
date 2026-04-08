import pytest
from datetime import datetime, timezone

from src.layer2_theory.models import TheoryLevel, LevelType
from src.layer3_strategy.playbook_schema import PlaybookConfig
from src.layer3_strategy.orchestrator import evaluate_setup

def build_config() -> PlaybookConfig:
    return PlaybookConfig(
        strategy_id="NQ_STANDARD_v1",
        max_level_tests_allowed=1,
        tick_size=0.25,
        entry_frontrun_ticks=2,    # +0.50 margin on entry
        stop_loss_padding_ticks=4, # +1.00 padding on SL
        take_profit_rr=2.0         # 1:2 R/R ratio
    )

def test_bullish_playbook_orchestration():
    config = build_config()
    level = TheoryLevel(
        timestamp=datetime.now(timezone.utc),
        level_type=LevelType.HOLD_LEVEL,
        is_bullish=True,    # Acts as Support
        price_high=15000.00, # Front edge
        price_low=14995.00,  # Rear edge
        status="active"
    )
    
    intent = evaluate_setup(level, config, test_count=0, current_timestamp=datetime.now(timezone.utc))
    
    assert intent is not None
    assert intent.is_bullish is True
    
    # Entry calculations: Front edge (15000.00) + 2 ticks of 0.25 = 15000.50
    assert intent.entry_price == 15000.50
    
    # Stop Loss calculations: Rear edge (14995.00) - 4 ticks of 0.25 = 14994.00
    assert intent.stop_loss == 14994.00
    
    # Risk calculation: 15000.50 - 14994.00 = 6.50
    # TP calculation: Entry + (Risk * 2.0) = 15000.50 + 13.00 = 15013.50
    assert intent.take_profit == 15013.50


def test_bearish_playbook_orchestration():
    config = build_config()
    level = TheoryLevel(
        timestamp=datetime.now(timezone.utc),
        level_type=LevelType.HOLD_LEVEL,
        is_bullish=False,   # Acts as Resistance
        price_high=15005.00, # Rear edge
        price_low=15000.00,  # Front edge
        status="active"
    )
    
    intent = evaluate_setup(level, config, test_count=0, current_timestamp=datetime.now(timezone.utc))
    
    assert intent is not None
    assert intent.is_bullish is False
    
    # Entry calculations: Front edge (15000.00) - 2 ticks of 0.25 = 14999.50
    assert intent.entry_price == 14999.50
    
    # Stop Loss calculations: Rear edge (15005.00) + 4 ticks of 0.25 = 15006.00
    assert intent.stop_loss == 15006.00
    
    # Risk calculation: 15006.00 - 14999.50 = 6.50 points
    # TP calculation: Entry - (Risk * 2.0) = 14999.50 - 13.00 = 14986.50
    assert intent.take_profit == 14986.50


def test_validation_rules_block_setup():
    config = build_config() # allowed tests = 1
    level = TheoryLevel(
        timestamp=datetime.now(timezone.utc),
        level_type=LevelType.HOLD_LEVEL,
        is_bullish=True,
        price_high=15000.00,
        price_low=14995.00,
        status="active"
    )
    
    # Attempt setup evaluation on a level tested 2 times
    intent = evaluate_setup(level, config, test_count=2, current_timestamp=datetime.now(timezone.utc))
    
    # Expected None due to exhaustion rules
    assert intent is None
