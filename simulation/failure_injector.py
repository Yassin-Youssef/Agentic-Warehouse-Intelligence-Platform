# =============================================================================
# FAILURE INJECTOR
# Injects three types of disruption into the simulation:
#
# 1. Robot failures: after each task completion, roll a random chance.
#    Normal robots: 3%. Robots 8,9,10: 10.5%. If failed, robot goes
#    offline for 120-300 seconds (2-5 min).
#
# 2. Conveyor delays: 10% of tasks get an extra 5-20 seconds added
#    to their pick duration. Simulates mechanical slowdowns.
#
# 3. Zone overloads: roughly every 30 min (exponential distribution),
#    a random zone gets double arrival rate for 5 minutes.
#    Exponential means the timing is random — sometimes 20 min apart,
#    sometimes 45 min. More realistic than fixed intervals.
#
# Without these disruptions, the simulation would run perfectly and
# there would be nothing for the analysis layer to detect.
# =============================================================================

import logging
from typing import Dict, Optional, Tuple
from numpy.random import Generator
from config.warehouse_config import WarehouseConfig
from simulation.robot import Robot
from simulation.zone import Zone

logger = logging.getLogger(__name__)

class FailureInjector:
    def __init__(self, config: WarehouseConfig, rng: Generator) -> None:
        self._config = config
        self._rng = rng
        # schedule the first overload using exponential distribution
        self._next_overload_time: float = float(
            self._rng.exponential(config.overload_interval_mean_seconds)
        )
        self._active_overload: Optional[_OverloadEvent] = None  # tracks current overload

    def check_robot_failure(self, robot: Robot) -> Optional[float]:
        """Roll for failure after a task. Returns downtime if failed, None if ok."""
        rate = self._config.get_failure_rate(robot.id)  # 3% or 10.5%
        if self._rng.random() < rate:  # random float 0-1, if below rate = failure
            low, high = self._config.failure_downtime_range
            downtime = float(self._rng.uniform(low, high))  # 120-300 seconds
            return downtime
        return None

    def apply_conveyor_delay(self) -> Optional[float]:
        """10% chance to add 5-20 extra seconds to a task. Returns delay or None."""
        if self._rng.random() < self._config.conveyor_delay_probability:
            low, high = self._config.conveyor_delay_range
            return float(self._rng.uniform(low, high))
        return None

    def tick_overload(self, current_time: float, zones: Dict[str, Zone]) -> Optional[Tuple[str, str]]:
        """Check overload status every second. Returns (zone_name, 'start'/'end') or None."""
        # if there's an active overload, check if it should end
        if self._active_overload is not None:
            if current_time >= self._active_overload.end_time:
                zone_name = self._active_overload.zone_name
                zones[zone_name].reset_arrival_rate()  # back to normal
                self._active_overload = None
                # schedule next overload
                self._next_overload_time = current_time + float(
                    self._rng.exponential(self._config.overload_interval_mean_seconds)
                )
                return (zone_name, "end")
            return None
        # if no active overload, check if it's time to start one
        if current_time >= self._next_overload_time:
            zone_names = list(zones.keys())
            zone_name = str(self._rng.choice(zone_names))  # pick random zone
            zones[zone_name].apply_overload(self._config.overload_rate_multiplier)  # double rate
            end_time = current_time + self._config.overload_duration_seconds  # 5 min from now
            self._active_overload = _OverloadEvent(zone_name=zone_name, end_time=end_time)
            logger.info("Zone overload START: %s (until t=%.0f)", zone_name, end_time)
            return (zone_name, "start")
        return None

class _OverloadEvent:
    """Simple container to track which zone is overloaded and when it ends."""
    __slots__ = ("zone_name", "end_time")  # memory optimization, no __dict__ needed
    def __init__(self, zone_name: str, end_time: float) -> None:
        self.zone_name = zone_name
        self.end_time = end_time