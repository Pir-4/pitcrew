from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    Message,
    ResultError,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from tests.support.constants import JUNIOR_MODEL

ANSWER = "qa_automation holds the API and UI tests of Gateway."
SESSION_ID = "test-session"


@dataclass(frozen=True)
class AgentCall:
    """What the Agent was asked, and what its working directory held at that moment."""

    prompt: str
    options: ClaudeAgentOptions
    files: list[str]


def result_message(
    subtype: str = "success", result: str | None = ANSWER
) -> ResultMessage:
    return ResultMessage(
        subtype=subtype,
        duration_ms=1200,
        duration_api_ms=1000,
        is_error=subtype != "success",
        num_turns=4,
        session_id=SESSION_ID,
        total_cost_usd=0.02,
        result=result,
    )


def assistant_message(*blocks: TextBlock | ToolUseBlock) -> AssistantMessage:
    return AssistantMessage(
        content=list(blocks), model=JUNIOR_MODEL, session_id=SESSION_ID
    )


class FakeRunner:
    """The Claude Agent SDK: streams `messages` (by default a successful answer `ANSWER`),
    raises `error` instead, or `failure` after them, or with `hang` never ends; keeps the
    calls. Like the SDK, it raises `ResultError` after an error result: Claude Code exits
    non-zero then."""

    def __init__(
        self,
        error: Exception | None = None,
        messages: list[Message] | None = None,
        hang: bool = False,
        failure: Exception | None = None,
    ) -> None:
        self.calls: list[AgentCall] = []
        self.error = error
        self.messages = [result_message()] if messages is None else messages
        self.hang = hang
        self.failure = failure
        # The stream was closed before it ended: Pitcrew stopped the Agent's process.
        self.stopped = False

    async def __call__(
        self, prompt: str, options: ClaudeAgentOptions
    ) -> AsyncGenerator[Message]:
        assert options.cwd is not None
        files = sorted(path.name for path in Path(options.cwd).iterdir())
        self.calls.append(AgentCall(prompt, options, files))
        if self.error is not None:
            raise self.error
        try:
            for message in self.messages:
                yield message
                if isinstance(message, ResultMessage) and message.is_error:
                    raise ResultError(
                        f"Claude Code returned an error result: {message.subtype}",
                        exit_code=1,
                    )
            if self.failure is not None:
                raise self.failure
            if self.hang:
                await anyio.sleep(3600)
        except BaseException:
            self.stopped = True
            raise

    @property
    def options(self) -> ClaudeAgentOptions:
        assert len(self.calls) == 1
        return self.calls[0].options
