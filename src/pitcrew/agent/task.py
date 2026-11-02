"""An Agent task and its result: what the Agent is asked to do and what it answered."""

import uuid
from dataclasses import dataclass, field
from typing import Self

from claude_agent_sdk import ResultMessage

from pitcrew.agent.constants import (
    LIMIT_SUBTYPES,
    READ_ONLY_TOOLS,
    AgentAction,
    AgentOutcome,
)


@dataclass(frozen=True)
class AgentTask:
    """What the Agent is asked to do.

    Attributes:
        action: What the task is for; decides the tier of its model.
        prompt: The question or instruction given to the Agent.
        tools: Claude Code's tools the Agent may use, approved without asking; `Skill` only
            for the test repo's skills.
        id: Names the task in the log lines and the Working copy.
    """

    action: AgentAction
    prompt: str
    tools: tuple[str, ...] = READ_ONLY_TOOLS
    id: str = field(default_factory=lambda: uuid.uuid4().hex)


@dataclass(frozen=True)
class AgentResult:
    """How an Agent task ended and what the Agent answered.

    Attributes:
        outcome: How the task ended.
        answer: The Agent's last answer; empty when it gave none.
        num_turns: `None` when Pitcrew stopped the Agent before its result.
        cost_usd: The SDK's estimate.
        session_id: The Claude Code session, kept on disk under the Claude state directory;
            `None` when the Agent was stopped before it said one.
    """

    outcome: AgentOutcome
    answer: str
    num_turns: int | None
    cost_usd: float | None
    session_id: str | None

    @property
    def succeeded(self) -> bool:
        return self.outcome is AgentOutcome.SUCCESS

    @classmethod
    def from_message(cls, message: ResultMessage) -> Self:
        """The result of the SDK's last message of an Agent task.

        Args:
            message: The SDK's `ResultMessage`.
        """
        if message.subtype == "success" and not message.is_error:
            outcome = AgentOutcome.SUCCESS
        else:
            outcome = LIMIT_SUBTYPES.get(message.subtype, AgentOutcome.ERROR)
        return cls(
            outcome=outcome,
            answer=message.result or "",
            num_turns=message.num_turns,
            cost_usd=message.total_cost_usd,
            session_id=message.session_id,
        )

    @classmethod
    def timed_out(cls, session_id: str | None) -> Self:
        """The result of an Agent task Pitcrew stopped on its timeout.

        Args:
            session_id: The session the Agent had said before it was stopped, if any.
        """
        return cls._unanswered(AgentOutcome.TIMEOUT, session_id)

    @classmethod
    def without_result(cls, session_id: str | None) -> Self:
        """The result of an Agent task whose Claude Code exited without saying how it ended.

        Args:
            session_id: The session the Agent had said before it exited, if any.
        """
        return cls._unanswered(AgentOutcome.ERROR, session_id)

    @classmethod
    def _unanswered(cls, outcome: AgentOutcome, session_id: str | None) -> Self:
        return cls(
            outcome=outcome,
            answer="",
            num_turns=None,
            cost_usd=None,
            session_id=session_id,
        )
