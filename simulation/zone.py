# =============================================================================
# ZONE
# A zone is one section of the warehouse (A1, A2, A3, B1, B2, B3).
# Each zone has:
# - A base arrival rate (how many tasks per minute come in)
# - A current arrival rate (can change during overload events)
# - A priority queue of waiting tasks
#
# The queue uses Python's heapq (min-heap). Tasks are stored as
# (priority, sequence_number, task) tuples. Since priority 1 < 3,
# high-priority tasks always come out first. The sequence number
# breaks ties so tasks with the same priority come out in FIFO order.
# =============================================================================

import heapq
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from schemas.log_schema import Task

@dataclass
class Zone:
    name: str                      # zone id like "A1", "B2"
    base_arrival_rate: float       # tasks per minute (from config)
    current_arrival_rate: float = 0.0  # can be temporarily doubled during overloads
    _queue: List[Tuple[int, int, Task]] = field(default_factory=list, repr=False)  # the heap
    _seq: int = field(default=0, repr=False)  # tiebreaker counter for same-priority tasks

    def __post_init__(self) -> None:
        # if no current rate set, use the base rate
        if self.current_arrival_rate == 0.0:
            self.current_arrival_rate = self.base_arrival_rate

    def add_task(self, task: Task) -> None:
        """Push a task onto the priority queue."""
        self._seq += 1  # increment so each task gets a unique sequence number
        heapq.heappush(self._queue, (task.priority, self._seq, task))

    def pop_task(self) -> Optional[Task]:
        """Remove and return the highest-priority task, or None if empty."""
        if self._queue:
            _, _, task = heapq.heappop(self._queue)  # ignore priority and seq, just return task
            return task
        return None

    @property
    def queue_length(self) -> int:
        return len(self._queue)

    def peek(self) -> Optional[Task]:
        """Look at the next task without removing it."""
        if self._queue:
            return self._queue[0][2]  # [0] = top of heap, [2] = the task object
        return None

    def apply_overload(self, multiplier: float) -> None:
        """Temporarily multiply the arrival rate (used during zone overload events)."""
        self.current_arrival_rate = self.base_arrival_rate * multiplier

    def reset_arrival_rate(self) -> None:
        """Restore arrival rate back to normal after overload ends."""
        self.current_arrival_rate = self.base_arrival_rate