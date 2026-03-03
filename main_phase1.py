# =============================================================================
# MAIN PHASE 1 — ENTRY POINT
# This is the file you run: python main_phase1.py
# It creates a WarehouseConfig, runs the simulation, saves the log
# as a JSON file in data/, and prints a summary to the console.
#
# No API keys needed. Just numpy.
# =============================================================================

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# make sure imports work regardless of where you run this from
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from config.warehouse_config import WarehouseConfig
from simulation.warehouse import WarehouseSimulator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main_phase1")

def main() -> None:
    print()
    print("=" * 64)
    print("  PHASE 1 — Warehouse Simulation Engine")
    print("=" * 64)
    print()

    config = WarehouseConfig()

    # log what we're about to do
    logger.info("Duration: %d s (%.1f hours)", config.sim_duration_seconds, config.sim_duration_seconds / 3600)
    logger.info("Seed: %d | Robots: %d | Zones: %s", config.random_seed, config.num_robots, ", ".join(config.zone_names))
    logger.info("High-failure robots: %s", config.high_failure_robot_ids)
    print()

    # run simulation
    sim = WarehouseSimulator(config)
    logs = sim.run()
    summary = sim.get_summary()

    # save to JSON in data/ folder
    data_dir = _project_root / "data"
    data_dir.mkdir(exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"warehouse_logs_{timestamp_str}.json"
    filepath = data_dir / filename
    output = {
        "logs": [entry.model_dump() for entry in logs],
        "summary": summary.model_dump(),
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)
    logger.info("Logs saved to %s", filepath)

    # print summary
    s = summary
    completion_rate = (s.total_tasks_completed / s.total_tasks_generated * 100) if s.total_tasks_generated > 0 else 0.0
    print()
    print("=" * 64)
    print("  SIMULATION SUMMARY")
    print("=" * 64)
    print(f"  Duration            : {s.sim_duration_seconds:,} s ({s.sim_duration_seconds / 3600:.1f} hours)")
    print(f"  Total events        : {s.total_events:,}")
    print(f"  Tasks generated     : {s.total_tasks_generated:,}")
    print(f"  Tasks completed     : {s.total_tasks_completed:,}")
    print(f"  Completion rate     : {completion_rate:.1f}%")
    print(f"  Tasks still queued  : {s.total_tasks_queued_remaining:,}")
    print(f"  Robot failures      : {s.total_robot_failures}")
    print(f"  Charging events     : {s.total_charging_events}")
    print(f"  Conveyor delays     : {s.total_conveyor_delays}")
    print(f"  Zone overloads      : {s.total_zone_overloads}")
    print()
    # per-zone table
    print("  ZONE STATS")
    print("  " + "-" * 50)
    print(f"  {'Zone':<8} {'Arrived':>10} {'Completed':>10} {'Avg Queue':>10}")
    print("  " + "-" * 50)
    for zone in config.zone_names:
        arrived = s.tasks_per_zone.get(zone, 0)
        completed = s.completions_per_zone.get(zone, 0)
        avg_q = s.average_queue_length_per_zone.get(zone, 0.0)
        print(f"  {zone:<8} {arrived:>10,} {completed:>10,} {avg_q:>10.1f}")
    print()
    # per-robot failures
    print("  ROBOT FAILURES")
    print("  " + "-" * 40)
    for rid in range(1, config.num_robots + 1):
        count = int(s.failures_per_robot.get(str(rid), 0))
        marker = "  [!] HIGH-FAILURE" if rid in config.high_failure_robot_ids else ""
        print(f"  Robot {rid:>2}: {count:>3} failures{marker}")
    print()
    print(f"  Log file: {filepath}")
    print("=" * 64)
    print()

if __name__ == "__main__":
    main()