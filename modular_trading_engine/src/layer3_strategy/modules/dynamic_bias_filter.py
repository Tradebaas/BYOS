from src.layer3_strategy.modules.base import BaseStrategyModule
from src.layer3_strategy.pipeline_context import PipelineContext

class DynamicBiasFilter(BaseStrategyModule):
    """
    Implements a structural Premium/Discount (PD) filter.
    Looks back N candles, finds equilibrium (Highest High + Lowest Low) / 2.
    Rejects setups if they trade against the equilibrium bias.
    """
    def process(self, context: PipelineContext) -> None:
        if not context.setup_candidates:
            return
            
        window = self.params.get('window', 200)
        history = context.theory_state.history
        
        # If not enough history, we can either pass or block. We'll pass for robustness during warmup.
        if len(history) < window:
            return
            
        recent_candles = history[-window:]
        highest_high = max(c.high for c in recent_candles)
        lowest_low = min(c.low for c in recent_candles)
        
        equilibrium = (highest_high + lowest_low) / 2.0
        
        current_price = history[-1].close
        
        survivors = []
        for tracker in context.setup_candidates:
            level = tracker.level_data
            
            if level.is_bullish:
                # LONG Setup: Should be in DISCOUNT (Below Equilibrium)
                if current_price <= equilibrium:
                    survivors.append(tracker)
            else:
                # SHORT Setup: Should be in PREMIUM (Above Equilibrium)
                if current_price >= equilibrium:
                    survivors.append(tracker)
                    
        context.setup_candidates = survivors
