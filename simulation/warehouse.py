# =============================================================================
# WAREHOUSE SIMULATOR
# This is the main simulation engine. It creates the zones, robots, and
# all subsystems, then runs a loop for 14,400 seconds (4 hours).
#
# Every simulated second, the loop does:
#   1. Generate new tasks (Poisson arrivals per zone)
#   2. Assign idle robots to queued tasks
#   3. Tick all robots (count down their timers)
#   4. Handle transitions (pick done -> check failure -> maybe charge)
#   5. Log idle robots every 60 seconds
#   6. Check zone overload events
#   7. Accumulate queue lengths for average calculation
#
# After the loop, get_summary() produces the final statistics.
# The logs list and summary get saved to JSON by main_phase1.py.
# =============================================================================

import logging
from collections import defaultdict
from typing import Dict, List, Optional
import numpy as np
from numpy.random import Generator
from config.warehouse_config import WarehouseConfig
from schemas.log_schema import EventType, LogEntry, SimulationSummary, Task
from simulation.dispatcher import Dispatcher
from simulation.failure_injector import FailureInjector
from simulation.robot import Robot
from simulation.task_generator import TaskGenerator
from simulation.zone import Zone

logger = logging.getLogger(__name__)

class WarehouseSimulator:
    def __init__(self, config: WarehouseConfig) -> None:
        self._config = config
        self._rng: Generator = np.random.default_rng(config.random_seed)  # seeded RNG
        # create all zones from config
        self._zones: Dict[str, Zone] = {
            name: Zone(name=name, base_arrival_rate=rate)
            for name, rate in config.zone_configs.items()
        }
        # create all robots from config
        self._robots: List[Robot] = [
            Robot(id=rid, home_zone=hz)
            for rid, hz in config.robot_home_zones.items()
        ]
        # subsystems that the loop uses
        self._task_gen = TaskGenerator(config, self._rng)
        self._dispatcher = Dispatcher(config, self._rng)
        self._failure_injector = FailureInjector(config, self._rng)
        # event log — every event in the simulation gets appended here
        self._logs: List[LogEntry] = []
        # counters for the summary
        self._tasks_generated: int = 0
        self._tasks_completed: int = 0
        self._total_failures: int = 0
        self._total_charging: int = 0
        self._total_conveyor_delays: int = 0
        self._total_zone_overloads: int = 0
        self._failures_per_robot: Dict[int, int] = defaultdict(int)   # auto-initializes to 0
        self._completions_per_zone: Dict[str, int] = defaultdict(int)
        self._tasks_per_zone: Dict[str, int] = defaultdict(int)
        # for computing average queue lengths
        self._queue_length_sum: Dict[str, float] = defaultdict(float)
        self._queue_length_samples: int = 0

    def run(self) -> List[LogEntry]:
        """Run the full 4-hour simulation and return the event log."""
        duration = self._config.sim_duration_seconds
        progress_interval = self._config.progress_log_interval_seconds
        logger.info("Simulation starting — %d seconds, seed=%d", duration, self._config.random_seed)

        for t in range(duration):
            current_time = float(t)

            # step 1: generate new tasks
            new_tasks = self._task_gen.generate_tasks(current_time, self._zones)
            for task in new_tasks:
                self._zones[task.zone].add_task(task)  # add to zone queue
                self._tasks_generated += 1
                self._tasks_per_zone[task.zone] += 1
                self._logs.append(LogEntry(
                    timestamp=current_time,
                    event_type=EventType.TASK_QUEUED.value,
                    zone=task.zone,
                    task_id=task.task_id,
                    queue_length=self._zones[task.zone].queue_length,
                    priority=task.priority,
                ))

            # step 2: assign idle robots to tasks
            assignments = self._dispatcher.dispatch(self._robots, self._zones)
            for robot, task, travel_time, pick_duration in assignments:
                # check if this task gets a conveyor delay
                delay = self._failure_injector.apply_conveyor_delay()
                if delay is not None:
                    pick_duration += delay  # add extra time to pick
                    self._total_conveyor_delays += 1
                    self._logs.append(LogEntry(
                        timestamp=current_time,
                        event_type=EventType.CONVEYOR_DELAY.value,
                        zone=task.zone,
                        robot_id=robot.id,
                        task_id=task.task_id,
                        task_duration=delay,
                        queue_length=self._zones[task.zone].queue_length,
                    ))
                # send robot to work
                if travel_time > 0:
                    robot.start_travel(task.zone, travel_time, task.task_id, pick_duration)
                else:
                    robot.start_pick(task.task_id, pick_duration)  # same zone, no travel

            # step 3: tick all robots and handle what comes back
            for robot in self._robots:
                event = robot.tick()  # returns None, 'pick_done', 'charge_done', 'recover', or 'travel_done'
                if event == "pick_done":
                    self._tasks_completed += 1
                    self._completions_per_zone[robot.current_zone] += 1
                    self._logs.append(LogEntry(
                        timestamp=current_time,
                        event_type=EventType.TASK_COMPLETED.value,
                        zone=robot.current_zone,
                        robot_id=robot.id,
                        task_id=robot.current_task_id,
                        task_duration=robot.task_pick_duration,
                        queue_length=self._zones[robot.current_zone].queue_length,
                        battery_level=robot.battery_level,
                    ))
                    # step 4: after finishing a task, check if robot fails
                    downtime = self._failure_injector.check_robot_failure(robot)
                    if downtime is not None:
                        robot.fail(downtime)
                        self._total_failures += 1
                        self._failures_per_robot[robot.id] += 1
                        self._logs.append(LogEntry(
                            timestamp=current_time,
                            event_type=EventType.ROBOT_FAILED.value,
                            zone=robot.current_zone,
                            robot_id=robot.id,
                            battery_level=robot.battery_level,
                            downtime_seconds=downtime,
                            queue_length=self._zones[robot.current_zone].queue_length,
                        ))
                    elif robot.needs_charging:
                        # no failure, but battery is low — go charge
                        charge_time = float(self._rng.uniform(*self._config.charge_time_range))
                        robot.start_charging(charge_time)
                        self._total_charging += 1
                        self._logs.append(LogEntry(
                            timestamp=current_time,
                            event_type=EventType.ROBOT_CHARGING.value,
                            zone=robot.current_zone,
                            robot_id=robot.id,
                            battery_level=robot.battery_level,
                            queue_length=self._zones[robot.current_zone].queue_length,
                        ))
                elif event == "charge_done":
                    self._logs.append(LogEntry(
                        timestamp=current_time,
                        event_type=EventType.ROBOT_CHARGED.value,
                        zone=robot.current_zone,
                        robot_id=robot.id,
                        battery_level=robot.battery_level,
                        queue_length=self._zones[robot.current_zone].queue_length,
                    ))
                elif event == "recover":
                    self._logs.append(LogEntry(
                        timestamp=current_time,
                        event_type=EventType.ROBOT_RECOVERED.value,
                        zone=robot.current_zone,
                        robot_id=robot.id,
                        battery_level=robot.battery_level,
                        queue_length=self._zones[robot.current_zone].queue_length,
                    ))

            # step 5: catch any idle robots that need charging
            for robot in self._robots:
                if robot.is_idle and robot.needs_charging:
                    charge_time = float(self._rng.uniform(*self._config.charge_time_range))
                    robot.start_charging(charge_time)
                    self._total_charging += 1
                    self._logs.append(LogEntry(
                        timestamp=current_time,
                        event_type=EventType.ROBOT_CHARGING.value,
                        zone=robot.current_zone,
                        robot_id=robot.id,
                        battery_level=robot.battery_level,
                        queue_length=self._zones[robot.current_zone].queue_length,
                    ))

            # step 6: log idle robots every 60 seconds
            if t > 0 and t % self._config.idle_log_interval_seconds == 0:
                for robot in self._robots:
                    if robot.is_idle:
                        self._logs.append(LogEntry(
                            timestamp=current_time,
                            event_type=EventType.ROBOT_IDLE.value,
                            zone=robot.current_zone,
                            robot_id=robot.id,
                            battery_level=robot.battery_level,
                            queue_length=self._zones[robot.current_zone].queue_length,
                        ))

            # step 7: check zone overloads
            overload_result = self._failure_injector.tick_overload(current_time, self._zones)
            if overload_result is not None:
                zone_name, kind = overload_result
                if kind == "start":
                    self._total_zone_overloads += 1
                    self._logs.append(LogEntry(
                        timestamp=current_time,
                        event_type=EventType.ZONE_OVERLOAD_START.value,
                        zone=zone_name,
                        queue_length=self._zones[zone_name].queue_length,
                    ))
                else:
                    self._logs.append(LogEntry(
                        timestamp=current_time,
                        event_type=EventType.ZONE_OVERLOAD_END.value,
                        zone=zone_name,
                        queue_length=self._zones[zone_name].queue_length,
                    ))

            # accumulate queue lengths every tick (for computing averages later)
            for zn, zone in self._zones.items():
                self._queue_length_sum[zn] += zone.queue_length
            self._queue_length_samples += 1

            # print progress every 15 simulated minutes
            if t > 0 and t % progress_interval == 0:
                mins = t / 60
                logger.info(
                    "[t=%5.0fs / %3.0fmin]  tasks_gen=%d  completed=%d  failures=%d  charging=%d",
                    current_time, mins, self._tasks_generated,
                    self._tasks_completed, self._total_failures, self._total_charging,
                )

        logger.info("Simulation complete — %d events logged.", len(self._logs))
        return self._logs

    def get_summary(self) -> SimulationSummary:
        """Build final stats after the simulation finishes."""
        remaining = sum(z.queue_length for z in self._zones.values())  # tasks still in queues
        avg_ql: Dict[str, float] = {}
        if self._queue_length_samples > 0:
            for zn in self._zones:
                avg_ql[zn] = round(self._queue_length_sum[zn] / self._queue_length_samples, 2)
        return SimulationSummary(
            sim_duration_seconds=self._config.sim_duration_seconds,
            total_events=len(self._logs),
            total_tasks_generated=self._tasks_generated,
            total_tasks_completed=self._tasks_completed,
            total_tasks_queued_remaining=remaining,
            total_robot_failures=self._total_failures,
            total_charging_events=self._total_charging,
            total_conveyor_delays=self._total_conveyor_delays,
            total_zone_overloads=self._total_zone_overloads,
            tasks_per_zone=dict(self._tasks_per_zone),
            completions_per_zone=dict(self._completions_per_zone),
            failures_per_robot={str(k): v for k, v in self._failures_per_robot.items()},
            average_queue_length_per_zone=avg_ql,
            config_snapshot=self._config.model_dump(),
        )

    @property
    def logs(self) -> List[LogEntry]:
        return self._logs