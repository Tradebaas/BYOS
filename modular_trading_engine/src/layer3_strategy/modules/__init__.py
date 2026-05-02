from src.layer3_strategy.modules.confirmation_hold_level_trigger import ConfirmationHoldLevelTrigger
from src.layer3_strategy.modules.ttl_timeout import TTLTimeout
from src.layer3_strategy.modules.limit_order_execution import RATLimitOrder
from src.layer3_strategy.modules.killzone_filter import KillzoneFilter
from src.layer3_strategy.modules.loss_cooldown_filter import LossCooldownFilter
from src.layer3_strategy.modules.origin_level_trigger import OriginLevelTrigger
from src.layer3_strategy.modules.origin_hold_level_trigger import OriginHoldLevelTrigger

MODULE_REGISTRY = {
    "ConfirmationHoldLevelTrigger": ConfirmationHoldLevelTrigger,
    "TTLTimeout": TTLTimeout,
    "RATLimitOrder": RATLimitOrder,
    "KillzoneFilter": KillzoneFilter,
    "LossCooldownFilter": LossCooldownFilter,
    "OriginLevelTrigger": OriginLevelTrigger,
    "OriginHoldLevelTrigger": OriginHoldLevelTrigger
}
