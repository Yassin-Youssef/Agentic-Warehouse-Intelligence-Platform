# =============================================================================
# AGENT CONFIG
# Stores default settings for the LLM agents in Phase 3.
# Every agent uses these defaults when calling the LLM.
# The model string is for OpenRouter — it routes our request to
# Claude Sonnet through their gateway. Same model quality as
# calling Anthropic directly, just a different URL.
#
# MAX_TOKENS controls how long the LLM's response can be.
# 1500 tokens is roughly 1000-1200 words — enough for a
# detailed analysis without being wasteful.
# =============================================================================

# OpenRouter model string, tells OpenRouter to route to Claude Sonnet
DEFAULT_MODEL = "anthropic/claude-3.5-sonnet"
# max response length from the LLM (roughly 1000-1200 words)
MAX_TOKENS = 1500