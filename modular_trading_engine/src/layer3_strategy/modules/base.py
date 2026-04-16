from typing import Dict, Any
from abc import ABC, abstractmethod

from src.layer3_strategy.pipeline_context import PipelineContext

class BaseStrategyModule(ABC):
    """
    Abstract base class for all modules operating in the Playbook Pipeline.
    """
    def __init__(self, params: Dict[str, Any]):
        self.params = params
        
    @abstractmethod
    def process(self, context: PipelineContext) -> None:
        """
        Mutates the PipelineContext. Implementations can read from context.theory_state,
        filter setup_candidates, or generate context.intents.
        """
        pass
