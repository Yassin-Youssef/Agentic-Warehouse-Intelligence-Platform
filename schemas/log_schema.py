# =============================================================================
# LOG SCHEMA
# =============================================================================
# Defines all the data models used throughout the simulation.
# - EventType: every kind of event the simulation can produce
# - RobotStatus: the possible states a robot can be in
# - Task: a single pick task in the warehouse
# - LogEntry: one row in the event log (this is what gets saved to JSON)
# - SimulationSummary: end-of-run statistics
#
# Every other file imports from here. This is the shared data language
# of the entire project.
# =============================================================================

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, Optional

# all possible events the simulation can log
class EventType(str, Enum):
    TASK_QUEUED = "task_queued"
    TASK_COMPLETED = "task_completed"
    ROBOT_FAILED = "robot_failed"
    ROBOT_RECOVERED = "robot_recovered"
    ROBOT_CHARGING = "robot_charging"
    ROBOT_CHARGED = "robot_charged"
    ROBOT_IDLE = "robot_idle"
    CONVEYOR_DELAY = "conveyor_delay"
    ZONE_OVERLOAD_START = "zone_overload_start"
    ZONE_OVERLOAD_END = "zone_overload_end"

# possible robot states — robot is always in exactly one of these
class RobotStatus(str, Enum):
    IDLE = "idle"
    TRAVELING = "traveling"
    PICKING = "picking"
    CHARGING = "charging"
    FAILED = "failed"

@dataclass
class Task:
    """A single warehouse pick task."""
    task_id: str                # format: T000001, T000002, etc.
    zone: str                   # which zone this task belongs to
    arrival_timestamp: float    # when it arrived in simulated seconds
    priority: int               # 1=high, 2=medium, 3=low

    def model_dump(self) -> Dict[str, Any]:
        return asdict(self)     # built-in: converts dataclass to dict

@dataclass
class LogEntry:
    """One row in the simulation event log. Every event produces one of these."""
    timestamp: float            # simulated seconds since start
    event_type: str             # one of the EventType values above
    zone: str                   # which zone this event happened in
    robot_id: Optional[int] = None        # which robot (null for zone-only events)
    task_id: Optional[str] = None         # which task (null for non-task events)
    task_duration: Optional[float] = None # how long the pick/delay took
    queue_length: int = 0                 # current queue length in that zone
    battery_level: Optional[float] = None # robot battery at time of event
    downtime_seconds: float = 0.0         # how long robot will be down (failures only)
    priority: Optional[int] = None        # task priority (task events only)

    def model_dump(self) -> Dict[str, Any]:
        """Convert to dict for JSON. Rounds floats to 2 decimals."""
        return {
            "timestamp": round(self.timestamp, 2),
            "event_type": self.event_type,
            "zone": self.zone,
            "robot_id": self.robot_id,
            "task_id": self.task_id,
            "task_duration": round(self.task_duration, 2) if self.task_duration is not None else None,
            "queue_length": self.queue_length,
            "battery_level": round(self.battery_level, 2) if self.battery_level is not None else None,
            "downtime_seconds": round(self.downtime_seconds, 2),
            "priority": self.priority,
        }

@dataclass
class SimulationSummary:
    """Stats collected at the end of a simulation run."""
    sim_duration_seconds: int = 0
    total_events: int = 0
    total_tasks_generated: int = 0
    total_tasks_completed: int = 0
    total_tasks_queued_remaining: int = 0
    total_robot_failures: int = 0
    total_charging_events: int = 0
    total_conveyor_delays: int = 0
    total_zone_overloads: int = 0
    tasks_per_zone: Dict[str, int] = field(default_factory=dict)         # zone -> tasks arrived
    completions_per_zone: Dict[str, int] = field(default_factory=dict)   # zone -> tasks completed
    failures_per_robot: Dict[str, int] = field(default_factory=dict)     # robot id (str) -> failure count
    average_queue_length_per_zone: Dict[str, float] = field(default_factory=dict)
    config_snapshot: Dict[str, Any] = field(default_factory=dict)        # copy of config for traceability

    def model_dump(self) -> Dict[str, Any]:
        return asdict(self)