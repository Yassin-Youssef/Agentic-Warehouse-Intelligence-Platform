# =============================================================================
# GET /warehouse/analysis
# =============================================================================
# Runs Phase 2 (deterministic analysis) through the API.
# Optional query param: ?log_file=warehouse_logs_20260303_145843.json
# If not provided, uses the most recent log from data/.
#
# Flow:
#   1. Load simulation log (specific or latest)
#   2. Run all 5 analyzers (throughput, queue, utilization, downtime, cost)
#   3. Build WarehouseAnalysisReport
#   4. Save to outputs/ as JSON
#   5. Return the full report as JSON response
#
# Same logic as main_phase2.py, just exposed as an API endpoint.
# =============================================================================

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from analysis import (
    throughput_analyzer, queue_analyzer,
    utilization_analyzer, downtime_analyzer, cost_estimator,
)
from schemas.analysis_schema import WarehouseAnalysisReport
from tools.log_loader import load_latest_log, load_log

logger = logging.getLogger("api.analysis")
router = APIRouter(prefix="/warehouse", tags=["analysis"])

@router.get("/analysis")
async def run_analysis(
    log_file: Optional[str] = Query(None, description="Specific log file in data/"),
) -> Dict[str, Any]:
    """Run Phase 2 analysis. Uses latest log if no log_file specified."""
    try:
        data_dir = str(_project_root / "data")

        # load specific log or the most recent one
        if log_file:
            filepath = str(_project_root / "data" / log_file)
            data = load_log(filepath)
            source_file = log_file
        else:
            data = load_latest_log(data_dir)
            data_path = Path(data_dir)
            json_files = sorted(data_path.glob("*.json"))
            source_file = json_files[-1].name if json_files else "unknown"

        logs = data["logs"]
        summary = data["summary"]
        sim_duration: int = summary.get("sim_duration_seconds", 14400)

        # run all 5 analyzers (same order as main_phase2.py)
        tp_report = throughput_analyzer.analyze(logs, summary, sim_duration)
        q_report = queue_analyzer.analyze(logs, sim_duration)
        u_report = utilization_analyzer.analyze(logs, summary, sim_duration)
        d_report = downtime_analyzer.analyze(logs, summary, sim_duration)
        c_report = cost_estimator.analyze(u_report, d_report, logs, summary, sim_duration)

        # package into report
        report = WarehouseAnalysisReport(
            source_file=source_file,
            analysis_timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            sim_duration_seconds=sim_duration,
            throughput=tp_report, queue=q_report,
            utilization=u_report, downtime=d_report, cost=c_report,
        )

        # save to outputs/
        outputs_dir = _project_root / "outputs"
        outputs_dir.mkdir(exist_ok=True)
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = outputs_dir / f"analysis_report_{ts_str}.json"
        report_dict = report.model_dump()
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2, default=str)

        logger.info("Analysis complete — saved to %s", json_path)
        return report_dict

    except Exception as e:
        logger.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=str(e))
