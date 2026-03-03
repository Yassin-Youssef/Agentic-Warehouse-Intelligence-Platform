# =============================================================================
# WAREHOUSE CONFIG
# =============================================================================
# This file holds every single parameter used in the warehouse simulation.
# Instead of hardcoding numbers across different files, everything lives here.
# If I want to change the simulation (more robots, faster picking, etc.),
# I only need to change this one file.
#
# The config is a dataclass, which means Python auto-generates the __init__
# method from the fields I declare. Each field has a default value so I can
# create a config with WarehouseConfig() and everything just works.
# =============================================================================

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

@dataclass
class WarehouseConfig:
    # --- simulation timing ---
    sim_duration_seconds: int = 14_400       # 4 hours (4 * 60 * 60)
    random_seed: int = 42                    # fixed seed so results are reproducible
    time_step_seconds: int = 1               # simulation advances 1 second at a time
    # --- zones ---
    # each zone has a name and an arrival rate (tasks per minute)
    # A3 is double the average on purpose — creates congestion for analysis to detect
    zone_configs: Dict[str, float] = field(default_factory=lambda: {
        "A1": 2.0, "A2": 1.8, "A3": 4.0,
        "B1": 1.5, "B2": 2.2, "B3": 1.9,
    })
    # --- robots ---
    # maps robot id to its home zone
    # B1 has no home robots on purpose — it gets underserved
    num_robots: int = 10
    robot_home_zones: Dict[int, str] = field(default_factory=lambda: {
        1: "A1", 2: "A1",
        3: "A2", 4: "A2",
        5: "A3", 6: "A3",
        7: "B2", 8: "B2",
        9: "B3", 10: "B3",
    })
    # --- failure rates ---
    base_failure_rate: float = 0.03          # 3% chance of breaking after each task
    high_failure_multiplier: float = 3.5     # robots 8,9,10 get 3% * 3.5 = 10.5%
    high_failure_robot_ids: List[int] = field(default_factory=lambda: [8, 9, 10])
    failure_downtime_range: Tuple[int, int] = (120, 300)  # broken for 2-5 min
    # --- battery ---
    battery_full: float = 100.0              # starts at 100%
    battery_drain_per_task: float = 0.5      # loses 0.5% per pick
    battery_drain_per_travel: float = 0.1    # loses 0.1% per travel
    battery_low_threshold: float = 15.0      # goes to charge below 15%
    charge_time_range: Tuple[int, int] = (60, 120)  # charging takes 1-2 min
    # --- travel and picking ---
    travel_time_range: Tuple[int, int] = (8, 40)    # 8-40 sec to travel between zones
    pick_duration_mean: float = 18.0         # average pick time
    pick_duration_std: float = 5.0           # spread around the average
    pick_duration_floor: float = 6.0         # pick can never be less than 6 sec
    # --- conveyor delays ---
    conveyor_delay_probability: float = 0.10         # 10% of tasks get delayed
    conveyor_delay_range: Tuple[int, int] = (5, 20)  # extra 5-20 sec added
    # --- zone overloads ---
    # roughly every 30 min, a random zone gets double the arrival rate for 5 min
    overload_interval_mean_seconds: float = 1800.0   # avg time between overloads
    overload_duration_seconds: float = 300.0          # overload lasts 5 min
    overload_rate_multiplier: float = 2.0             # arrival rate doubles
    # --- task priorities ---
    # 1 = high (20%), 2 = medium (50%), 3 = low (30%)
    priority_weights: Dict[int, float] = field(default_factory=lambda: {
        1: 0.20, 2: 0.50, 3: 0.30,
    })
    # --- logging intervals ---
    idle_log_interval_seconds: int = 60      # log idle robots every 60 sec
    progress_log_interval_seconds: int = 900 # print progress every 15 min

    def get_failure_rate(self, robot_id: int) -> float:
        """Returns the failure chance for a specific robot.
        Robots 8, 9, 10 have 3.5x higher rate than normal."""
        if robot_id in self.high_failure_robot_ids:
            return self.base_failure_rate * self.high_failure_multiplier
        return self.base_failure_rate

    @property
    def zone_names(self) -> List[str]:
        return list(self.zone_configs.keys())

    @property
    def zone_arrival_rates(self) -> Dict[str, float]:
        return dict(self.zone_configs)

    def model_dump(self) -> Dict:
        """Converts config to a plain dict so it can be saved as JSON.
        JSON needs string keys, so robot ids get converted from int to str."""
        return {
            "sim_duration_seconds": self.sim_duration_seconds,
            "random_seed": self.random_seed,
            "num_robots": self.num_robots,
            "zone_configs": self.zone_configs,
            "robot_home_zones": {str(k): v for k, v in self.robot_home_zones.items()},
            "base_failure_rate": self.base_failure_rate,
            "high_failure_multiplier": self.high_failure_multiplier,
            "high_failure_robot_ids": self.high_failure_robot_ids,
            "battery_low_threshold": self.battery_low_threshold,
            "pick_duration_mean": self.pick_duration_mean,
            "pick_duration_std": self.pick_duration_std,
            "conveyor_delay_probability": self.conveyor_delay_probability,
            "overload_interval_mean_seconds": self.overload_interval_mean_seconds,
        }