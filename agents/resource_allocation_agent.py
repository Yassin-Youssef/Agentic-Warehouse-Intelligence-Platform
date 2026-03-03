# =============================================================================
# RESOURCE ALLOCATION AGENT
# Suggests specific robot moves — which robots should go where.
# Reads utilization data (who's idle, who's overworked) and queue data
# (which zones are congested) and asks the LLM to propose concrete
# rebalancing strategies.
#
# For example: "Robot 2 has 40.9% idle time and is stationed at A1.
# Zone A3 has the highest queue. Reassigning Robot 2 to A3 could
# reduce A3's queue by approximately 15%."
#
# The agent references actual robot IDs and zone names from the data.
# =============================================================================

import json
from agents.base_agent import BaseAgent

class ResourceAllocationAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            name="Resource Allocation Agent",
            description="Suggests robot redistribution strategies",
            system_prompt=(
                "You are a warehouse resource optimization specialist. You see robot "
                "utilization data and queue data. Suggest specific task redistribution "
                "strategies. RULES: Reference actual robot IDs and zone names. Be concrete "
                "— say exactly which robots should move where and why. Base suggestions "
                "only on the data provided."
            ),
        )

    def _build_prompt(self, report: dict) -> str:
        """Pull utilization (per-robot idle/active rates) and queue data
        (which zones need help) and ask for specific rebalancing moves."""
        util = report.get("utilization", {})   # who's idle, who's busy
        q = report.get("queue", {}) # which zones are congested
        tp = report.get("throughput", {})   # task volume per zone

        # include per-robot metrics so the LLM can reference specific robots
        return (
            f"Robot utilization:\n"
            f"- Fleet average: {util.get('fleet_average_utilization', 'N/A')}%\n"
            f"- Underutilized (>40% idle): {util.get('underutilized_robots', [])}\n"
            f"- Overworked (>85% active): {util.get('overworked_robots', [])}\n"
            f"- Per-robot breakdown:\n{json.dumps(util.get('robot_metrics', {}), indent=2)}\n\n"
            f"Queue data:\n"
            f"- Average queue per zone: {json.dumps(q.get('average_queue_length_per_zone', {}))}\n"
            f"- Congested zones: {q.get('congested_zones', [])}\n"
            f"- Tasks per zone: {json.dumps(tp.get('tasks_per_zone', {}))}\n\n"
            f"Based on this utilization and queue data, suggest specific robot rebalancing moves. "
            f"For each suggestion, state: which robot(s), from where, to where, and expected impact."
        )