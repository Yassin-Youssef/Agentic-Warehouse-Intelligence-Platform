# =============================================================================
# DISPATCHER
# Assigns queued tasks to idle robots. The strategy:
# 1. For each idle robot, check its current zone for tasks
# 2. If none, send it to the busiest zone (highest queue length)
# 3. If same zone: travel time = 0, start picking immediately
#    If different zone: travel time = random 8-40 seconds
# 4. Pick duration = normal distribution (mean 18s, std 5s, min 6s)
#
# This is a greedy heuristic — not optimal, but realistic.
# Real warehouses use similar nearest-first strategies.
# =============================================================================

from typing import Dict, List, Optional, Tuple
from numpy.random import Generator
from config.warehouse_config import WarehouseConfig
from schemas.log_schema import Task
from simulation.robot import Robot
from simulation.zone import Zone

class Dispatcher:
    def __init__(self, config: WarehouseConfig, rng: Generator) -> None:
        self._config = config
        self._rng = rng

    def dispatch(self, robots: List[Robot], zones: Dict[str, Zone]) -> List[Tuple[Robot, Task, float, float]]:
        """Try to assign a task to every idle robot.
        Returns list of (robot, task, travel_time, pick_duration) tuples."""
        assignments: List[Tuple[Robot, Task, float, float]] = []
        for robot in robots:
            if not robot.is_idle:     # skip robots already doing something
                continue
            if robot.needs_charging:  # skip robots that need to charge
                continue
            task, zone_name = self._find_task(robot, zones)
            if task is None:          # no tasks available anywhere
                continue
            travel_time = self._travel_time(robot.current_zone, zone_name)
            pick_duration = self._pick_duration()
            assignments.append((robot, task, travel_time, pick_duration))
        return assignments

    def _find_task(self, robot: Robot, zones: Dict[str, Zone]) -> Tuple[Optional[Task], str]:
        """Find the best task for this robot."""
        # first: check robot's current zone
        current_zone = zones.get(robot.current_zone)
        if current_zone and current_zone.queue_length > 0:
            task = current_zone.pop_task()
            if task:
                return task, robot.current_zone
        # second: find the busiest zone and go there
        busiest_name: Optional[str] = None
        busiest_len: int = 0
        for name, zone in zones.items():
            if zone.queue_length > busiest_len:
                busiest_len = zone.queue_length
                busiest_name = name
        if busiest_name is not None and busiest_len > 0:
            task = zones[busiest_name].pop_task()
            if task:
                return task, busiest_name
        return None, ""  # nothing available

    def _travel_time(self, from_zone: str, to_zone: str) -> float:
        """0 if same zone, otherwise random 8-40 seconds."""
        if from_zone == to_zone:
            return 0.0
        low, high = self._config.travel_time_range
        return float(self._rng.uniform(low, high))

    def _pick_duration(self) -> float:
        """Random pick time: normal(mean=18, std=5), minimum 6 seconds."""
        dur = self._rng.normal(self._config.pick_duration_mean, self._config.pick_duration_std)
        return max(self._config.pick_duration_floor, float(dur))