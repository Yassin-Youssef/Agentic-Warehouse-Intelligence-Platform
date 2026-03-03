# =============================================================================
# BOTTLENECK DIAGNOSIS AGENT
# Explains WHY congestion happens, not just WHERE.
# Feeds queue metrics and throughput data to the LLM and asks it
# to identify root causes behind congestion patterns.
#
# For example, the analysis might show A3 has the highest average
# queue. This agent would explain: "A3 receives 4 tasks/min (double
# the warehouse average), but only 2 robots are assigned there,
# creating a persistent supply-demand imbalance."
#
# The LLM connects the dots between high arrival rates, queue growth,
# and zone performance — things the deterministic layer can measure
# but can't explain in natural language.
# =============================================================================

import json  # used to format dicts nicely in the prompt
from agents.base_agent import BaseAgent

class BottleneckDiagnosisAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            name="Bottleneck Diagnosis Agent",
            description="Identifies root causes of warehouse congestion",
            system_prompt=(
                "You are a warehouse bottleneck specialist. You receive queue metrics "
                "and throughput data from a warehouse simulation. Identify root causes of "
                "congestion. RULES: Reference specific zone names, queue growth rates, and "
                "peak values from the data. Do NOT invent data. Explain WHY congestion "
                "occurs, not just WHERE."
            ),
        )

    def _build_prompt(self, report: dict) -> str:
        """Extract queue and throughput metrics — the two things that
        tell you where congestion is happening and how bad it is."""
        q = report.get("queue", {})      # queue analyzer results
        tp = report.get("throughput", {}) # throughput analyzer results

        # json.dumps converts dicts to readable strings for the prompt
        return (
            f"Queue metrics:\n"
            f"- Average queue per zone: {json.dumps(q.get('average_queue_length_per_zone', {}))}\n"
            f"- Peak queue per zone: {json.dumps(q.get('peak_queue_length_per_zone', {}))}\n"
            f"- Queue growth rates (items/sec): {json.dumps(q.get('queue_growth_rate_per_zone', {}))}\n"
            f"- Congested zones (growth > 0.0003): {q.get('congested_zones', [])}\n"
            f"- Congestion events (queue > 8 for 5+ min): {q.get('congestion_events', 0)}\n\n"
            f"Throughput context:\n"
            f"- Tasks completed per zone: {json.dumps(tp.get('tasks_per_zone', {}))}\n"
            f"- Highest performing zone: {tp.get('highest_performing_zone', 'N/A')}\n"
            f"- Lowest performing zone: {tp.get('lowest_performing_zone', 'N/A')}\n\n"
            f"Analyze these queue metrics and identify the root causes of any bottlenecks. "
            f"For each bottleneck, state: the zone, severity, likely cause, and supporting evidence."
        )