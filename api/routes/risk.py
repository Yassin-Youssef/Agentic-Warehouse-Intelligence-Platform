# =============================================================================
# GET /warehouse/risk
# =============================================================================
# Runs the risk-focused Phase 3 agents through the API.
# Only runs 2 of the 5 agents:
#   - Bottleneck Diagnosis Agent
#   - Risk Forecast Agent
#
# Separated from /optimization so you can get just risk analysis
# without waiting for all 5 agents (~30 seconds faster).
#
# Optional query param: ?analysis_file=analysis_report_20260303_153651.json
# Returns: {agent_reports: [...], generated_at: timestamp}
# =============================================================================

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from agents.bottleneck_diagnosis_agent import BottleneckDiagnosisAgent
from agents.risk_forecast_agent import RiskForecastAgent

logger = logging.getLogger("api.risk")
router = APIRouter(prefix="/warehouse", tags=["risk"])

def _load_analysis(outputs_dir: Path, filename: Optional[str]) -> tuple:
    """Load a specific or the latest analysis_report_*.json."""
    if filename:
        path = outputs_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), filename
    files = sorted(outputs_dir.glob("analysis_report_*.json"))
    if not files:
        raise FileNotFoundError("No analysis reports found in outputs/")
    latest = files[-1]
    with open(latest, "r", encoding="utf-8") as f:
        return json.load(f), latest.name

@router.get("/risk")
async def run_risk(
    analysis_file: Optional[str] = Query(None, description="Specific analysis file in outputs/"),
) -> Dict[str, Any]:
    """Run 2 risk-focused agents on the analysis report."""
    try:
        outputs_dir = _project_root / "outputs"
        report, source = _load_analysis(outputs_dir, analysis_file)

        # only the 2 risk-related agents
        agents = [
            BottleneckDiagnosisAgent(),
            RiskForecastAgent(),
        ]

        agent_reports: List[Dict[str, Any]] = []
        for agent in agents:
            output = agent.run(report)
            agent_reports.append(output.model_dump())

        return {"agent_reports": agent_reports, "generated_at": datetime.now().isoformat()}

    except Exception as e:
        logger.exception("Risk agents failed")
        raise HTTPException(status_code=500, detail=str(e))
