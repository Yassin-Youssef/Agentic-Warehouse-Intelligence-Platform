# =============================================================================
# RISK FORECAST AGENT
# Predicts what goes wrong next if nothing changes.
# Uses trend data (queue growth rates, throughput slope, failure rates)
# to forecast problems 2-4 hours into the future.
#
# For example: "Robot 9's MTBF of 4.57 minutes means it fails roughly
# every 5 minutes. Over the next 4 hours, expect ~48 additional failures
# from this robot alone, costing approximately $2,400."
#
# Each prediction gets a risk level: high, medium, or low.
# =============================================================================

import json
from agents.base_agent import BaseAgent

class RiskForecastAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            name="Risk Forecast Agent",
            description="Predicts future operational risks from current trends",
            system_prompt=(
                "You are a risk analysis specialist for warehouse operations. Based on "
                "current trends, predict what will happen if conditions continue for the "
                "next 2-4 hours. RULES: Be specific about which zones or robots are at risk. "
                "Use the trend data (queue growth rates, throughput slope, failure rates) to "
                "justify predictions. Assign risk levels: high, medium, or low."
            ),
        )

    def _build_prompt(self, report: dict) -> str:
        """Pull trend data — the things that tell you where things are heading."""
        q = report.get("queue", {})   # queue growth rates
        tp = report.get("throughput", {}) # throughput trend slope
        dt = report.get("downtime", {}) # failure rates and clusters

        # include per-robot downtime details so the LLM can flag specific robots
        return (
            f"Current trends:\n"
            f"- Queue growth rates (items/sec): {json.dumps(q.get('queue_growth_rate_per_zone', {}))}\n"
            f"- Congested zones: {q.get('congested_zones', [])}\n"
            f"- Throughput trend: {tp.get('throughput_trend', 'N/A')} "
            f"(slope: {tp.get('throughput_trend_slope', 'N/A')})\n"
            f"- Hourly throughput: {tp.get('tasks_per_hour', [])}\n\n"
            f"Failure data:\n"
            f"- Fleet failure rate: {dt.get('fleet_failure_rate', 'N/A')} failures/robot-hour\n"
            f"- Failure clusters: {dt.get('failure_clusters', 0)}\n"
            f"- Least reliable robot: Robot {dt.get('least_reliable_robot', 'N/A')}\n"
            f"- Robot downtimes:\n{json.dumps(dt.get('robot_downtimes', {}), indent=2)}\n\n"
            f"Based on these trends, forecast operational risks for the next 2-4 hours. "
            f"For each risk: what could happen, which zone/robot, likelihood, and impact."
        )