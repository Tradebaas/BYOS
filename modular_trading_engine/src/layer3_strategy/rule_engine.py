from typing import List, Dict, Any
from datetime import datetime

from src.layer2_theory.market_state import MarketTheoryState
from src.layer3_strategy.models import OrderIntent
from src.layer3_strategy.playbook_schema import PlaybookConfig
from src.layer3_strategy.pipeline_context import PipelineContext
from src.layer3_strategy.modules import MODULE_REGISTRY

class RuleEngine:
    """
    The Modular Comparator of the Trading Engine.
    Executes a dynamic pipeline of Module nodes (read from Playbook JSON) 
    over the wiskundige (mathematical) MarketTheoryState logic.
    """
    def __init__(self, playbook: PlaybookConfig):
        self.strategy_id = playbook.strategy_id
        self.pipeline_modules = []
        
        # Instantiate pipeline modules dynamically based on Playbook JSON
        for step in playbook.pipeline:
            module_class = MODULE_REGISTRY.get(step.module_type)
            if not module_class:
                raise ValueError(f"Unknown module type in playbook: {step.module_type}")
                
            # Inject strategy_id into RATLimitOrder params automatically
            params_copy = dict(step.params)
            if step.module_type == "RATLimitOrder":
                params_copy['strategy_id'] = self.strategy_id
                
            self.pipeline_modules.append(module_class(params=params_copy))

    def evaluate(self, theory_state: MarketTheoryState, timestamp: datetime) -> List[OrderIntent]:
        """
        Runs the full modular pipeline on the currently active MarketTheoryState.
        Each module mutates the context, with the final module appending OrderIntents.
        """
        context = PipelineContext(theory_state=theory_state, timestamp=timestamp)
        
        for module in self.pipeline_modules:
            module.process(context)
            
        return context.intents
