# =============================================================================
# MAIN PHASE 2 — ENTRY POINT
# Run this with: python main_phase2.py
# It loads the latest simulation log from data/, runs all 5 analyzers
# (throughput, queue, utilization, downtime, cost), saves results
# as JSON and text in outputs/, and prints a summary to console.
#
# Phase 1 must have been run first so there's a log file in data/.
# No API keys needed. Just numpy.
#
# The pipeline:
#   1. Load latest JSON log from data/
#   2. Run 5 analyzers (each produces a report dataclass)
#   3. Combine all 5 into one WarehouseAnalysisReport
#   4. Save as JSON (for Phase 3 agents to read) and text (for humans)
#   5. Print summary to console
# =============================================================================

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# make sure imports work from project root
# this resolves the directory where this file lives and adds it to Python's import path
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# import all 5 analyzers
from analysis import throughput_analyzer, queue_analyzer, utilization_analyzer
from analysis import downtime_analyzer, cost_estimator
# the top-level report container that holds all 5 sub-reports
from schemas.analysis_schema import WarehouseAnalysisReport
# loads JSON log files from data/
from tools.log_loader import load_latest_log

# set up logging so we can see progress in the console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main_phase2")

def main() -> None:
    print()
    print("=" * 60)
    print("  PHASE 2 — Deterministic Analysis Layer")
    print("=" * 60)
    print()

    #step 1: load the most recent simulation log
    # Phase 1 saves logs as warehouse_logs_YYYYMMDD_HHMMSS.json in data/
    # load_latest_log finds the newest one by sorting filenames alphabetically
    data_dir = str(_project_root / "data")
    data = load_latest_log(data_dir)
    logs = data["logs"]         # list of ~7000 event dicts
    summary = data["summary"]   # aggregate stats from Phase 1
    sim_duration: int = summary.get("sim_duration_seconds", 14400)  # default 4 hours

    # figure out which file we loaded so we can store it in the report metadata
    data_path = Path(data_dir)
    json_files = sorted(data_path.glob("*.json"))
    source_file = json_files[-1].name if json_files else "unknown"
    logger.info("Loaded %d events from %s", len(logs), source_file)

    #step 2: run all 5 analyzers in order 
    # each analyzer takes the raw logs and/or summary and returns a report dataclass
    # the order matters for cost_estimator — it needs utilization and downtime results
    tp_report = throughput_analyzer.analyze(logs, summary, sim_duration)   # tasks/hour, trends
    q_report = queue_analyzer.analyze(logs, sim_duration)  # queue growth, congestion
    u_report = utilization_analyzer.analyze(logs, summary, sim_duration)   # robot idle/active ratios
    d_report = downtime_analyzer.analyze(logs, summary, sim_duration)      # MTBF, failure clusters
    c_report = cost_estimator.analyze(u_report, d_report, logs, summary, sim_duration)  # $ cost of waste

    # step 3: package all 5 reports into one container
    analysis_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = WarehouseAnalysisReport(
        source_file=source_file,
        analysis_timestamp=analysis_ts,
        sim_duration_seconds=sim_duration,
        throughput=tp_report,
        queue=q_report,
        utilization=u_report,
        downtime=d_report,
        cost=c_report,
    )

    #step 4: save outputs
    outputs_dir = _project_root / "outputs"
    outputs_dir.mkdir(exist_ok=True)  # create outputs/ if it doesn't exist
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = outputs_dir / f"analysis_report_{ts_str}.json"
    txt_path = outputs_dir / f"analysis_summary_{ts_str}.txt"

    # save JSON report this is the main output
    # Phase 3 agents will load this file and interpret the numbers
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, indent=2, default=str)
    logger.info("JSON report saved to %s", json_path)

    # save human-readable text summary
    text = _build_text_summary(tp_report, q_report, u_report, d_report, c_report, sim_duration, source_file)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)
    logger.info("Text summary saved to %s", txt_path)

    # step 5: print to console
    print(text)

