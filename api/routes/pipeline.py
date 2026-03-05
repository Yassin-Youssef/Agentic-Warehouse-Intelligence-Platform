# =============================================================================
# POST /warehouse/full-pipeline
# =============================================================================
# The "one-click" endpoint — runs the entire system end to end:
#   Phase 1 (simulate) -> Phase 2 (analyze) -> Phase 3 (agents)
#
# Returns everything in one response:
#   {simulation_summary, analysis_report, intelligence_report}
#
# Takes ~60-90 seconds:
#   Phase 1: ~5s (simulation)
#   Phase 2: <1s (math)
#   Phase 3: ~30-50s (5 LLM calls to OpenRouter)
#
# Saves all outputs to data/ and outputs/ along the way.
# =============================================================================

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from config.warehouse_config import WarehouseConfig
from simulation.warehouse import WarehouseSimulator
from analysis import (
    throughput_analyzer, queue_analyzer,
    utilization_analyzer, downtime_analyzer, cost_estimator,
)
from schemas.analysis_schema import WarehouseAnalysisReport
from agents.performance_summary_agent import PerformanceSummaryAgent
from agents.bottleneck_diagnosis_agent import BottleneckDiagnosisAgent
from agents.resource_allocation_agent import ResourceAllocationAgent
from agents.risk_forecast_agent import RiskForecastAgent
from agents.optimization_strategy_agent import OptimizationStrategyAgent

logger = logging.getLogger("api.pipeline")
router = APIRouter(prefix="/warehouse", tags=["pipeline"])

@router.post("/full-pipeline")
async def run_full_pipeline() -> Dict[str, Any]:
    """Run the complete pipeline: Simulate -> Analyze -> Reason."""
    try:
        # --- Phase 1: Simulation ---
        logger.info("Pipeline — starting Phase 1 (Simulation)")
        config = WarehouseConfig()
        sim = WarehouseSimulator(config)
        logs = sim.run()
        summary = sim.get_summary()

        # save simulation logs to data/
        data_dir = _project_root / "data"
        data_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"warehouse_logs_{ts}.json"

        sim_output = {
            "logs": [entry.model_dump() for entry in logs],
            "summary": summary.model_dump(),
        }
        with open(data_dir / log_filename, "w", encoding="utf-8") as f:
            json.dump(sim_output, f, indent=2, default=str)

        # --- Phase 2: Analysis ---
        logger.info("Pipeline — starting Phase 2 (Analysis)")
        raw_logs = sim_output["logs"]
        raw_summary = sim_output["summary"]
        sim_duration: int = raw_summary.get("sim_duration_seconds", 14400)

        tp = throughput_analyzer.analyze(raw_logs, raw_summary, sim_duration)
        q = queue_analyzer.analyze(raw_logs, sim_duration)
        u = utilization_analyzer.analyze(raw_logs, raw_summary, sim_duration)
        d = downtime_analyzer.analyze(raw_logs, raw_summary, sim_duration)
        c = cost_estimator.analyze(u, d, raw_logs, raw_summary, sim_duration)

        report = WarehouseAnalysisReport(
            source_file=log_filename,
            analysis_timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            sim_duration_seconds=sim_duration,
            throughput=tp, queue=q, utilization=u, downtime=d, cost=c,
        )
        report_dict = report.model_dump()

        # save analysis report to outputs/
        outputs_dir = _project_root / "outputs"
        outputs_dir.mkdir(exist_ok=True)
        with open(outputs_dir / f"analysis_report_{ts}.json", "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2, default=str)

        # --- Phase 3: Agents ---
        logger.info("Pipeline — starting Phase 3 (Agents)")
        agents = [
            PerformanceSummaryAgent(),
            BottleneckDiagnosisAgent(),
            ResourceAllocationAgent(),
            RiskForecastAgent(),
            OptimizationStrategyAgent(),
        ]

        agent_reports: List[Dict[str, Any]] = []
        for agent in agents:
            output = agent.run(report_dict)
            agent_reports.append(output.model_dump())

        # save intelligence report to outputs/
        intel_report = {
            "generated_at": datetime.now().isoformat(),
            "analysis_source": log_filename,
            "agent_reports": agent_reports,
        }
        with open(outputs_dir / f"intelligence_report_{ts}.json", "w", encoding="utf-8") as f:
            json.dump(intel_report, f, indent=2, default=str)

        # return everything
        return {
            "simulation_summary": summary.model_dump(),
            "analysis_report": report_dict,
            "intelligence_report": {"agent_reports": agent_reports},
        }

    except Exception as e:
        logger.exception("Full pipeline failed")
        raise HTTPException(status_code=500, detail=str(e))
