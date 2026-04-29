from curl_cffi import requests
import logging
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Optional, List

from src.layer1_data.models import Candle
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
        self._session = requests.Session(impersonate="chrome120")
        self._session.headers.update({
            "Authorization": f"Bearer {self.credentials.jwt_token}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    CHART_API_URL = "https://chartapi.topstepx.com/History/v2"

    def fetch_historical_bars(self, symbol: str = "/NQ", resolution: str = "1", lookback_mins: int = 1000) -> List[Candle]:
        """
        Fetches historical candles directly from the TopstepX Chart API.
        Used to 'warm up' the engine with pre-loaded 1-minute tracking data.
        """
        end_time_sec = int(time.time())
        start_time_sec = end_time_sec - (lookback_mins * 60)
        
        params = {
            "Symbol": symbol,
            "Resolution": resolution,
            "From": start_time_sec,
            "To": end_time_sec
        }
        
        # Build the exact URL parameters
        url = f"{self.CHART_API_URL}?{urllib.parse.urlencode(params)}"
        
        # We need specific headers to safely fetch chart data without getting blocked
        headers = {
            "Authorization": f"Bearer {self.credentials.jwt_token}",
            "Origin": "https://www.topstepx.com",
            "x-app-type": "web",
            "x-app-version": "1.22.50",
            "Accept": "application/json"
        }
        
        candles: List[Candle] = []
        try:
            logger.debug(f"Fetching {lookback_mins} minutes of historical data for {symbol} ...")
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            bars = data.get("bars", [])
            # Sort chronologically (ascending time) so the engine can process them sequentially
            bars = sorted(bars, key=lambda x: x.get("t", 0))
            
            for b in bars:
                raw_t = b.get("t", 0)
                if raw_t > 1e11: # usually ms if very large
                    dt = datetime.fromtimestamp(raw_t / 1000.0, tz=timezone.utc)
                else:
                    dt = datetime.fromtimestamp(raw_t, tz=timezone.utc)
                    
                candle = Candle(
                    timestamp=dt,
                    open=float(b.get("o", 0.0)),
                    high=float(b.get("h", 0.0)),
                    low=float(b.get("l", 0.0)),
                    close=float(b.get("c", 0.0)),
                    volume=float(b.get("v", 0.0))
                )
                candles.append(candle)
                
            logger.debug(f"Successfully fetched and sorted {len(candles)} historical candles for {symbol}.")
            return candles
            
        except Exception as e:
            logger.error(f"Failed to fetch historical bars from Chart API: {e}")
            return []

    def fetch_historical_bars_range(self, from_sec: int, to_sec: int, symbol: str = "/NQ", resolution: str = "1") -> List[Candle]:
        """
        Fetches historical candles directly from the TopstepX Chart API for a specific time window.
        Used specifically for building and updating the local Data Lake.
        """
        params = {
            "Symbol": symbol,
            "Resolution": resolution,
            "From": from_sec,
            "To": to_sec
        }
        
        url = f"{self.CHART_API_URL}?{urllib.parse.urlencode(params)}"
        
        headers = {
            "Authorization": f"Bearer {self.credentials.jwt_token}",
            "Origin": "https://www.topstepx.com",
            "x-app-type": "web",
            "x-app-version": "1.22.50",
            "Accept": "application/json"
        }
        
        candles: List[Candle] = []
        try:
            logger.info(f"Fetching historical data for {symbol} from TS {from_sec} to {to_sec}...")
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            bars = data.get("bars", [])
            bars = sorted(bars, key=lambda x: x.get("t", 0))
            
            for b in bars:
                raw_t = b.get("t", 0)
                if raw_t > 1e11: # usually ms if very large
                    dt = datetime.fromtimestamp(raw_t / 1000.0, tz=timezone.utc)
                else:
                    dt = datetime.fromtimestamp(raw_t, tz=timezone.utc)
                    
                candle = Candle(
                    timestamp=dt,
                    open=float(b.get("o", 0.0)),
                    high=float(b.get("h", 0.0)),
                    low=float(b.get("l", 0.0)),
                    close=float(b.get("c", 0.0)),
                    volume=float(b.get("v", 0.0))
                )
                candles.append(candle)
                
            logger.info(f"Successfully fetched {len(candles)} historical candles.")
            return candles
            
        except Exception as e:
            logger.error(f"Failed to fetch historical bars range from Chart API: {e}")
            return []

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

        # Defensieve Polariteit (Positief vs Negatief) via absolute math om wees-orders en API fails te voorkomen
        sl_abs = abs(int(round((intent.stop_loss - intent.entry_price) / self.tick_size)))
        tp_abs = abs(int(round((intent.take_profit - intent.entry_price) / self.tick_size)))

        # Lange posities (Buy - Side 0): TP moet positief zijn (+), SL moet negatief zijn (-).
        # Korte posities (Sell - Side 1): TP moet negatief zijn (-), SL moet positief zijn (+).
        if intent.is_bullish:
            sl_ticks = -sl_abs
            tp_ticks = tp_abs
        else:
            sl_ticks = sl_abs
            tp_ticks = -tp_abs

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
            if data.get("error") or data.get("success") is False:
                e_code = data.get("error") or data.get("errorCode")
                e_msg = data.get("errorMessage") or f"Logic Error: {data}"
                return TopstepOrderResponse(success=False, error_message=e_msg, error_code=e_code)
                
            order_id = data.get("orderId", 0)
            if not order_id:
                # Fallbacks for arrays or nested ids the Topstep API might randomly use
                if isinstance(data, dict) and "id" in data:
                    order_id = data["id"]
                elif isinstance(data, list) and len(data) > 0:
                    order_id = data[0].get("id", data[0].get("orderId", 0))
                else:    
                    logger.warning(f"Raw API REST Response missing orderId key: {data}")
                    
            return TopstepOrderResponse(success=True, order_id=order_id)
            
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return TopstepOrderResponse(success=False, error_message=str(e))

    def cancel_order(self, order_id: int) -> bool:
        """
        Cancels a specific order by ID.
        """
        payload = {
            "accountId": self.credentials.account_id,
            "orderId": order_id
        }
        try:
            response = self._session.post(f"{self.BASE_URL}/Order/cancel", json=payload)
            return response.ok
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def modify_order(self, order_id: int, new_price: float, is_stop: bool = True) -> bool:
        """
        Modifies a working order in TopstepX.
        Specifically designed to update the StopLoss bracket to a new breakeven price.
        Uses POST /Order/replace.
        """
        payload = {
            "accountId": self.credentials.account_id,
            "orderId": order_id,
        }
        
        # Voor Stop Market orders gebruiken we 'stopPrice', voor limits 'limitPrice'
        if is_stop:
            payload["stopPrice"] = new_price
        else:
            payload["limitPrice"] = new_price
            
        try:
            # We assume TopstepX uses /Order/replace for modifications.
            response = self._session.post(f"{self.BASE_URL}/Order/replace", json=payload)
            if not response.ok:
                logger.error(f"Failed to modify order {order_id}. HTTP {response.status_code}: {response.text}")
                return False
            return True
        except Exception as e:
            logger.error(f"Exception during order modification for {order_id}: {e}")
            return False

    def cancel_all_orders(self, base_symbol: str = "NQ") -> bool:
        """
        Annuleert alle pending (working) entry orders op dit account/target om state schoon te vegen.
        Omdat Topstep/ProjectX geen bulk-cancel heeft, itereren we over actieve orders.
        """
        contract_id = self._get_active_contract(base_symbol)
        if not contract_id:
            return False
            
        try:
            # Fetch explicitly to ensure we have the live order book
            response = self._session.get(f"https://userapi.topstepx.com/Order?accountId={self.credentials.account_id}")
            if not response.ok:
                logger.error("CancelAll failed to fetch current live orders.")
                return False
                
            orders = response.json()
            if not isinstance(orders, list):
                return False
                
            success_overall = True
            for o in orders:
                if o.get("status") in [1, "Working", "Pending"]:
                    # Only cancel orders matching the specific contract we requested
                    if str(o.get("contractId")) == str(contract_id):
                        o_id = o.get("id") or o.get("orderId")
                        if o_id:
                            logger.info(f"Issuing Cancel instruction for OrderID {o_id}...")
                            res = self.cancel_order(o_id)
                            if not res:
                                success_overall = False
            return success_overall
            
        except Exception as e:
            logger.error(f"Failed in CancelAll wrapper: {e}")
            return False

    def flatten_position(self, base_symbol: str = "NQ") -> bool:
        """
        Noodstop: Rucksichtlos flatten van de actieve positie.
        """
        contract_id = self._get_active_contract(base_symbol)
        if not contract_id:
            return False
            
        payload = {
            "accountId": self.credentials.account_id,
            "contractId": contract_id
        }
        try:
            response = self._session.post(f"{self.BASE_URL}/Position/close", json=payload)
            return response.ok
        except Exception as e:
            logger.error(f"Failed to Flatten: {e}")
            return False