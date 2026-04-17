from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys
from pathlib import Path
from fastapi.staticfiles import StaticFiles

# Add project root to path
root_dir = str(Path(__file__).parent.parent.parent.parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from modular_trading_engine.src.api.backtest_router import router as backtest_router

# Create app WITHOUT the live lifespan
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For dashboard
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(backtest_router, prefix="/api/v1")

# Mount Static UI for Backtest Engine
ui_dir = Path(root_dir) / "modular_trading_engine" / "backtest_ui"
if ui_dir.exists():
    app.mount("/dashboard", StaticFiles(directory=str(ui_dir), html=True), name="backtest_dashboard")
