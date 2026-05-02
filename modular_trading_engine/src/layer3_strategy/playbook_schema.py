from pydantic import BaseModel, ConfigDict, Field
from typing import List, Dict, Any

class PlaybookModuleConfig(BaseModel):
    """
    Configuration for a single step/module in the strategy pipeline.
    """
    module_type: str
    params: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(frozen=True)

class PlaybookGlobalSettings(BaseModel):
    """
    Optional global settings for the strategy such as instrument tracking and position sizing.
    """
    instrument: str = "NQ"
    multiplier: float = 20.0
    position_size: int = 1
    commission: float = 7.60
    
    model_config = ConfigDict(frozen=True)

class PlaybookConfig(BaseModel):
    """
    JSON-serializable configuration dictating exactly how Theory translates to Execution.
    The strategy is built by defining a sequential pipeline of module steps.
    """
    strategy_id: str
    global_settings: PlaybookGlobalSettings = Field(default_factory=PlaybookGlobalSettings)
    pipeline: List[PlaybookModuleConfig]
    
    model_config = ConfigDict(frozen=True)
