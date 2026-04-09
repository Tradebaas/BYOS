from typing import List
from datetime import datetime

from src.layer2_theory.market_state import MarketTheoryState
from src.layer3_strategy.models import OrderIntent
from src.layer3_strategy.playbook_schema import PlaybookConfig
from src.layer3_strategy.orchestrator import evaluate_setup

class RuleEngine:
    """
    The main Comparator of the Trading Engine.
    Takes pure Layer 2 MarketTheoryState wiskunde and evaluates it against
    strict Layer 3 JSON Playbook parameters to generate absolute OrderIntents.
    """
    def __init__(self, playbook: PlaybookConfig):
        self.playbook = playbook

    def evaluate(self, theory_state: MarketTheoryState, timestamp: datetime) -> List[OrderIntent]:
        """
        Runs the exact playbook rules over the currently active MarketTheoryState.
        """
        intents: List[OrderIntent] = []
        
        # 1. Sweep through all Origin Trackers
        for tracker in theory_state.origin_trackers:
            # We must only evaluate levels that are fully active
            if not tracker.is_active:
                continue
                
            test_count = getattr(tracker, 'test_count', 0)
            
            # Use the orchestrator to build the pure limit order boundaries
            intent = evaluate_setup(
                level=tracker.level_data,
                config=self.playbook,
                test_count=test_count,
                current_timestamp=timestamp
            )
            
            if intent is not None:
                intents.append(intent)
                
        # 2. Sweep through all Reverse Trackers (Hold Levels -> Reverse Levels)
        for tracker in theory_state.reverse_trackers:
            if not tracker.is_active:
                continue
                
            # For reverse trackers, hits represent the test count
            test_count = getattr(tracker, 'hits', 0)
            
            intent = evaluate_setup(
                level=tracker.level_data,
                config=self.playbook,
                test_count=test_count,
                current_timestamp=timestamp
            )
            
            if intent is not None:
                intents.append(intent)

        # Result is a deterministic list of exact boundary conditions representing Tactical Intent
        return intents
