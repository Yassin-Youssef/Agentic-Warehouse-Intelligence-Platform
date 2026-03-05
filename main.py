# =============================================================================
# UNIFIED CLI ENTRY POINT
# =============================================================================
# The single entry point for the entire platform.
# Run with: python main.py --mode [simulate|analyze|agents|api|full]
#
# Modes:
#   simulate — Phase 1 only (generate warehouse logs)
#   analyze  — Phase 1 + Phase 2 (simulate then analyze)
#   agents   — Phase 1 + Phase 2 + Phase 3 (full pipeline)
#   api      — Start FastAPI server on port 8000
#   full     — Same as agents (default if no mode specified)
#
# Each mode builds on the previous:
#   simulate: creates data/warehouse_logs_*.json
#   analyze:  also creates outputs/analysis_report_*.json
#   agents:   also creates outputs/intelligence_report_*.json
#   api:      exposes everything through HTTP endpoints
# =============================================================================

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")

def run_phase1() -> tuple:
    """Run Phase 1 simulation. Returns (log_filename, summary_dict)."""
    from config.warehouse_config import WarehouseConfig
    from simulation.warehouse import WarehouseSimulator

    print()
    print("=" * 64)
    print("  PHASE 1 — Warehouse Simulation Engine")
    print("=" * 64)
    print()

    config = WarehouseConfig()
    sim = WarehouseSimulator(config)
    logs = sim.run()
    summary = sim.get_summary()

    # save to data/
    data_dir = _project_root / "data"
    data_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"warehouse_logs_{ts}.json"

    output = {
        "logs": [entry.model_dump() for entry in logs],
        "summary": summary.model_dump(),
    }
    with open(data_dir / filename, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    logger.info("Logs saved → %s", data_dir / filename)
    return filename, summary.model_dump()

def run_phase2() -> Dict[str, Any]:
    """Run Phase 2 analysis on latest log. Returns report dict."""
    from analysis import (throughput_analyzer, queue_analyzer,
                          utilization_analyzer, downtime_analyzer, cost_estimator)
    from schemas.analysis_schema import WarehouseAnalysisReport
    from tools.log_loader import load_latest_log

    print()
    print("=" * 64)
    print("  PHASE 2 — Deterministic Analysis Layer")
    print("=" * 64)
    print()

    data_dir = str(_project_root / "data")
    data = load_latest_log(data_dir)
    logs = data["logs"]
    summary = data["summary"]
    sim_duration: int = summary.get("sim_duration_seconds", 14400)

    # find which file we loaded
    data_path = Path(data_dir)
    json_files = sorted(data_path.glob("*.json"))
    source_file = json_files[-1].name if json_files else "unknown"

    # run all 5 analyzers
    tp = throughput_analyzer.analyze(logs, summary, sim_duration)
    q = queue_analyzer.analyze(logs, sim_duration)
    u = utilization_analyzer.analyze(logs, summary, sim_duration)
    d = downtime_analyzer.analyze(logs, summary, sim_duration)
    c = cost_estimator.analyze(u, d, logs, summary, sim_duration)

    report = WarehouseAnalysisReport(
        source_file=source_file,
        analysis_timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        sim_duration_seconds=sim_duration,
        throughput=tp, queue=q, utilization=u, downtime=d, cost=c,
    )
    report_dict = report.model_dump()

    # save to outputs/
    outputs_dir = _project_root / "outputs"
    outputs_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = outputs_dir / f"analysis_report_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2, default=str)

    logger.info("Analysis saved → %s", json_path)
    return report_dict

def run_phase3() -> List[Dict[str, Any]]:
    """Run Phase 3 agents on latest analysis. Returns list of agent dicts."""
    from agents.performance_summary_agent import PerformanceSummaryAgent
    from agents.bottleneck_diagnosis_agent import BottleneckDiagnosisAgent
    from agents.resource_allocation_agent import ResourceAllocationAgent
    from agents.risk_forecast_agent import RiskForecastAgent
    from agents.optimization_strategy_agent import OptimizationStrategyAgent

    print()
    print("=" * 64)
    print("  PHASE 3 — Agentic Reasoning Layer")
    print("=" * 64)
    print()

    # load latest analysis report
    outputs_dir = _project_root / "outputs"
    files = sorted(outputs_dir.glob("analysis_report_*.json"))
    if not files:
        raise FileNotFoundError("No analysis reports found in outputs/")
    latest = files[-1]
    with open(latest, "r", encoding="utf-8") as f:
        report = json.load(f)

    # run all 5 agents
    agents = [
        PerformanceSummaryAgent(),
        BottleneckDiagnosisAgent(),
        ResourceAllocationAgent(),
        RiskForecastAgent(),
        OptimizationStrategyAgent(),
    ]

    results = []
    for agent in agents:
        print(f"  Running {agent.name}...")
        output = agent.run(report)
        results.append(output.model_dump())
        print(f"  Done.")
        print()

    # save intelligence report
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    intel_path = outputs_dir / f"intelligence_report_{ts}.json"
    with open(intel_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "analysis_source": latest.name,
            "agent_reports": results,
        }, f, indent=2, default=str)

    logger.info("Intelligence report saved → %s", intel_path)
    return results

# --- mode dispatch ---

def mode_simulate():
    run_phase1()

def mode_analyze():
    run_phase1()
    run_phase2()

def mode_agents():
    run_phase1()
    run_phase2()
    run_phase3()

def mode_full():
    run_phase1()
    run_phase2()
    run_phase3()
    print()
    print("=" * 64)
    print("  FULL PIPELINE COMPLETE")
    print("=" * 64)

def mode_api():
    import uvicorn
    print()
    print("=" * 64)
    print("  API MODE — Starting FastAPI server on port 8000")
    print("=" * 64)
    print()
    uvicorn.run("api.app:app", host="0.0.0.0", port=8000, reload=False)

def main():
    parser = argparse.ArgumentParser(description="Agentic Warehouse Intelligence Platform")
    parser.add_argument("--mode", choices=["simulate", "analyze", "agents", "api", "full"],
                        default="full", help="Run mode (default: full)")
    args = parser.parse_args()

    dispatch = {
        "simulate": mode_simulate,
        "analyze": mode_analyze,
        "agents": mode_agents,
        "api": mode_api,
        "full": mode_full,
    }

    print()
    print("=" * 64)
    print(f"  Agentic Warehouse Intelligence Platform — {args.mode.upper()}")
    print("=" * 64)

    dispatch[args.mode]()

if __name__ == "__main__":
    main()
