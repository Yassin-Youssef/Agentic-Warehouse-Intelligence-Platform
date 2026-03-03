# =============================================================================
# TASK GENERATOR
# Generates new tasks for each zone every simulated second using a
# Poisson process. The Poisson distribution models random arrivals
# at a known average rate — this is the standard way to simulate
# order arrivals in warehouses, call centers, network packets, etc.
#
# Each zone has its own arrival rate (from config). A3 has 4.0 tasks/min
# while others are around 1.5-2.2, so A3 gets roughly double the tasks.
#
# Each task gets a random priority:
#   1 = high (20%), 2 = medium (50%), 3 = low (30%)
# =============================================================================

from typing import Dict, List
import numpy as np
from numpy.random import Generator
from config.warehouse_config import WarehouseConfig
from schemas.log_schema import Task
from simulation.zone import Zone

class TaskGenerator:
    def __init__(self, config: WarehouseConfig, rng: Generator) -> None:
        self._config = config
        self._rng = rng
        self._task_counter: int = 0  # increments to create unique task ids
        # pull priority options and their probabilities from config
        self._priorities: List[int] = list(config.priority_weights.keys())      # [1, 2, 3]
        self._priority_probs: List[float] = list(config.priority_weights.values())  # [0.2, 0.5, 0.3]

    def generate_tasks(self, current_time: float, zones: Dict[str, Zone]) -> List[Task]:
        """Generate new tasks across all zones for this second."""
        new_tasks: List[Task] = []
        for zone_name, zone in zones.items():
            # poisson draw: convert tasks/min to tasks/sec
            lam = zone.current_arrival_rate / 60.0  # e.g. 4.0/60 = 0.067 for A3
            count: int = int(self._rng.poisson(lam)) # usually 0, sometimes 1, rarely 2+
            for _ in range(count):
                self._task_counter += 1
                task_id = f"T{self._task_counter:06d}"  # T000001, T000002, etc.
                priority = int(self._rng.choice(self._priorities, p=self._priority_probs))
                task = Task(
                    task_id=task_id,
                    zone=zone_name,
                    arrival_timestamp=current_time,
                    priority=priority,
                )
                new_tasks.append(task)
        return new_tasks