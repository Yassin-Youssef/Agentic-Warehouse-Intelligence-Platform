# =============================================================================
# GET + POST /warehouse/config
# =============================================================================
# GET  /warehouse/config — returns the default WarehouseConfig as JSON.
#   Shows all available parameters and their current defaults.
#
# POST /warehouse/config — accepts partial overrides, returns the merged
#   config. Does NOT persist — just a preview of what the config would
#   look like if you changed certain values.
#
# ConfigOverride uses Optional fields — only the ones you send get
# applied, the rest stay at their defaults.
# =============================================================================

import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from config.warehouse_config import WarehouseConfig

logger = logging.getLogger("api.config")
router = APIRouter(prefix="/warehouse", tags=["config"])

# pydantic model — all fields optional so you only send what you want to change
class ConfigOverride(BaseModel):
    num_robots: Optional[int] = None
    sim_duration_seconds: Optional[int] = None
    random_seed: Optional[int] = None
    base_failure_rate: Optional[float] = None
    high_failure_multiplier: Optional[float] = None
    conveyor_delay_probability: Optional[float] = None
    battery_low_threshold: Optional[float] = None
    pick_duration_mean: Optional[float] = None
    pick_duration_std: Optional[float] = None
    overload_interval_mean_seconds: Optional[float] = None

@router.get("/config")
async def get_config() -> Dict[str, Any]:
    """Return the current default config as JSON."""
    try:
        return WarehouseConfig().model_dump()
    except Exception as e:
        logger.exception("Failed to retrieve config")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/config")
async def preview_config(body: ConfigOverride) -> Dict[str, Any]:
    """Preview what the config would look like with your overrides applied."""
    try:
        config = WarehouseConfig()
        # only apply fields that were actually sent (not None)
        for field_name in body.model_fields:
            value = getattr(body, field_name)
            if value is not None:
                setattr(config, field_name, value)
        return config.model_dump()
    except Exception as e:
        logger.exception("Config preview failed")
        raise HTTPException(status_code=500, detail=str(e))
