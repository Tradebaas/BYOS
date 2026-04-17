from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import sys

# Ensure imports work regardless of execution location
root_dir = str(Path(__file__).parent.parent.parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from modular_trading_engine.src.layer1_data.csv_parser import load_historical_1m_data
from modular_trading_engine.src.layer2_theory.market_state import MarketTheoryState
from modular_trading_engine.src.layer3_strategy.playbook_schema import PlaybookConfig
from modular_trading_engine.src.layer3_strategy.rule_engine import RuleEngine
from modular_trading_engine.src.layer4_execution.data_vault import DataVault
from modular_trading_engine.src.layer4_execution.simulator import BacktestSimulator

router = APIRouter()

from typing import Optional
from datetime import datetime

class BacktestRequest(BaseModel):
    instrument: str = "NQ"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    timeframe: int = 1
    bias_window_size: int = 200
    sl_points: float = 10.0
    tp_points: float = 20.0
    killzone_start_hour: int = 9
    killzone_start_min: int = 20
    killzone_end_hour: int = 9
    killzone_end_min: int = 40
    max_candles_open: int = 30
    tick_size: float = 0.25
    entry_frontrun_ticks: int = 0
    stop_loss_padding_ticks: int = 0

@router.get("/dataset-info/{instrument}")
async def get_dataset_info(instrument: str):
    data_file = Path(root_dir) / "modular_trading_engine" / "data" / "historical" / f"{instrument}_1min.csv"
    if not data_file.exists():
        raise HTTPException(status_code=404, detail="Data file not found")
        
    try:
        # Load minimal data to get first and last candle timestamps
        candles = load_historical_1m_data(data_file)
        if not candles:
            return {"min_date": None, "max_date": None}
            
        min_date = candles[0].timestamp.strftime("%Y-%m-%d")
        max_date = candles[-1].timestamp.strftime("%Y-%m-%d")
        
        return {
            "min_date": min_date,
            "max_date": max_date
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import json
import os

@router.get("/playbooks")
async def list_playbooks():
    playbooks_dir = Path(root_dir) / "modular_trading_engine" / "data" / "playbooks"
    if not playbooks_dir.exists():
        return []
        
    files = [f for f in os.listdir(playbooks_dir) if f.endswith('.json')]
    return files

@router.get("/playbooks/{name}")
async def get_playbook(name: str):
    # Security: prevent path traversal
    if ".." in name or "/" in name:
        raise HTTPException(status_code=400, detail="Invalid playbook name")
        
    playbook_file = Path(root_dir) / "modular_trading_engine" / "data" / "playbooks" / name
    if not playbook_file.exists():
        raise HTTPException(status_code=404, detail="Playbook not found")
        
    try:
        with open(playbook_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/backtest")
async def run_backtest_endpoint(req: BacktestRequest):
    try:
        # Build the Playbook configuration dynamically from request
        playbook_dict = {
            "strategy_id": "Dashboard-Backtest-Params",
            "pipeline": [
                {
                    "module_type": "ConfirmationHoldLevelTrigger",
                    "params": {
                        "bias_window_size": req.bias_window_size
                    }
                },
                {
                    "module_type": "KillzoneFilter",
                    "params": {
                        "start_hour": 0,
                        "start_minute": 0,
                        "end_hour": 23,
                        "end_minute": 59,
                        "timezone": "America/New_York",
                        "exclude_windows": [
                            {
                                "start_hour": req.killzone_start_hour,
                                "start_minute": req.killzone_start_min,
                                "end_hour": req.killzone_end_hour,
                                "end_minute": req.killzone_end_min
                            }
                        ]
                    }
                },
                {
                    "module_type": "TTLTimeout",
                    "params": {
                        "max_candles_open": req.max_candles_open
                    }
                },
                {
                    "module_type": "RATLimitOrder",
                    "params": {
                        "tick_size": req.tick_size,
                        "entry_frontrun_ticks": req.entry_frontrun_ticks,
                        "stop_loss_padding_ticks": req.stop_loss_padding_ticks,
                        "absolute_sl_points": req.sl_points,
                        "absolute_tp_points": req.tp_points
                    }
                }
            ]
        }
        
        playbook_config = PlaybookConfig(**playbook_dict)
        
        # Initialize
        data_file = Path(root_dir) / "modular_trading_engine" / "data" / "historical" / f"{req.instrument}_1min.csv"
        if not data_file.exists():
            raise HTTPException(status_code=404, detail=f"Data file not found for {req.instrument}")
            
        candles = load_historical_1m_data(data_file)
        if not candles:
            raise HTTPException(status_code=400, detail="Empty historical dataset")

        from datetime import timezone
        from modular_trading_engine.src.layer1_data.models import Candle
        
        # 1. Date Filtering
        if req.start_date:
            try:
                sd = datetime.fromisoformat(req.start_date.replace('Z', '+00:00'))
                if not sd.tzinfo: sd = sd.replace(tzinfo=timezone.utc)
                candles = [c for c in candles if c.timestamp >= sd]
            except ValueError:
                pass
                
        if req.end_date:
            try:
                ed = datetime.fromisoformat(req.end_date.replace('Z', '+00:00'))
                if not ed.tzinfo: ed = ed.replace(tzinfo=timezone.utc)
                candles = [c for c in candles if c.timestamp <= ed]
            except ValueError:
                pass

        # 2. Timeframe Resampling
        if req.timeframe > 1:
            resampled = []
            current_chunk = []
            curr_slot = None
            
            for c in candles:
                slot_minute = (c.timestamp.minute // req.timeframe) * req.timeframe
                slot_start = c.timestamp.replace(minute=slot_minute, second=0, microsecond=0)
                
                if curr_slot != slot_start:
                    if current_chunk:
                        resampled.append(Candle(
                            timestamp=curr_slot,
                            open=current_chunk[0].open,
                            high=max(x.high for x in current_chunk),
                            low=min(x.low for x in current_chunk),
                            close=current_chunk[-1].close,
                            volume=sum(x.volume for x in current_chunk)
                        ))
                    current_chunk = [c]
                    curr_slot = slot_start
                else:
                    current_chunk.append(c)
                    
            if current_chunk:
                resampled.append(Candle(
                    timestamp=curr_slot,
                    open=current_chunk[0].open,
                    high=max(x.high for x in current_chunk),
                    low=min(x.low for x in current_chunk),
                    close=current_chunk[-1].close,
                    volume=sum(x.volume for x in current_chunk)
                ))
            candles = resampled

        if not candles:
             raise HTTPException(status_code=400, detail="No candles found with these filters")

        theory_state = MarketTheoryState()
        rule_engine = RuleEngine(playbook_config)
        data_vault = DataVault()
        simulator = BacktestSimulator(vault=data_vault)
        
        # Simulate over all candles
        for candle in candles:
            theory_state.process_candle(candle)
            intents = rule_engine.evaluate(theory_state=theory_state, timestamp=candle.timestamp)
            for intent in intents:
                simulator.stage_order(intent)
            simulator.process_candle(candle)
            
        # Calculate stats
        trades = data_vault.trades
        total_trades = len(trades)
        
        if total_trades == 0:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "max_drawdown": 0.0,
                "trades": []
            }
            
        wins = [t for t in trades if t.win]
        win_rate = (len(wins) / total_trades) * 100
        total_pnl_points = sum(t.pnl_points for t in trades)
        
        # Drawdown calculation
        max_drawdown = 0.0
        peak = 0.0
        cumulative = 0.0
        for t in trades:
            cumulative += t.pnl_points
            if cumulative > peak:
                peak = cumulative
            drawdown = peak - cumulative
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                
        # Format trades
        formatted_trades = []
        for t in trades[-50:]:  # Return last 50 trades to limit payload
            formatted_trades.append({
                "time": t.entry_time.isoformat(),
                "direction": "LONG" if t.is_bullish else "SHORT",
                "entry_price": round(t.entry_price, 2),
                "pnl": round(t.pnl_points, 2),
                "win": t.win,
                "mfe": round(t.mfe, 2),
                "mae": round(t.mae, 2)
            })
            
        return {
            "total_trades": total_trades,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl_points, 2),
            "max_drawdown": round(max_drawdown, 2),
            "trades": formatted_trades
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
