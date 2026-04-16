from pydantic import BaseModel, ConfigDict, Field
from typing import List, Dict, Any

class PlaybookModuleConfig(BaseModel):
    """
    Configuration for a single step/module in the strategy pipeline.
    """
    module_type: str
    params: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(frozen=True)

class PlaybookConfig(BaseModel):
    """
    JSON-serializable configuration dictating exactly how Theory translates to Execution.
    The strategy is built by defining a sequential pipeline of module steps.
    """
    strategy_id: str
    pipeline: List[PlaybookModuleConfig]
    
    model_config = ConfigDict(frozen=True)
