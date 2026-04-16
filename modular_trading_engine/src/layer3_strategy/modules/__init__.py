from src.layer3_strategy.modules.origin_filter import OriginHighlanderFilter
from src.layer3_strategy.modules.hold_level_trigger import VirginHoldLevelTrigger
from src.layer3_strategy.modules.confirmation_hold_level_trigger import ConfirmationHoldLevelTrigger
from src.layer3_strategy.modules.ttl_timeout import TTLTimeout
from src.layer3_strategy.modules.limit_order_execution import RATLimitOrder
from src.layer3_strategy.modules.killzone_filter import KillzoneFilter
from src.layer3_strategy.modules.dynamic_bias_filter import DynamicBiasFilter

MODULE_REGISTRY = {
    "OriginHighlanderFilter": OriginHighlanderFilter,
    "VirginHoldLevelTrigger": VirginHoldLevelTrigger,
    "ConfirmationHoldLevelTrigger": ConfirmationHoldLevelTrigger,
    "TTLTimeout": TTLTimeout,
    "RATLimitOrder": RATLimitOrder,
    "KillzoneFilter": KillzoneFilter,
    "DynamicBiasFilter": DynamicBiasFilter
}
