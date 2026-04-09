import json
from pathlib import Path
from src.layer3_strategy.playbook_schema import PlaybookConfig

class ConfigParser:
    """
    Strict parser for translating declarative JSON strategy rule sets
    into immutable backend Pydantic models.
    """
    
    @staticmethod
    def load_playbook(filepath: str) -> PlaybookConfig:
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Strategy playbook not found at {filepath}")
            
        with open(path, "r") as f:
            data = json.load(f)
            
        return PlaybookConfig(**data)
