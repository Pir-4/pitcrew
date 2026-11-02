"""The one place that calls the Claude Agent SDK. The Agent depends on `AgentRunner`, so the
tests replace the SDK, and with it Claude Code and the model, by a fake."""

import warnings
from collections.abc import AsyncGenerator
from contextlib import aclosing
from typing import Protocol, cast

from claude_agent_sdk import (
    CanUseToolShadowedWarning,
    ClaudeAgentOptions,
    Message,
    query,
)

# The task's tools are approved by `allowed_tools` on purpose; `can_use_tool` is there for
# whatever else reaches it, so the SDK's warning that it is not asked for them is noise. This
# module is the only caller of the SDK.
warnings.filterwarnings("ignore", category=CanUseToolShadowedWarning)


class AgentRunner(Protocol):
    def __call__(
        self, prompt: str, options: ClaudeAgentOptions
    ) -> AsyncGenerator[Message]:
        """Runs Claude Code with `options` on `prompt`: its messages, up to its result.
        Closing the stream before the end stops Claude Code's process."""
        ...


async def run_with_sdk(
    prompt: str, options: ClaudeAgentOptions
) -> AsyncGenerator[Message]:
    """Streams the Agent's messages through `query`, closed with the stream.

    Args:
        prompt: What the Agent is asked.
        options: Everything else Claude Code runs with.
    """
    # An async generator, annotated as an iterator: its `aclose` stops Claude Code.
    stream = cast(AsyncGenerator[Message], query(prompt=prompt, options=options))
    async with aclosing(stream) as messages:
        async for message in messages:
            yield message
