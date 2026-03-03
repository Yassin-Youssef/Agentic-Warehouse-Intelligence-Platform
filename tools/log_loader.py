# =============================================================================
# LOG LOADER
# Reads the JSON log files that Phase 1 saved in data/.
# Also provides filter functions so analyzers can easily pull out
# specific events — like "all task_completed events" or "all events
# for robot 8" or "all events in zone A3".
#
# Every Phase 2 analyzer imports from here. It's the bridge between
# Phase 1's raw JSON output and Phase 2's analysis modules.
# =============================================================================

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# loading functions

def load_latest_log(data_dir: str = "data") -> Dict[str, Any]:
    """Find the most recent JSON log file and return its contents.
    Files are named warehouse_logs_YYYYMMDD_HHMMSS.json so sorting
    alphabetically gives us chronological order — last one is newest."""
    data_path = Path(data_dir)
    json_files = sorted(data_path.glob("*.json"))  # sorted alphabetically = sorted by date
    if not json_files:
        raise FileNotFoundError(f"No JSON log files found in {data_path.resolve()}")
    latest = json_files[-1]  # last file = most recent
    logger.info("Loading latest log file: %s", latest.name)
    return load_log(str(latest))

def load_log(filepath: str) -> Dict[str, Any]:
    """Load a specific log file. Returns dict with 'logs' and 'summary' keys."""
    with open(filepath, "r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)
    logger.info("Loaded %d log entries from %s", len(data.get("logs", [])), filepath)
    return data

# filter functions
# these all take the "logs" list (list of dicts) and return a filtered subset

def get_events_by_type(logs: List[Dict[str, Any]], event_type: str) -> List[Dict[str, Any]]:
    """Filter logs to only events matching a specific type (e.g. 'task_completed')."""
    return [e for e in logs if e.get("event_type") == event_type]

def get_events_by_zone(logs: List[Dict[str, Any]], zone: str) -> List[Dict[str, Any]]:
    """Filter logs to only events in a specific zone (e.g. 'A3')."""
    return [e for e in logs if e.get("zone") == zone]

def get_events_by_robot(logs: List[Dict[str, Any]], robot_id: int) -> List[Dict[str, Any]]:
    """Filter logs to only events for a specific robot. Compares as int."""
    return [e for e in logs if e.get("robot_id") == robot_id]

def get_events_in_timerange(logs: List[Dict[str, Any]], start: float, end: float) -> List[Dict[str, Any]]:
    """Filter logs to events where start <= timestamp < end."""
    return [e for e in logs if start <= e.get("timestamp", -1) < end]

def get_all_zones(logs: List[Dict[str, Any]]) -> List[str]:
    """Get sorted list of unique zone names from the logs."""
    zones = {e["zone"] for e in logs if e.get("zone") is not None}
    return sorted(zones)

def get_all_robot_ids(logs: List[Dict[str, Any]]) -> List[int]:
    """Get sorted list of unique robot IDs from the logs, skipping None entries."""
    ids = {e["robot_id"] for e in logs if e.get("robot_id") is not None}
    return sorted(ids)