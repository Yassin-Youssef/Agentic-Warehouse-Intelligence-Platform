# =============================================================================
# BASE AGENT
# Abstract base class that all 5 agents inherit from.
# This defines the standard workflow every agent follows:
#
#   1. _build_prompt() — the subclass extracts relevant metrics from the
#      Phase 2 analysis report and formats them into a text prompt
#   2. call_llm() — sends the prompt to Claude via OpenRouter
#   3. _parse_response() — takes the LLM's raw text and packages it into
#      an AgentOutput dataclass
#
# Each of the 5 agents only overrides _build_prompt() — they each pull
# different metrics from the report and ask different questions. But
# the LLM call and response parsing is identical for all agents.
#
# This is the inheritance pattern:
#   BaseAgent (this file)
#     ├── PerformanceSummaryAgent
#     ├── BottleneckDiagnosisAgent
#     ├── ResourceAllocationAgent
#     ├── RiskForecastAgent
#     └── OptimizationStrategyAgent
# =============================================================================

from datetime import datetime
from schemas.agent_schema import AgentOutput
from tools.llm_client import call_llm

class BaseAgent:
    def __init__(self, name: str, description: str, system_prompt: str) -> None:
        self.name = name                    # e.g. "Risk Forecast Agent"
        self.description = description      # short description of what it does
        self.system_prompt = system_prompt  # tells the LLM what role to play

    def run(self, analysis_report: dict) -> AgentOutput:
        """Main entry point. Build prompt -> call LLM -> parse response.
        This is what main_phase3.py calls for each agent."""
        # step 1: subclass builds a prompt from the analysis report
        user_prompt = self._build_prompt(analysis_report)
        # step 2: send system_prompt + user_prompt to Claude via OpenRouter
        raw_response = call_llm(self.system_prompt, user_prompt)
        # step 3: package the raw text into a structured AgentOutput
        return self._parse_response(raw_response, user_prompt)

    def _build_prompt(self, analysis_report: dict) -> str:
        """Subclasses MUST override this.
        Extracts relevant metrics from the report and formats them into text."""
        raise NotImplementedError("Each agent must implement _build_prompt()")

    def _parse_response(self, raw_response: str, user_prompt: str) -> AgentOutput:
        """Take the LLM's raw text and package it into an AgentOutput.
        Also tries to extract recommendation lines from the text."""
        # split the response into lines and look for recommendations
        # recommendations usually start with "- " or "1. ", "2. " etc
        lines = raw_response.strip().split("\n")
        recommendations = []
        for line in lines:
            stripped = line.strip()
            # check if line starts with a bullet point
            if stripped.startswith("-"):
                clean = stripped.lstrip("- ").strip()
                if clean:
                    recommendations.append(clean)
            # check if line starts with a number like "1." or "2."
            elif len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in ".)" :
                clean = stripped[2:].strip().lstrip(". ").strip()
                if clean:
                    recommendations.append(clean)

        return AgentOutput(
            agent_name=self.name,
            timestamp=datetime.now().isoformat(),  # when this agent ran
            summary=raw_response.strip(),  # the full LLM response
            recommendations=recommendations, # extracted bullet points
            confidence="high", # default confidence level
            raw_input_preview=user_prompt[:200], # first 200 chars for debugging
        )