"""Constants of the Agent: what an Agent task is for and the tools it gets by default."""

from enum import StrEnum
from pathlib import Path

from pitcrew.constants import ModelTier

SKILL_TOOL = "Skill"

READ_ONLY_TOOLS = ("Read", "Grep", "Glob", SKILL_TOOL)

SKILLS_DIR = Path(".claude") / "skills"

TOOL_INPUT_LOG_LENGTH = 200


class AgentAction(StrEnum):
    """What an Agent task is for; it decides the tier of the model the task gets.

    Attributes:
        SMOKE: `pitcrew agent-smoke`: answer a question about the test repo.
    """

    SMOKE = "smoke"

    @property
    def model_tier(self) -> ModelTier:
        return _MODEL_TIERS[self]


class AgentOutcome(StrEnum):
    """How an Agent task ended.

    Attributes:
        SUCCESS: The Agent answered.
        TURN_LIMIT: The Agent stopped on `AGENT_MAX_TURNS`.
        BUDGET_LIMIT: The Agent stopped on `AGENT_MAX_BUDGET_USD`.
        TIMEOUT: Pitcrew stopped the Agent's process after `AGENT_TIMEOUT_SECONDS`.
        ERROR: Claude Code ended the task with an error of its own, e.g. a failed model call.
    """

    SUCCESS = "success"
    TURN_LIMIT = "turn_limit"
    BUDGET_LIMIT = "budget_limit"
    TIMEOUT = "timeout"
    ERROR = "error"


LIMIT_SUBTYPES = {
    "error_max_turns": AgentOutcome.TURN_LIMIT,
    "error_max_budget_usd": AgentOutcome.BUDGET_LIMIT,
}

_MODEL_TIERS = {
    AgentAction.SMOKE: ModelTier.JUNIOR,
}
