# =============================================================================
# PERFORMANCE SUMMARY AGENT
# The "executive summary" agent — produces an overall health briefing.
# Pulls key metrics from ALL sections of the analysis report (throughput,
# utilization, downtime, cost) and asks the LLM to summarize the
# warehouse's operational health in plain English.
#
# This is what management reads first. It answers: "How is the
# warehouse doing overall? What are the 3-5 most important things?"
#
# The LLM does NOT compute anything — it only interprets the numbers
# that Phase 2 already calculated. This is "Rules decide -> LLM explains."
# =============================================================================

from agents.base_agent import BaseAgent

class PerformanceSummaryAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            name="Performance Summary Agent",
            description="Generates an overall warehouse performance summary",
            # system_prompt tells the LLM what role to play
            # it explicitly says "do NOT compute" to prevent hallucination
            system_prompt=(
                "You are a warehouse operations analyst. You receive pre-computed "
                "operational metrics from a warehouse simulation. Your job is to produce "
                "a clear, structured performance summary. RULES: Do NOT compute any numbers "
                "— only interpret the metrics provided. Reference actual values from the data. "
                "Be concise and specific. Write like a senior engineer briefing management."
            ),
        )

    def _build_prompt(self, report: dict) -> str:
        """Pull key metrics from all 5 analysis sections into one prompt.
        The LLM gets a complete picture and writes the summary."""
        # extract each section from the analysis report
        tp = report.get("throughput", {})  # throughput analyzer results
        util = report.get("utilization", {}) # utilization analyzer results
        dt = report.get("downtime", {}) # downtime analyzer results
        cost = report.get("cost", {})   # cost estimator results
        cb = cost.get("cost_breakdown", {})    # idle/delay/failure/queue percentages

        # format all key metrics into a clear text block for the LLM
        return (
            f"Here are the warehouse performance metrics for the past 4-hour period:\n"
            f"- Total tasks completed: {tp.get('total_tasks_completed', 'N/A')}\n"
            f"- Average throughput: {tp.get('average_throughput_per_hour', 'N/A')} tasks/hour\n"
            f"- Throughput trend: {tp.get('throughput_trend', 'N/A')} "
            f"(slope: {tp.get('throughput_trend_slope', 'N/A')})\n"
            f"- Fleet utilization: {util.get('fleet_average_utilization', 'N/A')}%\n"
            f"- Total failures: {dt.get('total_failures', 'N/A')}\n"
            f"- Fleet failure rate: {dt.get('fleet_failure_rate', 'N/A')} failures/robot-hour\n"
            f"- Failure clusters: {dt.get('failure_clusters', 'N/A')}\n"
            f"- Total inefficiency cost: ${cost.get('total_inefficiency_cost', 'N/A')}\n"
            f"- Cost breakdown: idle={cb.get('idle', {}).get('percentage', 'N/A')}%, "
            f"delay={cb.get('delay', {}).get('percentage', 'N/A')}%, "
            f"failure={cb.get('failure', {}).get('percentage', 'N/A')}%, "
            f"queue={cb.get('queue', {}).get('percentage', 'N/A')}%\n"
            f"- Best zone: {tp.get('highest_performing_zone', 'N/A')}\n"
            f"- Worst zone: {tp.get('lowest_performing_zone', 'N/A')}\n\n"
            f"Provide a concise performance summary with 3-5 key highlights "
            f"and an overall health assessment."
        )