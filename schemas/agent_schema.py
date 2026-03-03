# =============================================================================
# AGENT SCHEMA
# Defines the output format for every Phase 3 agent.
# When an agent calls the LLM and gets a response back, it packages
# that response into an AgentOutput dataclass. This gives every agent
# the same output shape — consistent and easy to serialize to JSON.
#
# Fields:
# - agent_name: identifies which agent produced this (e.g. "Risk Forecast Agent")
# - timestamp: when the agent ran, in ISO format
# - summary: the full text response from the LLM
# - recommendations: extracted bullet points from the response
# - confidence: how confident the agent is (always "high" for now)
# - raw_input_preview: first 200 chars of the prompt, useful for debugging
#   when an agent gives a weird answer — you can see what it was given
# =============================================================================

from dataclasses import dataclass, field, asdict  # dataclass auto-generates __init__
from typing import Any, Dict, List

@dataclass
class AgentOutput:
    agent_name: str # which agent made this output
    timestamp: str # ISO format: "2026-03-03T15:36:51"
    summary: str # the full text the LLM returned
    recommendations: List[str] = field(default_factory=list)  # bullet points extracted from the text
    confidence: str = "high" # "high", "medium", or "low"
    raw_input_preview: str = ""  # first 200 chars of what was sent to the LLM

    def model_dump(self) -> Dict[str, Any]:
        """Convert to plain dict for JSON serialization."""
        return asdict(self)