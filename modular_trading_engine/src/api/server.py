import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import json

import sys
from pathlib import Path
from fastapi.staticfiles import StaticFiles

# Add project root to path
root_dir = str(Path(__file__).parent.parent.parent.parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from modular_trading_engine.src.layer4_execution.live_fleet_commander import LiveFleetCommander
from modular_trading_engine.src.api.backtest_router import router as backtest_router

logger = logging.getLogger("FastAPIServer")

commander = LiveFleetCommander()
active_connections = set()

def datetime_handler(x):
    if isinstance(x, datetime):
        return x.isoformat()
    raise TypeError("Unknown type")

async def broadcast_state():
    """ Periodically fetch state from commander's engine and broadcast """
    while True:
        try:
            if active_connections:
                state = commander.engine.get_state()
                payload = {"levels": state}
                
                # Serialize datetime using default=str
                json_payload = json.dumps(payload, default=str)
                # Clean up closed connections
                disconnected = set()
                for connection in list(active_connections):
                    try:
                        await connection.send_text(json_payload)
                    except Exception:
                        disconnected.add(connection)
                
                for conn in disconnected:
                    active_connections.discard(conn)
                    
        except Exception as e:
            logger.error(f"Error in broadcast loop: {e}")
            
        await asyncio.sleep(1) # Broadcast every 1 second

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    logger.info("Starting Fleet Commander and Broadcast Loop...")
    init_success = await commander.initialize()
    if not init_success:
        logger.error("Fleet Commander failed to initialize. Exiting.")
        return
        
    loop_task = asyncio.create_task(commander.run_forever())
    broadcast_task = asyncio.create_task(broadcast_state())
    
    yield
    
    # SHUTDOWN
    logger.info("Shutting down Fleet Commander...")
    loop_task.cancel()
    broadcast_task.cancel()
    try:
        await loop_task
        await broadcast_task
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For dashboard
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    try:
        while True:
            await websocket.receive_text() # Keep connection alive
    except WebSocketDisconnect:
        active_connections.discard(websocket)

@app.get("/api/state")
async def get_state():
    """ REST fallback for state fetching """
    return {"levels": commander.engine.get_state()}

app.include_router(backtest_router, prefix="/api/v1")

# Mount Static UI for Backtest Engine
ui_dir = Path(root_dir) / "modular_trading_engine" / "backtest_ui"
if ui_dir.exists():
    app.mount("/dashboard", StaticFiles(directory=str(ui_dir), html=True), name="backtest_dashboard")
