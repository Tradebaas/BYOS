"""
TopstepX Real-Time Market Data Client (SignalR WebSocket)

Standalone, additive module that connects to the TopstepX Market Hub
via SignalR to receive real-time tick data, quotes, and DOM depth.

This module does NOT modify or depend on any existing production code.
It receives its JWT and contract_id as constructor parameters.

Architecture:
    rtc.topstepx.com/hubs/market (SignalR)
        ├── SubscribeContractTrades   → GatewayTrade  (tick-by-tick)
        ├── SubscribeContractQuotes   → GatewayQuote  (BBO + OHLC)
        └── SubscribeContractMarketDepth → GatewayDepth (L2 DOM, optional)
"""

import asyncio
import logging
import ssl
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Deque, Callable

from pysignalr.client import SignalRClient

logger = logging.getLogger("TopstepRealtime")

# ─────────────────────────────────────────────────────────────────────
# Data Models (lightweight dataclasses, no Pydantic to stay decoupled)
# ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Tick:
    """Single executed trade on the exchange (Time & Sales)."""
    timestamp: datetime
    price: float
    volume: int
    side: str        # "BUY" or "SELL"
    symbol_id: str


@dataclass(frozen=True)
class Quote:
    """Best Bid/Offer snapshot with session OHLCV."""
    timestamp: datetime
    last_price: float
    best_bid: float
    best_ask: float
    spread: float
    high: float
    low: float
    open: float
    volume: int
    symbol_id: str


@dataclass(frozen=True)
class DepthLevel:
    """Single DOM price level update."""
    timestamp: datetime
    price: float
    volume: int
    level_type: str   # "BID", "ASK", "TRADE", etc.


# ─────────────────────────────────────────────────────────────────────
# TickBuffer — Thread-safe, bounded in-memory ring buffer
# ─────────────────────────────────────────────────────────────────────

class TickBuffer:
    """
    Thread-safe ring buffer for real-time market data.
    Uses collections.deque(maxlen) to auto-evict old data and bound memory.
    
    Designed to be consumed by external modules (e.g. trailing TP logic)
    without any coupling to the SignalR transport layer.
    """
    
    def __init__(self, max_ticks: int = 10_000, max_quotes: int = 1_000, max_depth: int = 5_000):
        self._lock = threading.Lock()
        
        self._ticks: Deque[Tick] = deque(maxlen=max_ticks)
        self._quotes: Deque[Quote] = deque(maxlen=max_quotes)
        self._depth: Deque[DepthLevel] = deque(maxlen=max_depth)
        
        # Fast-access latest values (atomic reads, no lock needed for simple floats)
        self._latest_price: float = 0.0
        self._latest_bid: float = 0.0
        self._latest_ask: float = 0.0
        self._tick_count: int = 0
        self._quote_count: int = 0
    
    # ── Write interface (called by SignalR handlers) ──────────────────
    
    def add_tick(self, tick: Tick) -> None:
        with self._lock:
            self._ticks.append(tick)
            self._latest_price = tick.price
            self._tick_count += 1
    
    def add_quote(self, quote: Quote) -> None:
        with self._lock:
            self._quotes.append(quote)
            self._latest_bid = quote.best_bid
            self._latest_ask = quote.best_ask
            self._latest_price = quote.last_price
            self._quote_count += 1
    
    def add_depth(self, level: DepthLevel) -> None:
        with self._lock:
            self._depth.append(level)
    
    # ── Read interface (consumed by strategy / trailing TP logic) ─────
    
    @property
    def latest_price(self) -> float:
        return self._latest_price
    
    @property
    def latest_bid(self) -> float:
        return self._latest_bid
    
    @property
    def latest_ask(self) -> float:
        return self._latest_ask
    
    @property
    def current_spread(self) -> float:
        if self._latest_bid > 0 and self._latest_ask > 0:
            return round(self._latest_ask - self._latest_bid, 4)
        return 0.0
    
    @property
    def tick_count(self) -> int:
        return self._tick_count
    
    @property
    def quote_count(self) -> int:
        return self._quote_count
    
    def ticks_since(self, since: datetime) -> List[Tick]:
        """Returns all buffered ticks after the given timestamp."""
        with self._lock:
            return [t for t in self._ticks if t.timestamp >= since]
    
    def latest_ticks(self, n: int = 100) -> List[Tick]:
        """Returns the N most recent ticks."""
        with self._lock:
            items = list(self._ticks)
            return items[-n:] if len(items) > n else items
    
    def latest_quotes(self, n: int = 10) -> List[Quote]:
        """Returns the N most recent quotes."""
        with self._lock:
            items = list(self._quotes)
            return items[-n:] if len(items) > n else items
    
    def stats(self) -> dict:
        """Quick diagnostic summary."""
        return {
            "tick_count": self._tick_count,
            "quote_count": self._quote_count,
            "buffer_ticks": len(self._ticks),
            "buffer_quotes": len(self._quotes),
            "buffer_depth": len(self._depth),
            "latest_price": self._latest_price,
            "latest_bid": self._latest_bid,
            "latest_ask": self._latest_ask,
            "spread": self.current_spread,
        }


