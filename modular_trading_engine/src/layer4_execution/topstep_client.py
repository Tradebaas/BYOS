import requests
import logging
from typing import Optional
from src.layer3_strategy.models import OrderIntent
from src.layer4_execution.models_broker import TopstepCredentials, TopstepOrderResponse

logger = logging.getLogger(__name__)

class TopstepClient:
    """
    Client for interacting with the TopstepX (ProjectX) REST API.
    Handles dynamic contract resolution and precise payload translation
    for automated algorithmic trade execution.
    """
    BASE_URL = "https://api.topstepx.com/api"

    def __init__(self, credentials: TopstepCredentials, tick_size: float = 0.25):
        self.credentials = credentials
        self.tick_size = tick_size
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.credentials.jwt_token}",
            "Content-Type": "application/json"
        })

    def _get_active_contract(self, base_symbol: str = "NQ") -> Optional[str]:
        """
        Dynamically fetches the active contract ID (e.g., CON.F.US.ENQ.M25).
        Resolves the target symbol prefix dynamically.
        """
        if base_symbol == "NQ":
            target_symbol = "F.US.ENQ"
        elif base_symbol == "YM":
            target_symbol = "F.US.YM"
        elif base_symbol == "ES":
            target_symbol = "F.US.EP"
        else:
            target_symbol = f"F.US.{base_symbol}"

        payload = {"live": False, "searchText": base_symbol}
        
        try:
            response = self._session.post(f"{self.BASE_URL}/Contract/search", json=payload)
            response.raise_for_status()
            data = response.json()
            
            contracts = data.get("contracts", [])
            for c in contracts:
                if c.get("activeContract") is True and c.get("symbolId") == target_symbol:
                    return c.get("id")
                    
            logger.error(f"Active contract for {target_symbol} not found in search results.")
            return None
        except Exception as e:
            logger.error(f"Failed to fetch active contract: {e}")
            return None

    def _build_payload(self, intent: OrderIntent, contract_id: str, size: int) -> dict:
        """
        Vertaalt een OrderIntent direct naar een dictonary structuur die voldoet aan Topstep's regels.
        """
        side = 0 if intent.is_bullish else 1

        # Distance = (Target_Price - Entry_Price) / Tick_Size
        sl_ticks = int(round((intent.stop_loss - intent.entry_price) / self.tick_size))
        tp_ticks = int(round((intent.take_profit - intent.entry_price) / self.tick_size))

        return {
            "accountId": self.credentials.account_id,
            "contractId": contract_id,
            "type": 1,                     # 1 = Limit Order (for the entry)
            "limitPrice": intent.entry_price, # The exact entry limit price
            "side": side,
            "size": size,
            "stopLossBracket": {
                "ticks": sl_ticks,
                "type": 4                  # 4 = Stop Market
            },
            "takeProfitBracket": {
                "ticks": tp_ticks,
                "type": 1                  # 1 = Limit
            }
        }

    def execute_intent(self, intent: OrderIntent, base_symbol: str = "NQ", size: int = 1) -> TopstepOrderResponse:
        """
        Translates a Layer 3 OrderIntent into a Topstep 'Order/place' OCO payload.
        Ensures strict compliance with absolute +/- ticks formatting.
        """
        contract_id = self._get_active_contract(base_symbol)
        if not contract_id:
            return TopstepOrderResponse(success=False, error_message="Could not resolve active contract", error_code=8)

        payload = self._build_payload(intent, contract_id, size)

        try:
            response = self._session.post(f"{self.BASE_URL}/Order/place", json=payload)
            
            # Non-2xx response code (e.g. 400 Bad Request)
            if not response.ok:
                error_msg = response.text
                return TopstepOrderResponse(success=False, error_message=error_msg, error_code=response.status_code)
                
            data = response.json()
            
            # The API often returns 200 OK but sets error Code within body (like Code 2)
            if data.get("error"):
                e_code = data.get("error")
                return TopstepOrderResponse(success=False, error_message="Topstep Logic Error", error_code=e_code)
                
            return TopstepOrderResponse(success=True, order_id=data.get("orderId", 0))
            
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return TopstepOrderResponse(success=False, error_message=str(e))
