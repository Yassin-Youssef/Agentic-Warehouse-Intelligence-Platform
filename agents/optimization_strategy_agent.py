# =============================================================================
# OPTIMIZATION STRATEGY AGENT
# The "big picture" agent — gets the ENTIRE analysis report and proposes
# 3-5 ranked strategies to improve warehouse operations.
#
# This is the most important agent. Its output is what you'd present
# to management as actionable recommendations. Each strategy includes:
# - What to change
# - Expected impact (with numbers from the report)
# - Implementation priority (high/medium/low)
# - Tradeoffs (what you'd give up)
#
# Example output:
# "Strategy 1: Replace robots 8, 9, 10 (HIGH PRIORITY)
#  These three robots account for 81 of 149 failures (54%).
#  Failure cost alone is $4,050. Replacing them would reduce
#  total inefficiency cost by approximately 44%."
# =============================================================================

import json
from agents.base_agent import BaseAgent

class OptimizationStrategyAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            name="Optimization Strategy Agent",
            description="Proposes ranked operational optimization strategies",
            system_prompt=(
                "You are a senior warehouse operations engineer. You receive a complete "
                "operational analysis. Propose 3-5 concrete optimization strategies. RULES: "
                "For each strategy state: what to change, expected impact (reference the "
                "numbers), implementation priority (high/medium/low), and tradeoffs. "
                "Rank strategies by impact. Be realistic — these should be actionable."
            ),
        )

    def _build_prompt(self, report: dict) -> str:
        """This agent gets EVERYTHING — all 5 analysis sections.
        It needs the complete picture to propose meaningful strategies."""
        tp = report.get("throughput", {})      # how fast tasks are being completed
        q = report.get("queue", {})            # where congestion is happening
        util = report.get("utilization", {})   # which robots are idle/busy
        dt = report.get("downtime", {})        # which robots keep breaking
        cost = report.get("cost", {})          # dollar cost of all the waste

        return (
            f"Complete warehouse analysis:\n\n"
            f"THROUGHPUT:\n"
            f"- Completed: {tp.get('total_tasks_completed', 'N/A')} tasks\n"
            f"- Average: {tp.get('average_throughput_per_hour', 'N/A')} tasks/hour\n"
            f"- Trend: {tp.get('throughput_trend', 'N/A')} (slope: {tp.get('throughput_trend_slope', 'N/A')})\n"
            f"- Per zone: {json.dumps(tp.get('tasks_per_zone', {}))}\n\n"
            f"QUEUES:\n"
            f"- Averages: {json.dumps(q.get('average_queue_length_per_zone', {}))}\n"
            f"- Growth rates: {json.dumps(q.get('queue_growth_rate_per_zone', {}))}\n"
            f"- Congested: {q.get('congested_zones', [])}\n\n"
            f"UTILIZATION:\n"
            f"- Fleet average: {util.get('fleet_average_utilization', 'N/A')}%\n"
            f"- Underutilized: {util.get('underutilized_robots', [])}\n"
            f"- Overworked: {util.get('overworked_robots', [])}\n"
            f"- Per-robot:\n{json.dumps(util.get('robot_metrics', {}), indent=2)}\n\n"
            f"DOWNTIME:\n"
            f"- Total failures: {dt.get('total_failures', 'N/A')}\n"
            f"- Failure rate: {dt.get('fleet_failure_rate', 'N/A')} per robot-hour\n"
            f"- Clusters: {dt.get('failure_clusters', 0)}\n"
            f"- Least reliable: Robot {dt.get('least_reliable_robot', 'N/A')}\n"
            f"- Robot details:\n{json.dumps(dt.get('robot_downtimes', {}), indent=2)}\n\n"
            f"COST:\n"
            f"- Total waste: ${cost.get('total_inefficiency_cost', 'N/A')}\n"
            f"- Breakdown:\n{json.dumps(cost.get('cost_breakdown', {}), indent=2)}\n\n"
            f"Based on this complete analysis, propose 3-5 ranked optimization strategies. "
            f"For each: what to change, expected impact, priority, and tradeoffs."
        )