# ─────────────────────────────────────────────────────────────────────
# DOM Type Enum (from ProjectX API docs)
# ─────────────────────────────────────────────────────────────────────

DOM_TYPES = {
    0: "UNKNOWN",
    1: "ASK",
    2: "BID",
    3: "BEST_ASK",
    4: "BEST_BID",
    5: "TRADE",
    6: "RESET",
    7: "LOW",
    8: "HIGH",
    9: "NEW_BEST_BID",
    10: "NEW_BEST_ASK",
    11: "FILL",
}


# ─────────────────────────────────────────────────────────────────────
# TopstepRealtimeClient — SignalR Market Hub Connection
# ─────────────────────────────────────────────────────────────────────

class TopstepRealtimeClient:
    """
    Standalone SignalR client for real-time TopstepX market data.
    
    Connects to: wss://rtc.topstepx.com/hubs/market
    Subscribes to: Trades (ticks), Quotes (BBO), and optionally DOM Depth.
    
    Usage:
        buffer = TickBuffer()
        client = TopstepRealtimeClient(
            jwt_token="eyJ...",
            contract_id="CON.F.US.ENQ.M25",
            buffer=buffer
        )
        await client.start()  # blocks while connected
    """
    
    MARKET_HUB_URL = "https://rtc.topstepx.com/hubs/market"
    
    def __init__(
        self,
        jwt_token: str,
        contract_id: str,
        buffer: TickBuffer,
        enable_depth: bool = False,
        on_tick_callback: Optional[Callable[[Tick], None]] = None,
    ):
        self.jwt_token = jwt_token
        self.contract_id = contract_id
        self.buffer = buffer
        self.enable_depth = enable_depth
        self.on_tick_callback = on_tick_callback
        
        self._connected = False
        self._client: Optional[SignalRClient] = None
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    def _build_hub_url(self) -> str:
        """Constructs the authenticated SignalR hub URL."""
        return f"{self.MARKET_HUB_URL}?access_token={self.jwt_token}"
    
    @staticmethod
    def _create_ssl_context() -> ssl.SSLContext:
        """Creates an SSL context for the WebSocket connection.
        
        Bypasses certificate verification to work around macOS
        certificate chain issues with the TopstepX Kestrel server.
        """
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    
    # ── SignalR Event Handlers ────────────────────────────────────────
    
    async def _on_open(self) -> None:
        """Called when the WebSocket connection is established."""
        self._connected = True
        logger.info(f"🟢 Connected to TopstepX Market Hub")
        logger.info(f"   Contract: {self.contract_id}")
        logger.info(f"   DOM Depth: {'enabled' if self.enable_depth else 'disabled'}")
    
    async def _on_close(self) -> None:
        """Called when the WebSocket connection is closed."""
        self._connected = False
        logger.warning("🔴 Disconnected from TopstepX Market Hub")
    
    async def _on_error(self, message) -> None:
        """Called on SignalR transport errors."""
        self._connected = False
        logger.error(f"⚠️ SignalR Error: {message}")
    
    async def _handle_trade(self, args) -> None:
        """
        Handler for GatewayTrade events (tick-by-tick T&S data).
        
        Actual wire format (verified live 2026-04-28):
            args = (['CON.F.US.ENQ.M26', [{tick1}, {tick2}, ...]],)
        
        Each tick dict: {symbolId, price, timestamp, type, volume, contractId}
        type: 0 = BUY, 1 = SELL
        """
        try:
            # pysignalr delivers args as a tuple of the SignalR invocation arguments
            # For GatewayTrade: args = (['contractId', [list_of_trades]],)
            payload = args[0] if isinstance(args, tuple) else args
            
            # Extract trade list — format: ['CON.F.US.ENQ.M26', [{...}, {...}]]
            if isinstance(payload, list) and len(payload) >= 2:
                trade_list = payload[1]
            elif isinstance(payload, list) and len(payload) == 1:
                trade_list = payload[0] if isinstance(payload[0], list) else [payload[0]]
            elif isinstance(payload, dict):
                trade_list = [payload]
            else:
                logger.debug(f"Unexpected GatewayTrade format: {args}")
                return
            
            # Ensure trade_list is iterable of dicts
            if isinstance(trade_list, dict):
                trade_list = [trade_list]
            
            for data in trade_list:
                if not isinstance(data, dict):
                    continue
                
                # Parse timestamp
                raw_ts = data.get("timestamp", "")
                if isinstance(raw_ts, str) and raw_ts:
                    try:
                        dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                    except ValueError:
                        dt = datetime.now(timezone.utc)
                else:
                    dt = datetime.now(timezone.utc)
                
                # Parse side (0 = Buy, 1 = Sell per TradeLogType enum)
                raw_type = data.get("type", 0)
                side = "BUY" if raw_type == 0 else "SELL"
                
                tick = Tick(
                    timestamp=dt,
                    price=float(data.get("price", 0.0)),
                    volume=int(data.get("volume", 0)),
                    side=side,
                    symbol_id=str(data.get("symbolId", "")),
                )
                
                self.buffer.add_tick(tick)
                
                # Fire optional callback (for external consumers)
                if self.on_tick_callback:
                    self.on_tick_callback(tick)
                
        except Exception as e:
            logger.error(f"Error processing GatewayTrade: {e}")
    
    async def _handle_quote(self, args) -> None:
        """
        Handler for GatewayQuote events (BBO + session stats).
        
        Actual wire format (verified live 2026-04-28):
            args = (['CON.F.US.ENQ.M26', {symbol, lastPrice, bestBid, bestAsk, ...}],)
        
        Note: Some quote updates are partial (e.g. only bestBid/bestAsk without lastPrice).
        """
        try:
            # Unwrap pysignalr tuple
            payload = args[0] if isinstance(args, tuple) else args
            
            if isinstance(payload, list) and len(payload) >= 2:
                data = payload[1]
            elif isinstance(payload, list) and len(payload) == 1:
                data = payload[0]
            elif isinstance(payload, dict):
                data = payload
            else:
                logger.debug(f"Unexpected GatewayQuote format: {args}")
                return
            
            if not isinstance(data, dict):
                return
            
            raw_ts = data.get("timestamp", data.get("lastUpdated", ""))
            if isinstance(raw_ts, str) and raw_ts:
                try:
                    dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                except ValueError:
                    dt = datetime.now(timezone.utc)
            else:
                dt = datetime.now(timezone.utc)
            
            bid = float(data.get("bestBid", 0.0))
            ask = float(data.get("bestAsk", 0.0))
            
            quote = Quote(
                timestamp=dt,
                last_price=float(data.get("lastPrice", 0.0)),
                best_bid=bid,
                best_ask=ask,
                spread=round(ask - bid, 4) if bid > 0 and ask > 0 else 0.0,
                high=float(data.get("high", 0.0)),
                low=float(data.get("low", 0.0)),
                open=float(data.get("open", 0.0)),
                volume=int(data.get("volume", 0)),
                symbol_id=str(data.get("symbol", data.get("symbolId", ""))),
            )
            
            self.buffer.add_quote(quote)
            
        except Exception as e:
            logger.error(f"Error processing GatewayQuote: {e}")
    
    async def _handle_depth(self, args) -> None:
        """
        Handler for GatewayDepth events (Level 2 DOM updates).
        Only active when enable_depth=True.
        
        Expected args format:
            [contractId, {timestamp, type, price, volume, currentVolume}]
        """
        try:
            if isinstance(args, list) and len(args) >= 2:
                data = args[1]
            elif isinstance(args, list) and len(args) == 1:
                data = args[0]
            elif isinstance(args, dict):
                data = args
            else:
                return
            
            raw_ts = data.get("timestamp", "")
            if isinstance(raw_ts, str) and raw_ts:
                try:
                    dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                except ValueError:
                    dt = datetime.now(timezone.utc)
            else:
                dt = datetime.now(timezone.utc)
            
            raw_type = data.get("type", 0)
            level_type = DOM_TYPES.get(raw_type, "UNKNOWN")
            
            depth_level = DepthLevel(
                timestamp=dt,
                price=float(data.get("price", 0.0)),
                volume=int(data.get("volume", data.get("currentVolume", 0))),
                level_type=level_type,
            )
            
            self.buffer.add_depth(depth_level)
            
        except Exception as e:
            logger.error(f"Error processing GatewayDepth: {e}")
    
    # ── Subscription Management ───────────────────────────────────────
    
    async def _subscribe(self) -> None:
        """Subscribes to all requested market data channels."""
        logger.info(f"📡 Subscribing to contract: {self.contract_id}")
        
        await self._client.send("SubscribeContractQuotes", [self.contract_id])
        logger.info("   ✅ Subscribed to Quotes (BBO)")
        
        await self._client.send("SubscribeContractTrades", [self.contract_id])
        logger.info("   ✅ Subscribed to Trades (Ticks)")
        
        if self.enable_depth:
            await self._client.send("SubscribeContractMarketDepth", [self.contract_id])
            logger.info("   ✅ Subscribed to Market Depth (DOM)")
    
    async def _unsubscribe(self) -> None:
        """Unsubscribes from all market data channels."""
        try:
            if self._client:
                await self._client.send("UnsubscribeContractQuotes", [self.contract_id])
                await self._client.send("UnsubscribeContractTrades", [self.contract_id])
                if self.enable_depth:
                    await self._client.send("UnsubscribeContractMarketDepth", [self.contract_id])
                logger.info("📴 Unsubscribed from all market data channels")
        except Exception as e:
            logger.warning(f"Error during unsubscribe: {e}")
    
    # ── Main Lifecycle ────────────────────────────────────────────────
    
    async def start(self) -> None:
        """
        Connects to the TopstepX Market Hub and begins receiving data.
        This is a blocking coroutine — run it as an asyncio task.
        """
        url = self._build_hub_url()
        
        logger.info(f"🔌 Connecting to TopstepX Market Hub...")
        logger.info(f"   URL: {self.MARKET_HUB_URL}")
        logger.info(f"   Contract: {self.contract_id}")
        
        self._client = SignalRClient(url, ssl=self._create_ssl_context())
        
        # Register lifecycle callbacks
        self._client.on_open(self._on_open)
        self._client.on_close(self._on_close)
        self._client.on_error(self._on_error)
        
        # Register market data event handlers
        self._client.on("GatewayTrade", self._handle_trade)
        self._client.on("GatewayQuote", self._handle_quote)
        
        if self.enable_depth:
            self._client.on("GatewayDepth", self._handle_depth)
        
        # Start the client and subscribe once connected
        await asyncio.gather(
            self._client.run(),
            self._subscribe_when_ready(),
        )
    
    async def _subscribe_when_ready(self) -> None:
        """Waits for connection then subscribes to channels."""
        # Give the SignalR handshake a moment to complete
        for _ in range(30):
            if self._connected:
                await self._subscribe()
                return
            await asyncio.sleep(0.5)
        
        logger.error("❌ Timed out waiting for SignalR connection (15s)")
    
    async def stop(self) -> None:
        """Gracefully disconnects from the Market Hub."""
        await self._unsubscribe()
        self._connected = False
        logger.info("🛑 TopstepRealtimeClient stopped")


# ─────────────────────────────────────────────────────────────────────
# Standalone Runner (for testing and future FleetCommander integration)
# ─────────────────────────────────────────────────────────────────────

async def run_realtime_feed(
    jwt_token: str,
    contract_id: str,
    enable_depth: bool = False,
    on_tick_callback: Optional[Callable[[Tick], None]] = None,
) -> TickBuffer:
    """
    Entry point to start the real-time feed as a standalone coroutine.
    
    Returns the TickBuffer which can be queried by external modules.
    The coroutine blocks while the feed is active.
    
    Usage:
        buffer = await run_realtime_feed(jwt_token, contract_id)
    """
    buffer = TickBuffer()
    client = TopstepRealtimeClient(
        jwt_token=jwt_token,
        contract_id=contract_id,
        buffer=buffer,
        enable_depth=enable_depth,
        on_tick_callback=on_tick_callback,
    )
    
    await client.start()
    return buffer
