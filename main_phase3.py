# =============================================================================
# MAIN PHASE 3 — ENTRY POINT
# Run this with: python main_phase3.py
#
# What it does:
#   1. Loads the latest Phase 2 analysis report from outputs/
#   2. Creates all 5 agents
#   3. Runs each agent (each makes one LLM call to Claude via OpenRouter)
#   4. Saves the intelligence report as JSON and text in outputs/
#   5. Prints everything to console
#
# REQUIRES:
#   - OpenRouter API key in .env file (OPENROUTER_API_KEY=sk-or-...)
#   - Phase 2 must have been run first (analysis report in outputs/)
#   - pip install python-dotenv requests
#
# Each agent call takes ~5-10 seconds (waiting for Claude's response),
# so the full run takes about 30-50 seconds for all 5 agents.
# =============================================================================

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# make sure imports work from project root
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# import all 5 agents — each one is a subclass of BaseAgent
from agents.performance_summary_agent import PerformanceSummaryAgent
from agents.bottleneck_diagnosis_agent import BottleneckDiagnosisAgent
from agents.resource_allocation_agent import ResourceAllocationAgent
from agents.risk_forecast_agent import RiskForecastAgent
from agents.optimization_strategy_agent import OptimizationStrategyAgent

# set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main_phase3")

def _load_latest_analysis() -> tuple:
    """Find the most recent analysis_report_*.json in outputs/ and load it.
    These files are named with timestamps so sorting alphabetically = chronological."""
    outputs_dir = _project_root / "outputs"
    report_files = sorted(outputs_dir.glob("analysis_report_*.json"))
    if not report_files:
        raise FileNotFoundError("No analysis reports found in outputs/. Run Phase 2 first.")
    latest = report_files[-1]  # last file = most recent
    logger.info("Loading analysis report: %s", latest.name)
    with open(latest, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data, latest.name

def main() -> None:
    print()
    print("=" * 60)
    print("  PHASE 3 — Agentic Reasoning Layer")
    print("=" * 60)
    print()

    # step 1: load the latest Phase 2 analysis report
    report, source_file = _load_latest_analysis()
    logger.info("Loaded report from %s", source_file)

    # step 2: create all 5 agents
    # they run in this order: summary first (overview), then specific analyses
    agents = [
        PerformanceSummaryAgent(),        # overall health briefing
        BottleneckDiagnosisAgent(),       # explains congestion causes
        ResourceAllocationAgent(),        # suggests robot moves
        RiskForecastAgent(),              # predicts future problems
        OptimizationStrategyAgent(),      # proposes ranked strategies
    ]

    # step 3: run each agent one by one
    # each agent.run() calls the LLM once and returns an AgentOutput
    agent_outputs = []
    for agent in agents:
        print(f"  Running {agent.name}...")
        output = agent.run(report)         # builds prompt -> calls LLM -> parses response
        agent_outputs.append(output)
        print(f"  Done.")
        print()

    # step 4: package all 5 outputs into one intelligence report
    intelligence_report = {
        "generated_at": datetime.now().isoformat(),
        "analysis_source": source_file,
        "agent_reports": [out.model_dump() for out in agent_outputs],
    }

    # step 5: save outputs
    outputs_dir = _project_root / "outputs"
    outputs_dir.mkdir(exist_ok=True)
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = outputs_dir / f"intelligence_report_{ts_str}.json"
    txt_path = outputs_dir / f"intelligence_summary_{ts_str}.txt"

    # save JSON — this is the structured output
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(intelligence_report, f, indent=2, default=str)
    logger.info("JSON report saved to %s", json_path)

    # save human-readable text
    text = _build_text_report(agent_outputs, source_file)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)
    logger.info("Text summary saved to %s", txt_path)

    # step 6: print to console
    print(text)

def _build_text_report(agent_outputs: list, source_file: str) -> str:
    """Format all 5 agent outputs into one readable text report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # build the report header
    sections = [
        "=" * 60,
        "WAREHOUSE INTELLIGENCE REPORT",
        "=" * 60,
        f"Generated: {timestamp}",
        f"Analysis Source: {source_file}",
    ]
    # add each agent's output as its own section
    for output in agent_outputs:
        sections.append("")
        sections.append(f"--- {output.agent_name.upper()} ---")
        sections.append(output.summary)
    sections.append("")
    sections.append("=" * 60)
    return "\n".join(sections) + "\n"

if __name__ == "__main__":
    main()