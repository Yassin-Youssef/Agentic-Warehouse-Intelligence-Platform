# =============================================================================
# ANALYSIS SCHEMA
# Defines the data models for all Phase 2 analysis reports.
# Each analyzer (throughput, queue, utilization, downtime, cost)
# produces one of these dataclasses. They all get combined into
# a WarehouseAnalysisReport which is saved as JSON.
#
# This is the shared output format of Phase 2. Phase 3's agents
# will read these reports to generate their recommendations.
#
# model_dump() on each report converts it to a plain dict for JSON.
# Some reports need to convert int keys to strings because JSON
# only supports string keys (e.g. robot_id 8 -> "8").
# =============================================================================

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

@dataclass
class ThroughputReport:
    """How many tasks got done, how fast, and whether it's trending up or down."""
    total_tasks_completed: int = 0
    tasks_per_hour: List[int] = field(default_factory=list) # e.g. [801, 830, 825, 837]
    average_throughput_per_hour: float = 0.0  # mean of tasks_per_hour
    tasks_per_zone: Dict[str, int] = field(default_factory=dict)   # zone -> total completions
    tasks_per_zone_per_hour: Dict[str, List[int]] = field(default_factory=dict)  # zone -> hourly breakdown
    throughput_trend_slope: float = 0.0 # from linear regression on hourly counts
    throughput_trend: str = "stable" # "increasing", "decreasing", or "stable"
    highest_performing_zone: str = ""
    lowest_performing_zone: str = ""
    highest_zone_throughput_per_hour: float = 0.0
    lowest_zone_throughput_per_hour: float = 0.0
    def model_dump(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class QueueReport:
    """How congested are the zone queues and are they getting worse."""
    average_queue_length_per_zone: Dict[str, float] = field(default_factory=dict)
    peak_queue_length_per_zone: Dict[str, int] = field(default_factory=dict)
    queue_growth_rate_per_zone: Dict[str, float] = field(default_factory=dict)  # slope from linear regression
    congested_zones: List[str] = field(default_factory=list)   # zones with growth rate > threshold
    congestion_events: int = 0  # times queue stayed > 8 for 5+ minutes
    highest_avg_queue_zone: str = ""
    highest_peak_queue_zone: str = ""
    def model_dump(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class RobotMetrics:
    """Time breakdown for a single robot."""
    active_time: float = 0.0  # seconds spent picking
    failed_time: float = 0.0   # seconds spent broken
    charging_time: float = 0.0 # seconds spent charging
    idle_time: float = 0.0  # seconds doing nothing
    utilization_rate: float = 0.0  # active_time / sim_duration * 100
    idle_rate: float = 0.0   # idle_time / sim_duration * 100
    failed_rate: float = 0.0 # failed_time / sim_duration * 100
    num_tasks: int = 0
    def model_dump(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class UtilizationReport:
    """How busy is each robot and the fleet overall."""
    robot_metrics: Dict[int, Dict[str, Any]] = field(default_factory=dict)  # robot_id -> metrics dict
    underutilized_robots: List[Tuple[int, float]] = field(default_factory=list)  # (robot_id, idle_rate)
    overworked_robots: List[Tuple[int, float]] = field(default_factory=list)     # (robot_id, utilization_rate)
    fleet_average_utilization: float = 0.0
    def model_dump(self) -> Dict[str, Any]:
        d = asdict(self)
        # JSON keys must be strings, but robot_ids are ints — convert them
        d["robot_metrics"] = {str(k): v for k, v in self.robot_metrics.items()}
        return d

@dataclass
class RobotDowntime:
    """Downtime stats for a single robot."""
    failure_count: int = 0
    total_downtime: float = 0.0  # total seconds spent broken
    mtbf_minutes: float = 0.0  # mean time between failures in minutes
    downtime_percentage: float = 0.0  # what % of sim time was this robot broken
    reliability_score: float = 100.0  # 100 = perfect, 0 = always broken
    def model_dump(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class DowntimeReport:
    """Fleet-wide failure and reliability analysis."""
    robot_downtimes: Dict[int, Dict[str, Any]] = field(default_factory=dict)  # robot_id -> downtime stats
    total_failures: int = 0
    fleet_failure_rate: float = 0.0  # failures per robot-hour
    least_reliable_robot: int = 0
    most_reliable_robot: int = 0
    failure_clusters: int = 0  # groups of 3+ failures within 30 min
    def model_dump(self) -> Dict[str, Any]:
        d = asdict(self)
        d["robot_downtimes"] = {str(k): v for k, v in self.robot_downtimes.items()}
        return d

@dataclass
class CostReport:
    """Dollar cost of all inefficiencies."""
    idle_cost: float = 0.0   # cost of robots sitting idle
    delay_cost: float = 0.0 # cost of conveyor delays
    failure_cost: float = 0.0  # cost of robot breakdowns
    queue_cost: float = 0.0  # cost of tasks waiting in queue
    total_inefficiency_cost: float = 0.0
    cost_breakdown: Dict[str, Dict[str, float]] = field(default_factory=dict)  # category -> {amount, percentage}
    def model_dump(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class WarehouseAnalysisReport:
    """Top-level container that holds all 5 sub-reports plus metadata."""
    source_file: str = ""   # which log file was analyzed
    analysis_timestamp: str = ""# when the analysis ran
    sim_duration_seconds: int = 0
    throughput: Optional[ThroughputReport] = None
    queue: Optional[QueueReport] = None
    utilization: Optional[UtilizationReport] = None
    downtime: Optional[DowntimeReport] = None
    cost: Optional[CostReport] = None
    def model_dump(self) -> Dict[str, Any]:
        """Convert everything to dicts. Calls model_dump() on each sub-report."""
        return {
            "source_file": self.source_file,
            "analysis_timestamp": self.analysis_timestamp,
            "sim_duration_seconds": self.sim_duration_seconds,
            "throughput": self.throughput.model_dump() if self.throughput else None,
            "queue": self.queue.model_dump() if self.queue else None,
            "utilization": self.utilization.model_dump() if self.utilization else None,
            "downtime": self.downtime.model_dump() if self.downtime else None,
            "cost": self.cost.model_dump() if self.cost else None,
        }