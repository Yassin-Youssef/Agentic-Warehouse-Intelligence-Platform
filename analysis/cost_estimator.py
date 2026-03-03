# =============================================================================
# COST ESTIMATOR
# Puts a dollar value on every type of inefficiency:
# - Idle cost: robots sitting around doing nothing ($15/hour per robot)
# - Delay cost: conveyor delays adding time to tasks ($2.50 per delayed task)
# - Failure cost: robot breakdowns ($50 per failure event)
# - Queue cost: tasks waiting in line ($0.75 per item-minute)
#
# This makes the analysis business-relevant. Instead of saying
# "robots are idle", we say "idle robots cost $1,200 over 4 hours."
#
# The cost parameters are defaults that can be overridden. In a real
# system you'd tune these to actual operational costs.
# =============================================================================

import logging
from typing import Any, Dict, List
from schemas.analysis_schema import CostReport, UtilizationReport, DowntimeReport

logger = logging.getLogger(__name__)

def analyze(
    utilization_report: UtilizationReport,
    downtime_report: DowntimeReport,
    logs: List[Dict[str, Any]],
    summary: Dict[str, Any],
    sim_duration: int,
    cost_per_idle_robot_hour: float = 15.0,   # $ per hour a robot sits idle
    cost_per_delayed_task: float = 2.50,  # $ per task that got a conveyor delay
    cost_per_failure_event: float = 50.0, # $ per robot breakdown
    cost_per_queued_minute: float = 0.75,  # $ per item sitting in queue per minute
) -> CostReport:
    """Estimate total cost of operational inefficiencies."""
    logger.info("Running cost estimation …")

    # idle cost: for each robot, (idle_time / 3600) * rate, summed across fleet
    idle_cost = 0.0
    for rid, metrics in utilization_report.robot_metrics.items():
        idle_hours = metrics.get("idle_time", 0.0) / 3600.0  # convert seconds to hours
        idle_cost += idle_hours * cost_per_idle_robot_hour
    idle_cost = round(idle_cost, 2)

    # delay cost: number of conveyor delays * cost per delay
    delay_cost = round(summary.get("total_conveyor_delays", 0) * cost_per_delayed_task, 2)

    # failure cost: number of failures * cost per failure
    failure_cost = round(summary.get("total_robot_failures", 0) * cost_per_failure_event, 2)

    # queue cost: for each zone, avg_queue_length * (sim_minutes) * rate
    # this estimates the total "item-minutes" spent waiting across all zones
    avg_queue = summary.get("average_queue_length_per_zone", {})
    queue_cost = 0.0
    for zone, avg_len in avg_queue.items():
        queue_cost += avg_len * (sim_duration / 60.0) * cost_per_queued_minute
    queue_cost = round(queue_cost, 2)

    # total everything up
    total = round(idle_cost + delay_cost + failure_cost + queue_cost, 2)

    # calculate what percentage each category contributes
    def _pct(part: float) -> float:
        return round(part / max(0.01, total) * 100, 2)  # max(0.01) avoids division by zero

    breakdown = {
        "idle": {"amount": idle_cost, "percentage": _pct(idle_cost)},
        "delay": {"amount": delay_cost, "percentage": _pct(delay_cost)},
        "failure": {"amount": failure_cost, "percentage": _pct(failure_cost)},
        "queue": {"amount": queue_cost, "percentage": _pct(queue_cost)},
    }

    report = CostReport(
        idle_cost=idle_cost,
        delay_cost=delay_cost,
        failure_cost=failure_cost,
        queue_cost=queue_cost,
        total_inefficiency_cost=total,
        cost_breakdown=breakdown,
    )
    logger.info("Cost estimation complete — total: $%.2f", total)
    return report