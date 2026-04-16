from src.layer3_strategy.modules.base import BaseStrategyModule
from src.layer3_strategy.pipeline_context import PipelineContext

class TTLTimeout(BaseStrategyModule):
    def process(self, context: PipelineContext) -> None:
        max_candles = self.params.get('max_candles_open', 20)
        
        valid_candidates = []
        for tracker in context.setup_candidates:
            # Assumes 1-minute candle timeframe resolution
            delta = context.timestamp - tracker.level_data.timestamp
            candles_open = delta.total_seconds() / 60.0
            
            if candles_open <= max_candles:
                valid_candidates.append(tracker)
                
        context.setup_candidates = valid_candidates
