# =============================================================================
# ROBOT
# Each robot is a state machine that cycles through:
#   idle -> traveling -> picking -> idle (normal loop)
# with possible diversions to:
#   charging (battery low) or failed (random breakdown)
#
# The tick() method is called every simulated second. It counts down
# the action timer and returns an event string when a transition happens.
# Most ticks return None (robot is still doing the same thing).
#
# The robot also tracks how much total time it spends in each state,
# which Phase 2 uses to calculate utilization rates.
# =============================================================================

from dataclasses import dataclass, field
from typing import Dict, Optional
from schemas.log_schema import RobotStatus

@dataclass
class Robot:
    id: int # robot id (1-10)
    home_zone: str   # where this robot starts
    current_zone: str = ""     # where it currently is
    battery_level: float = 100.0   # starts fully charged
    status: RobotStatus = RobotStatus.IDLE # current state
    # internal timers
    _action_remaining: float = 0.0 # seconds left in current action
    _current_task_id: Optional[str] = None # which task its working on
    _travel_destination: Optional[str] = None  # where its heading
    _task_pick_duration: float = 0.0       # stored for logging when pick finishes
    # tracks total time spent in each state (used by Phase 2 utilization analyzer)
    state_time: Dict[str, float] = field(default_factory=lambda: {
        "idle": 0.0, "traveling": 0.0, "picking": 0.0,
        "charging": 0.0, "failed": 0.0,
    })

    def __post_init__(self) -> None:
        if not self.current_zone:
            self.current_zone = self.home_zone  # start at home zone

    # state transitions
    def start_travel(self, destination: str, travel_time: float, task_id: str,
                     pick_duration: float) -> None:
        """Start moving to another zone to pick a task."""
        self.status = RobotStatus.TRAVELING
        self._action_remaining = travel_time
        self._travel_destination = destination
        self._current_task_id = task_id
        self._task_pick_duration = pick_duration
        self.battery_level = max(0.0, self.battery_level - 0.1)  # small drain for travel

    def start_pick(self, task_id: str, pick_duration: float) -> None:
        """Start picking a task in the current zone (no travel needed)."""
        self.status = RobotStatus.PICKING
        self._action_remaining = pick_duration
        self._current_task_id = task_id
        self._task_pick_duration = pick_duration

    def start_charging(self, charge_time: float) -> None:
        """Go to charging station."""
        self.status = RobotStatus.CHARGING
        self._action_remaining = charge_time
        self._current_task_id = None

    def fail(self, downtime: float) -> None:
        """Break down for downtime seconds."""
        self.status = RobotStatus.FAILED
        self._action_remaining = downtime
        self._current_task_id = None

    def set_idle(self) -> None:
        self.status = RobotStatus.IDLE
        self._action_remaining = 0.0
        self._current_task_id = None

    # tick (called every simulated second)
    def tick(self) -> Optional[str]:
        """Advance 1 second. Returns event string on state transition, None otherwise.
        Possible returns: 'travel_done', 'pick_done', 'charge_done', 'recover'"""
        self.state_time[self.status.value] += 1.0  # track time in current state
        if self._action_remaining <= 0:
            return None  # nothing to count down
        self._action_remaining -= 1.0  # count down
        if self._action_remaining <= 0:  # timer just hit zero — transition
            if self.status == RobotStatus.TRAVELING:
                # arrived at destination, now start picking
                self.current_zone = self._travel_destination or self.current_zone
                self._travel_destination = None
                self.status = RobotStatus.PICKING
                self._action_remaining = self._task_pick_duration
                return "travel_done"
            if self.status == RobotStatus.PICKING:
                # finished picking, drain battery, go idle
                self.battery_level = max(0.0, self.battery_level - 0.5)
                self.status = RobotStatus.IDLE
                self._action_remaining = 0.0
                self._current_task_id = None
                return "pick_done"
            if self.status == RobotStatus.CHARGING:
                # fully charged, go idle
                self.battery_level = 100.0
                self.status = RobotStatus.IDLE
                self._action_remaining = 0.0
                return "charge_done"
            if self.status == RobotStatus.FAILED:
                # repaired, go idle
                self.status = RobotStatus.IDLE
                self._action_remaining = 0.0
                return "recover"
        return None

    # helpers
    @property
    def is_idle(self) -> bool:
        return self.status == RobotStatus.IDLE

    @property
    def needs_charging(self) -> bool:
        return self.battery_level < 15.0

    @property
    def current_task_id(self) -> Optional[str]:
        return self._current_task_id

    @property
    def task_pick_duration(self) -> float:
        return self._task_pick_duration