def _build_text_summary(tp, q, u, d, c, sim_duration, source_file) -> str:
    """Build the formatted text summary that gets printed and saved.
    Takes all 5 report objects and formats their key metrics into a readable string."""
    hours = sim_duration / 3600  # convert seconds to hours for display
    # join hourly task counts into a string like "801, 830, 825, 837"
    hourly_str = ", ".join(str(h) for h in tp.tasks_per_hour)

    # queue section
    # show which zones are congested, or "None detected" if all clear
    congested_str = ", ".join(q.congested_zones) if q.congested_zones else "None detected"
    highest_avg_zone = q.highest_avg_queue_zone
    highest_avg_val = q.average_queue_length_per_zone.get(highest_avg_zone, 0)
    highest_peak_zone = q.highest_peak_queue_zone
    highest_peak_val = q.peak_queue_length_per_zone.get(highest_peak_zone, 0)

    #utilization section
    # format underutilized/overworked robot lists, or show "None" if empty
    underutil_strs = [f"Robot {rid}: {idle:.1f}% idle" for rid, idle in u.underutilized_robots] or ["None"]
    overwork_strs = [f"Robot {rid}: {util:.1f}% active" for rid, util in u.overworked_robots] or ["None"]

    #downtime section
    # get details for the best and worst robots by reliability
    least_id = d.least_reliable_robot
    most_id = d.most_reliable_robot
    least_info = d.robot_downtimes.get(least_id, {})   # dict with score, mtbf, etc.
    most_info = d.robot_downtimes.get(most_id, {})

    #cost section
    cb = c.cost_breakdown  # dict with idle/delay/failure/queue -> {amount, percentage}

    # build the output line by line
    lines = [
        "=" * 60,
        "WAREHOUSE OPERATIONS ANALYSIS",
        "=" * 60,
        f"Period: 0.0s to {sim_duration}s ({hours:.1f} hours)",
        f"Source: {source_file}",
        "",
        "--- THROUGHPUT ---",
        f"Total tasks completed: {tp.total_tasks_completed}",
        f"Average throughput: {tp.average_throughput_per_hour} tasks/hour",
        f"Throughput trend: {tp.throughput_trend} (slope: {tp.throughput_trend_slope})",
        f"Highest performing zone: {tp.highest_performing_zone} ({tp.highest_zone_throughput_per_hour} tasks/hour)",
        f"Lowest performing zone: {tp.lowest_performing_zone} ({tp.lowest_zone_throughput_per_hour} tasks/hour)",
        f"Hourly breakdown: [{hourly_str}]",
        "",
        "--- QUEUE HEALTH ---",
        f"Zones with growing congestion: {congested_str}",
        f"Highest average queue: Zone {highest_avg_zone} ({highest_avg_val} items)",
        f"Peak queue length: Zone {highest_peak_zone} ({highest_peak_val} items)",
        f"Congestion events detected: {q.congestion_events}",
        "",
        "--- ROBOT UTILIZATION ---",
        f"Fleet average utilization: {u.fleet_average_utilization}%",
        f"Underutilized robots (>40% idle): {', '.join(underutil_strs)}",
        f"Overworked robots (>85% active): {', '.join(overwork_strs)}",
        "",
        "--- DOWNTIME & RELIABILITY ---",
        f"Total failures: {d.total_failures}",
        f"Fleet failure rate: {d.fleet_failure_rate} failures/robot-hour",
        f"Failure clusters detected: {d.failure_clusters}",
        f"Least reliable robot: Robot {least_id} (score: {least_info.get('reliability_score', 0)}, MTBF: {least_info.get('mtbf_minutes', 0)} min)",
        f"Most reliable robot: Robot {most_id} (score: {most_info.get('reliability_score', 0)}, MTBF: {most_info.get('mtbf_minutes', 0)} min)",
        "",
        "--- COST IMPACT ---",
        f"Total estimated inefficiency cost: ${c.total_inefficiency_cost:,.2f}",
        f"  Idle cost:    ${cb['idle']['amount']:,.2f} ({cb['idle']['percentage']}%)",
        f"  Delay cost:   ${cb['delay']['amount']:,.2f} ({cb['delay']['percentage']}%)",
        f"  Failure cost: ${cb['failure']['amount']:,.2f} ({cb['failure']['percentage']}%)",
        f"  Queue cost:   ${cb['queue']['amount']:,.2f} ({cb['queue']['percentage']}%)",
        "=" * 60,
    ]
    return "\n".join(lines) + "\n"

if __name__ == "__main__":
    main()