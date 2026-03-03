# =============================================================================
# THROUGHPUT ANALYZER
# Counts how many tasks got completed per hour, per zone, and detects
# whether throughput is trending up, down, or stable.
#
# The trend is detected using linear regression (numpy polyfit).
# We fit a straight line through the 4 hourly counts. The slope of
# that line tells us the direction:
#   slope > 5   = throughput is increasing
#   slope < -5  = throughput is decreasing
#   otherwise   = stable
#
# This is pure math — no AI. Phase 3 agents will interpret these
# numbers and explain what they mean.
# =============================================================================

import logging
from typing import Any, Dict, List
import numpy as np
from schemas.analysis_schema import ThroughputReport
from tools.log_loader import get_events_by_type, get_events_in_timerange

logger = logging.getLogger(__name__)
BUCKET_SECONDS = 3600  # 1 hour = 3600 seconds

def analyze(logs: List[Dict[str, Any]], summary: Dict[str, Any], sim_duration: int) -> ThroughputReport:
    """Analyze throughput from simulation logs."""
    logger.info("Running throughput analysis …")
    num_hours = max(1, sim_duration // BUCKET_SECONDS)  # 14400 // 3600 = 4 hours
    completed_events = get_events_by_type(logs, "task_completed")  # only task_completed events

    # count completions per hour bucket: [0-3600), [3600-7200), [7200-10800), [10800-14400)
    tasks_per_hour: List[int] = []
    for i in range(num_hours):
        start = i * BUCKET_SECONDS       # e.g. 0, 3600, 7200, 10800
        end = (i + 1) * BUCKET_SECONDS   # e.g. 3600, 7200, 10800, 14400
        bucket = get_events_in_timerange(completed_events, start, end)
        tasks_per_hour.append(len(bucket))
    average_throughput = round(float(np.mean(tasks_per_hour)) if tasks_per_hour else 0.0, 2)

    # linear regression on hourly counts to detect trend
    # x = [0, 1, 2, 3], y = tasks_per_hour
    # polyfit returns [slope, intercept], we only care about slope
    x = np.arange(len(tasks_per_hour), dtype=float)
    if len(tasks_per_hour) >= 2:
        slope = float(np.polyfit(x, tasks_per_hour, 1)[0])  # [0] = slope
    else:
        slope = 0.0
    slope = round(slope, 2)
    # classify the trend based on slope magnitude
    if slope > 5.0:
        trend = "increasing"
    elif slope < -5.0:
        trend = "decreasing"
    else:
        trend = "stable"

    # per-zone completions (from summary) and hourly breakdown per zone
    completions_per_zone: Dict[str, int] = summary.get("completions_per_zone", {})
    tasks_per_zone_per_hour: Dict[str, List[int]] = {}
    for zone in completions_per_zone:
        zone_completed = [e for e in completed_events if e.get("zone") == zone]
        hourly: List[int] = []
        for i in range(num_hours):
            start = i * BUCKET_SECONDS
            end = (i + 1) * BUCKET_SECONDS
            hourly.append(len([e for e in zone_completed if start <= e.get("timestamp", -1) < end]))
        tasks_per_zone_per_hour[zone] = hourly

    # find best and worst performing zones
    if completions_per_zone:
        highest_zone = max(completions_per_zone, key=completions_per_zone.get)
        lowest_zone = min(completions_per_zone, key=completions_per_zone.get)
    else:
        highest_zone = ""
        lowest_zone = ""
    highest_tph = round(completions_per_zone.get(highest_zone, 0) / max(1, num_hours), 2)
    lowest_tph = round(completions_per_zone.get(lowest_zone, 0) / max(1, num_hours), 2)

    report = ThroughputReport(
        total_tasks_completed=summary.get("total_tasks_completed", 0),
        tasks_per_hour=tasks_per_hour,
        average_throughput_per_hour=average_throughput,
        tasks_per_zone=dict(completions_per_zone),
        tasks_per_zone_per_hour=tasks_per_zone_per_hour,
        throughput_trend_slope=slope,
        throughput_trend=trend,
        highest_performing_zone=highest_zone,
        lowest_performing_zone=lowest_zone,
        highest_zone_throughput_per_hour=highest_tph,
        lowest_zone_throughput_per_hour=lowest_tph,
    )
    logger.info("Throughput analysis complete — trend: %s (slope=%.2f)", trend, slope)
    return report