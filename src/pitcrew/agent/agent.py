"""The Agent: Claude Code given an Agent task in a Working copy, run against the internal
LiteLLM and configured by Pitcrew alone (ADR 0005)."""

import json
from collections.abc import AsyncGenerator
from contextlib import aclosing
from pathlib import Path
from typing import Any

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKError,
    Message,
    PermissionResultDeny,
    ResultMessage,
    TextBlock,
    ToolPermissionContext,
    ToolUseBlock,
)

from pitcrew.agent.constants import SKILL_TOOL, SKILLS_DIR, TOOL_INPUT_LOG_LENGTH
from pitcrew.agent.environment import AgentEnvironment
from pitcrew.agent.runner import AgentRunner, run_with_sdk
from pitcrew.agent.task import AgentResult, AgentTask
from pitcrew.config.settings import Settings
from pitcrew.constants import ModelTier
from pitcrew.log import Stopwatch, get_logger, log_scope, masked

logger = get_logger(__name__)


class Agent:
    """Runs Agent tasks, each on the model of the tier its action needs and within the
    limits of the settings."""

    def __init__(self, settings: Settings, runner: AgentRunner = run_with_sdk) -> None:
        """Takes the models, the limits and Claude Code's env from the settings.

        Args:
            settings: The service settings: LiteLLM, the Agent's models and limits, the work
                dir.
            runner: Runs Claude Code; the tests pass a fake in place of the SDK.

        Raises:
            AgentNotConfiguredException: `LITELLM_KEY` is not set.
        """
        self._environment = AgentEnvironment(settings)
        # Pitcrew's flag layer, above the project's: no settings file that slipped into the
        # Working copy can run a hook or send the key elsewhere.
        self._settings = json.dumps(
            {
                "disableAllHooks": True,
                "env": {"ANTHROPIC_BASE_URL": self._environment.base_url},
            }
        )
        self._models = {tier: settings.agent.model(tier) for tier in ModelTier}
        self._max_turns = settings.agent.max_turns
        self._max_budget_usd = settings.agent.max_budget_usd
        self._timeout_seconds = settings.agent.timeout_seconds
        self._runner = runner

    def run(self, task: AgentTask, working_copy: Path) -> AgentResult:
        """Runs the Agent in `working_copy` until it answers, hits a limit or times out.

        The prompt reaches Claude Code with every registered secret masked (ADR 0006);
        test data in it is sent as is, and nothing is put back into the answer.

        Args:
            task: What the Agent is asked to do; its action picks the model.
            working_copy: The checked-out test repo the Agent works in.

        Returns:
            How the task ended, with the Agent's answer when it gave one.
        """
        model = self._models[task.action.model_tier]
        prompt = masked(task.prompt)
        with log_scope(agent_task_id=task.id, agent_action=task.action):
            options = self._options(task, working_copy, model)
            logger.info(
                "Agent task started",
                model=model,
                tools=list(task.tools),
                max_turns=self._max_turns,
                max_budget_usd=self._max_budget_usd,
                timeout_seconds=self._timeout_seconds,
            )
            stopwatch = Stopwatch()
            result = anyio.run(self._run, prompt, options)
            logger.info(
                "Agent task finished",
                outcome=result.outcome,
                num_turns=result.num_turns,
                cost_usd=result.cost_usd,
                session_id=result.session_id,
                model=model,
                duration_ms=stopwatch.ms,
            )
            return result

    async def _run(self, prompt: str, options: ClaudeAgentOptions) -> AgentResult:
        """Reads the Agent's messages until its result. The timeout is an anyio cancel
        scope: the SDK stops Claude Code's process on it, shielded from the cancellation.
        The SDK raises when Claude Code exits non-zero, which it does after an error
        result (a limit hit) too."""
        result = None
        session_id = None
        failure = None
        messages: AsyncGenerator[Message] = self._runner(prompt, options)
        async with aclosing(messages):
            with anyio.move_on_after(self._timeout_seconds) as timeout:
                try:
                    async for message in messages:
                        if isinstance(message, AssistantMessage):
                            session_id = message.session_id or session_id
                            _log_content(message)
                        elif isinstance(message, ResultMessage):
                            result = message
                except ClaudeSDKError as error:
                    failure = error
        # A result read before the timeout or the exit stands: it says how the task ended.
        if result is not None:
            return AgentResult.from_message(result)
        if timeout.cancelled_caught:
            return AgentResult.timed_out(session_id)
        logger.warning(
            "Claude Code ended without a result",
            error=str(failure) if failure is not None else None,
        )
        return AgentResult.without_result(session_id)

    def _options(
        self, task: AgentTask, working_copy: Path, model: str
    ) -> ClaudeAgentOptions:
        """The test repo gives the knowledge, Pitcrew the rights (ADR 0005): the Working copy
        holds none of the repo's Claude Code settings, so `project` loads its CLAUDE.md files
        and skills; the tools, hooks, MCP servers and env are Pitcrew's. The Working copy is
        never marked trusted, so a settings file that slipped into it allows nothing."""
        return ClaudeAgentOptions(
            # Only these tools exist for the Agent, whatever a skill asks for.
            tools=list(task.tools),
            # A bare `Skill` would approve any skill by name; `skills` approves the repo's
            # one by one (`Skill(<name>)`), and `can_use_tool` refuses the rest.
            allowed_tools=[tool for tool in task.tools if tool != SKILL_TOOL],
            can_use_tool=_refuse,
            model=model,
            cwd=working_copy,
            env=self._environment.for_model(model),
            max_turns=self._max_turns,
            max_budget_usd=self._max_budget_usd,
            setting_sources=["project"],
            settings=self._settings,
            # The repo's own skills; the ones bundled with Claude Code stay hidden.
            skills=_repo_skills(working_copy),
            strict_mcp_config=True,
        )


def _repo_skills(working_copy: Path) -> list[str]:
    skills = working_copy / SKILLS_DIR
    if not skills.is_dir():
        return []
    return sorted(path.name for path in skills.iterdir() if path.is_dir())


async def _refuse(
    tool: str, tool_input: dict[str, Any], context: ToolPermissionContext
) -> PermissionResultDeny:
    """What `allowed_tools` does not approve reaches here and is refused: nobody is there
    to ask."""
    logger.warning("Agent tool call refused", tool=tool, tool_input=_short(tool_input))
    return PermissionResultDeny(
        message=f"{tool} is not allowed in this Agent task; use only its tools"
    )


def _log_content(message: AssistantMessage) -> None:
    """The Agent's text and tool calls, at debug: what it is doing, without the transcript."""
    for block in message.content:
        if isinstance(block, TextBlock):
            logger.debug("Agent text", text=block.text)
        elif isinstance(block, ToolUseBlock):
            logger.debug(
                "Agent tool call", tool=block.name, tool_input=_short(block.input)
            )


def _short(tool_input: dict[str, Any]) -> str:
    """Masked before it is cut, so that no part of a secret is left to mask."""
    text = masked(json.dumps(tool_input, ensure_ascii=False))
    if len(text) <= TOOL_INPUT_LOG_LENGTH:
        return text
    return text[:TOOL_INPUT_LOG_LENGTH] + "…"
