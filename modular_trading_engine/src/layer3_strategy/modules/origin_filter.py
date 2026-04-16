from src.layer3_strategy.modules.base import BaseStrategyModule
from src.layer3_strategy.pipeline_context import PipelineContext

class OriginHighlanderFilter(BaseStrategyModule):
    def process(self, context: PipelineContext) -> None:
        max_tests = self.params.get('max_level_tests_allowed', 3)
        # De Highlander Regel: De oudste actieve Origin Level dicteert de polariteit.
        # Als deze exhausted is (test_count > max_tests), dicteert hij NOG STEEDS de
        # richting, maar weigeren we trades op hemzelf. Nieuwere Origins mogen wel
        # getrade worden zolang ze dezelfde polariteit hebben.
        from src.layer2_theory.models import LevelType
        for tracker in context.theory_state.origin_trackers:
            if tracker.is_active and tracker.level_data.level_type == LevelType.ORIGIN_LEVEL:
                # De eerste actieve Origin is per definitie de Highlander.
                context.active_polarity_is_bullish = tracker.level_data.is_bullish
                
                # Check of Er tenminste één Origin Level in deze richting is die NIET exhausted is
                has_tradable = False
                for ot in context.theory_state.origin_trackers:
                    if ot.is_active and ot.level_data.level_type == LevelType.ORIGIN_LEVEL:
                        if ot.level_data.is_bullish == context.active_polarity_is_bullish:
                            if getattr(ot, 'test_count', 0) <= max_tests:
                                has_tradable = True
                                break
                                
                if not has_tradable:
                    context.active_polarity_is_bullish = None
                break
