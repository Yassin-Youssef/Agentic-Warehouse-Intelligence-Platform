# =============================================================================
# POST /warehouse/simulate
# =============================================================================
# Runs Phase 1 (simulation) through the API.
# Accepts optional JSON body to override default config
# (e.g. change num_robots, sim_duration, failure_rate).
# If no body is sent, uses default WarehouseConfig.
#
# Flow:
#   1. Build config (default + any overrides from request body)
#   2. Create WarehouseSimulator and run it
#   3. Save logs to data/ as JSON
#   4. Return: {status, log_file, summary}
#
# Same logic as main_phase1.py, just wrapped in an endpoint.
# =============================================================================

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# make sure project root is importable
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from config.warehouse_config import WarehouseConfig
from simulation.warehouse import WarehouseSimulator

logger = logging.getLogger("api.simulate")
router = APIRouter(prefix="/warehouse", tags=["simulation"])

# pydantic model for optional config overrides in the request body
class SimulateRequest(BaseModel):
    num_robots: Optional[int] = None
    sim_duration_seconds: Optional[int] = None
    random_seed: Optional[int] = None
    base_failure_rate: Optional[float] = None
    conveyor_delay_probability: Optional[float] = None

@router.post("/simulate")
async def run_simulation(body: Optional[SimulateRequest] = None) -> Dict[str, Any]:
    """Run Phase 1 simulation. Optional JSON body overrides default config."""
    try:
        config = WarehouseConfig()

        # apply any overrides from the request body
        if body is not None:
            for field_name in body.model_fields:
                value = getattr(body, field_name)
                if value is not None:
                    setattr(config, field_name, value)

        # run the simulation (same as main_phase1.py)
        sim = WarehouseSimulator(config)
        logs = sim.run()
        summary = sim.get_summary()

        # save logs to data/
        data_dir = _project_root / "data"
        data_dir.mkdir(exist_ok=True)
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"warehouse_logs_{ts_str}.json"
        filepath = data_dir / filename

        output = {
            "logs": [entry.model_dump() for entry in logs],
            "summary": summary.model_dump(),
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, default=str)

        logger.info("Simulation complete — saved to %s", filepath)
        return {"status": "completed", "log_file": filename, "summary": summary.model_dump()}

    except Exception as e:
        logger.exception("Simulation failed")
        raise HTTPException(status_code=500, detail=str(e))
