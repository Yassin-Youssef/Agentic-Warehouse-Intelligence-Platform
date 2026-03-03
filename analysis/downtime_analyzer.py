# =============================================================================
# DOWNTIME ANALYZER
# Calculates reliability metrics for each robot:
# - Failure count and total downtime
# - MTBF (Mean Time Between Failures) — standard reliability metric
#   MTBF = (sim_duration - downtime) / failures. Lower = less reliable.
# - Reliability score: 100 = perfect, 0 = always broken
# - Failure clustering: 3+ failures within 30 min = a cluster
#   Clusters suggest systemic problems, not random bad luck.
#
# This is where we detect that robots 8, 9, 10 are significantly
# less reliable than the rest of the fleet.
# =============================================================================

import logging
from typing import Any, Dict, List
from schemas.analysis_schema import DowntimeReport
from tools.log_loader import get_all_robot_ids, get_events_by_robot

logger = logging.getLogger(__name__)
CLUSTER_WINDOW_SECONDS = 1800.0  # 30 minutes
CLUSTER_MIN_FAILURES = 3         # need at least 3 failures to form a cluster

def analyze(logs: List[Dict[str, Any]], summary: Dict[str, Any], sim_duration: int) -> DowntimeReport:
    """Compute downtime and reliability metrics for all robots."""
    logger.info("Running downtime analysis …")
    robot_ids = get_all_robot_ids(logs)
    robot_downtimes: Dict[int, Dict[str, Any]] = {}
    reliability_scores: Dict[int, float] = {}

    for rid in robot_ids:
        robot_events = get_events_by_robot(logs, rid)
        failed_events = [e for e in robot_events if e.get("event_type") == "robot_failed"]
        failure_count = len(failed_events)
        total_downtime = sum(float(e.get("downtime_seconds", 0)) for e in failed_events)
        # MTBF: how many seconds of operation between each failure on average
        # (sim_duration - downtime) = total operational time
        # divide by number of failures to get average time between failures
        mtbf_seconds = (sim_duration - total_downtime) / max(1, failure_count)
        mtbf_minutes = round(mtbf_seconds / 60.0, 2)
        # downtime as percentage of total sim time
        downtime_pct = round(total_downtime / max(1, sim_duration) * 100, 2)
        # reliability score: starts at 100, loses 2 points per percent of downtime
        # clamped between 0 and 100
        score = round(max(0.0, min(100.0, 100.0 - downtime_pct * 2)), 2)

        robot_downtimes[rid] = {
            "failure_count": failure_count,
            "total_downtime": round(total_downtime, 2),
            "mtbf_minutes": mtbf_minutes,
            "downtime_percentage": downtime_pct,
            "reliability_score": score,
        }
        reliability_scores[rid] = score

    # fleet-level stats
    total_failures = summary.get("total_robot_failures", 0)
    num_robots = len(robot_ids) if robot_ids else 1
    # failures per robot-hour: total failures / (num_robots * hours)
    fleet_failure_rate = round(total_failures / max(1, num_robots * sim_duration / 3600), 2)

    # find least and most reliable robots
    if reliability_scores:
        least_reliable = min(reliability_scores, key=reliability_scores.get)
        most_reliable = max(reliability_scores, key=reliability_scores.get)
    else:
        least_reliable = 0
        most_reliable = 0

    # count failure clusters across the fleet
    clusters = _count_failure_clusters(logs)

    report = DowntimeReport(
        robot_downtimes=robot_downtimes,
        total_failures=total_failures,
        fleet_failure_rate=fleet_failure_rate,
        least_reliable_robot=least_reliable,
        most_reliable_robot=most_reliable,
        failure_clusters=clusters,
    )
    logger.info("Downtime analysis complete — %d clusters detected", clusters)
    return report

def _count_failure_clusters(logs: List[Dict[str, Any]]) -> int:
    """Count distinct failure clusters. A cluster = 3+ failures within 30 min.
    Once a cluster is found, skip past it to avoid double-counting."""
    # get all failure events sorted by time
    failed = sorted(
        [e for e in logs if e.get("event_type") == "robot_failed"],
        key=lambda e: float(e.get("timestamp", 0)),
    )
    if len(failed) < CLUSTER_MIN_FAILURES:
        return 0  # not enough failures to form any cluster
    timestamps = [float(e["timestamp"]) for e in failed]
    clusters = 0
    i = 0
    while i < len(timestamps):
        window_end = timestamps[i] + CLUSTER_WINDOW_SECONDS  # 30 min from current failure
        # count how many failures fall within this 30-min window
        j = i
        while j < len(timestamps) and timestamps[j] <= window_end:
            j += 1
        count_in_window = j - i
        if count_in_window >= CLUSTER_MIN_FAILURES:
            clusters += 1  # found a cluster
            i = j # skip past it to avoid double-counting
        else:
            i += 1  # no cluster here, move to next failure
    return clusters