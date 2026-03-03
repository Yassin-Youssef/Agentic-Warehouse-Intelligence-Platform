# =============================================================================
# QUEUE ANALYZER
# Checks queue health for each zone:
# - Average and peak queue lengths
# - Queue growth rate (is the queue getting longer over time?)
# - Congestion events (queue > 8 items for 5+ minutes straight)
#
# Growth rate is calculated using linear regression on all
# (timestamp, queue_length) pairs for each zone. A positive slope
# means the queue is growing — tasks are arriving faster than
# robots can handle them.
#
# Congestion threshold: growth rate > 0.0003 items/sec flags a zone.
# This is where Phase 2 detects that A3 is problematic.
# =============================================================================

import logging
from typing import Any, Dict, List
import numpy as np
from schemas.analysis_schema import QueueReport
from tools.log_loader import get_all_zones, get_events_by_zone

logger = logging.getLogger(__name__)
CONGESTION_GROWTH_THRESHOLD = 0.0003  # items per second — above this = congested
CONGESTION_QUEUE_THRESHOLD = 8  # queue length above this = congested period
CONGESTION_DURATION_THRESHOLD = 300.0 # 300 seconds = 5 minutes of sustained congestion

def analyze(logs: List[Dict[str, Any]], sim_duration: int) -> QueueReport:
    """Analyze queue health across all zones."""
    logger.info("Running queue analysis …")
    zones = get_all_zones(logs)
    avg_queue: Dict[str, float] = {}
    peak_queue: Dict[str, int] = {}
    growth_rate: Dict[str, float] = {}
    congested: List[str] = []
    total_congestion_events = 0

    for zone in zones:
        zone_events = get_events_by_zone(logs, zone)
        # collect every (timestamp, queue_length) pair from this zone's events
        # every event logged in a zone includes the queue_length at that moment
        pairs = [
            (float(e["timestamp"]), int(e["queue_length"]))
            for e in zone_events
            if e.get("timestamp") is not None and e.get("queue_length") is not None
        ]
        if not pairs:
            avg_queue[zone] = 0.0
            peak_queue[zone] = 0
            growth_rate[zone] = 0.0
            continue
        pairs.sort(key=lambda p: p[0])  # sort by timestamp
        timestamps = [p[0] for p in pairs]
        queue_lengths = [p[1] for p in pairs]
        avg_queue[zone] = round(float(np.mean(queue_lengths)), 2)
        peak_queue[zone] = int(max(queue_lengths))
        # linear regression: fit a line through (timestamp, queue_length)
        # slope = how fast the queue is growing in items per second
        if len(pairs) >= 2:
            slope = float(np.polyfit(timestamps, queue_lengths, 1)[0])
        else:
            slope = 0.0
        growth_rate[zone] = round(slope, 6)
        # flag zone as congested if growth rate exceeds threshold
        if slope > CONGESTION_GROWTH_THRESHOLD:
            congested.append(zone)
        # count sustained congestion events for this zone
        total_congestion_events += _count_congestion_events(pairs)

    # find zones with worst queue stats
    highest_avg_zone = max(avg_queue, key=avg_queue.get) if avg_queue else ""
    highest_peak_zone = max(peak_queue, key=peak_queue.get) if peak_queue else ""

    report = QueueReport(
        average_queue_length_per_zone=avg_queue,
        peak_queue_length_per_zone=peak_queue,
        queue_growth_rate_per_zone=growth_rate,
        congested_zones=sorted(congested),
        congestion_events=total_congestion_events,
        highest_avg_queue_zone=highest_avg_zone,
        highest_peak_queue_zone=highest_peak_zone,
    )
    logger.info("Queue analysis complete — congested zones: %s", congested or "none")
    return report

def _count_congestion_events(pairs: List[tuple]) -> int:
    """Count how many times queue stays above 8 for 5+ consecutive minutes.
    Scans through the sorted (timestamp, queue_length) pairs and tracks
    when the queue goes above the threshold. If it stays above for 300+
    seconds, that counts as one congestion event."""
    count = 0
    above_start = None  # timestamp when queue first went above threshold
    for ts, ql in pairs:
        if ql > CONGESTION_QUEUE_THRESHOLD:
            if above_start is None:
                above_start = ts  # queue just went above threshold
            elif ts - above_start >= CONGESTION_DURATION_THRESHOLD:
                count += 1 # stayed above for 5+ min = congestion event
                above_start = None # reset and look for next event
        else:
            above_start = None # queue dropped below threshold, reset
    return count