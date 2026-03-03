# =============================================================================
# UTILIZATION ANALYZER
# Estimates how each robot spent its time during the simulation:
# - Active (picking tasks)
# - Failed (broken down)
# - Charging (at charging station)
# - Idle (doing nothing)
#
# We don't have exact state timestamps in the logs, so we estimate:
#   active_time  = num_tasks * 18 seconds (average pick duration)
#   failed_time  = sum of downtime_seconds from failure events
#   charging_time = num_charges * 90 seconds (midpoint of 60-120 range)
#   idle_time    = sim_duration - active - failed - charging
#
# Robots with >40% idle time are flagged as underutilized.
# Robots with >85% utilization are flagged as overworked.
# =============================================================================

import logging
from typing import Any, Dict, List, Tuple
import numpy as np
from schemas.analysis_schema import UtilizationReport
from tools.log_loader import get_all_robot_ids, get_events_by_robot

logger = logging.getLogger(__name__)
MEAN_TASK_DURATION = 18.0  # average pick time from config
MEAN_CHARGE_TIME = 90.0    # midpoint of charge_time_range (60, 120)

def analyze(logs: List[Dict[str, Any]], summary: Dict[str, Any], sim_duration: int) -> UtilizationReport:
    """Compute per-robot utilization metrics."""
    logger.info("Running utilization analysis …")
    robot_ids = get_all_robot_ids(logs)
    robot_metrics: Dict[int, Dict[str, Any]] = {}
    underutilized: List[Tuple[int, float]] = []
    overworked: List[Tuple[int, float]] = []
    utilization_rates: List[float] = []

    for rid in robot_ids:
        robot_events = get_events_by_robot(logs, rid)
        # count how many tasks this robot completed
        num_tasks = len([e for e in robot_events if e.get("event_type") == "task_completed"])
        # collect total downtime from failure events
        failed_events = [e for e in robot_events if e.get("event_type") == "robot_failed"]
        failed_time = sum(float(e.get("downtime_seconds", 0)) for e in failed_events)
        # count how many times this robot charged
        num_charges = len([e for e in robot_events if e.get("event_type") == "robot_charging"])
        # estimate time breakdown
        active_time = num_tasks * MEAN_TASK_DURATION         # e.g. 330 tasks * 18s = 5940s
        charging_time = num_charges * MEAN_CHARGE_TIME       # e.g. 2 charges * 90s = 180s
        idle_time = max(0.0, sim_duration - active_time - failed_time - charging_time)
        # convert to percentages
        utilization_rate = round(active_time / max(1, sim_duration) * 100, 2)
        idle_rate = round(idle_time / max(1, sim_duration) * 100, 2)
        failed_rate = round(failed_time / max(1, sim_duration) * 100, 2)

        metrics = {
            "active_time": round(active_time, 2),
            "failed_time": round(failed_time, 2),
            "charging_time": round(charging_time, 2),
            "idle_time": round(idle_time, 2),
            "utilization_rate": utilization_rate,
            "idle_rate": idle_rate,
            "failed_rate": failed_rate,
            "num_tasks": num_tasks,
        }
        robot_metrics[rid] = metrics
        utilization_rates.append(utilization_rate)
        # flag robots that are too idle or too busy
        if idle_rate > 40.0:
            underutilized.append((rid, idle_rate))
        if utilization_rate > 85.0:
            overworked.append((rid, utilization_rate))

    fleet_avg = round(float(np.mean(utilization_rates)) if utilization_rates else 0.0, 2)

    report = UtilizationReport(
        robot_metrics=robot_metrics,
        underutilized_robots=underutilized,
        overworked_robots=overworked,
        fleet_average_utilization=fleet_avg,
    )
    logger.info("Utilization analysis complete — fleet avg: %.1f%%", fleet_avg)
    return report