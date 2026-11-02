import json
from pathlib import Path

import anyio
import pytest
from claude_agent_sdk import (
    Message,
    PermissionResultDeny,
    ProcessError,
    TextBlock,
    ToolPermissionContext,
    ToolUseBlock,
)

from pitcrew.agent import Agent, AgentAction, AgentResult, AgentTask
from pitcrew.config.settings import get_settings
from pitcrew.log import mask_secrets
from tests.support.agent import (
    ANSWER,
    SESSION_ID,
    FakeRunner,
    assistant_message,
    result_message,
)
from tests.support.constants import (
    GITLAB_TOKEN,
    JUNIOR_MODEL,
    LITELLM_KEY,
    LITELLM_URL,
    MAX_BUDGET_USD,
    MAX_TURNS,
)
from tests.support.git import SKILL
from tests.support.logs import Logs

READ_ONLY_TOOLS = ["Read", "Grep", "Glob", "Skill"]


@pytest.fixture
def working_copy(tmp_path: Path) -> Path:
    """A Working copy as the Agent finds it: the test repo with one skill, no git needed."""
    working_copy = tmp_path / "working_copy"
    (working_copy / ".claude" / "skills" / SKILL).mkdir(parents=True)
    (working_copy / ".claude" / "skills" / SKILL / "SKILL.md").write_text("A skill\n")
    (working_copy / "README.md").write_text("content\n")
    return working_copy


def run_smoke(
    runner: FakeRunner, working_copy: Path, prompt: str = "Describe it"
) -> AgentResult:
    """An Agent task of the smoke, the action `agent-smoke` runs."""
    agent = Agent(get_settings(), runner)
    return agent.run(AgentTask(AgentAction.SMOKE, prompt), working_copy)


def test_smoke_agent_gets_read_only_tools_and_the_junior_model(
    agent_env: dict[str, str], working_copy: Path
) -> None:
    runner = FakeRunner()

    run_smoke(runner, working_copy, prompt="Fix the tests")

    options = runner.options
    assert options.tools == READ_ONLY_TOOLS
    # `Skill` is approved per repo skill by `skills`, never for any name.
    assert options.allowed_tools == ["Read", "Grep", "Glob"]
    assert options.model == JUNIOR_MODEL
    assert options.cwd == working_copy


def test_agent_gets_the_repos_knowledge_and_pitcrews_rules(
    agent_env: dict[str, str], working_copy: Path
) -> None:
    runner = FakeRunner()

    run_smoke(runner, working_copy)

    options = runner.options
    # The repo's CLAUDE.md files and skills, and none of Claude Code's bundled skills.
    assert options.setting_sources == ["project"]
    assert options.skills == [SKILL]
    # Pitcrew's flag layer, above anything a settings file in the Working copy could say.
    assert options.settings is not None
    settings = json.loads(options.settings)
    assert settings["disableAllHooks"] is True
    assert settings["env"] == {"ANTHROPIC_BASE_URL": LITELLM_URL}
    assert options.strict_mcp_config


def test_tool_outside_the_task_is_refused(
    agent_env: dict[str, str], working_copy: Path, logs: Logs
) -> None:
    runner = FakeRunner()
    run_smoke(runner, working_copy)
    can_use_tool = runner.options.can_use_tool
    assert can_use_tool is not None

    decision = anyio.run(
        can_use_tool, "Bash", {"command": "git push"}, ToolPermissionContext()
    )

    assert isinstance(decision, PermissionResultDeny)
    assert "Bash" in decision.message
    assert "Agent tool call refused" in logs.messages()


def test_working_copy_is_never_marked_trusted(
    agent_env: dict[str, str], working_copy: Path
) -> None:
    # Once trusted, the allow rules of a settings file in the Working copy would apply. Claude
    # Code does not run here: this guards that Pitcrew itself writes no mark.
    runner = FakeRunner()

    run_smoke(runner, working_copy)

    claude_config_dir = Path(runner.options.env["CLAUDE_CONFIG_DIR"])
    assert claude_config_dir.is_dir()
    for path in claude_config_dir.rglob("*"):
        assert not path.is_file() or "hasTrustDialogAccepted" not in path.read_text()


def test_agent_task_gets_the_turn_and_budget_limits(
    agent_env: dict[str, str], working_copy: Path
) -> None:
    runner = FakeRunner()

    run_smoke(runner, working_copy)

    assert runner.options.max_turns == MAX_TURNS
    assert runner.options.max_budget_usd == MAX_BUDGET_USD


# Registered by the test that needs it; a value of its own, so that no other test masks it.
REGISTERED_SECRET = "registered-secret-value"


@pytest.mark.parametrize(
    "secret",
    [
        pytest.param(GITLAB_TOKEN, id="read through Settings"),
        pytest.param(REGISTERED_SECRET, id="registered with mask_secrets"),
    ],
)
def test_secret_in_the_prompt_reaches_claude_code_masked(
    agent_env: dict[str, str], working_copy: Path, logs: Logs, secret: str
) -> None:
    mask_secrets([REGISTERED_SECRET])
    runner = FakeRunner()

    run_smoke(runner, working_copy, prompt=f"Why does token={secret} fail?")

    [call] = runner.calls
    assert call.prompt == "Why does token=*** fail?"
    assert secret not in logs.text


def test_test_data_in_the_prompt_reaches_claude_code_as_is(
    agent_env: dict[str, str], working_copy: Path
) -> None:
    # Stage test data is sent as is (ADR 0006): the fix needs the value a model rejected.
    prompt = (
        "Swap from EQBfAN7LfaUYgXZNw5Wc7GBgkEX2yhuJ5ka95J1JJwXXf4a8 for qa.user@example.com"
        " failed: amount 0.00012345 TON below the minimum"
    )
    runner = FakeRunner()

    run_smoke(runner, working_copy, prompt=prompt)

    [call] = runner.calls
    assert call.prompt == prompt


@pytest.mark.parametrize(
    ("messages", "failure", "outcome", "answer"),
    [
        pytest.param([result_message()], None, "success", ANSWER, id="answered"),
        pytest.param(
            [result_message("error_max_turns", result=None)],
            None,
            "turn_limit",
            "",
            id="turn limit hit",
        ),
        pytest.param(
            [result_message("error_max_budget_usd", result=None)],
            None,
            "budget_limit",
            "",
            id="budget limit hit",
        ),
        pytest.param(
            [result_message("error_during_execution", result=None)],
            None,
            "error",
            "",
            id="error result",
        ),
        pytest.param(
            [assistant_message(TextBlock("Reading the tests"))],
            None,
            "error",
            "",
            id="ended without a result",
        ),
        pytest.param(
            [assistant_message(TextBlock("Reading the tests"))],
            ProcessError("Command failed", exit_code=1),
            "error",
            "",
            id="process failed without a result",
        ),
    ],
)
def test_agent_task_ends_with_the_outcome_of_its_last_message(
    agent_env: dict[str, str],
    working_copy: Path,
    messages: list[Message],
    failure: Exception | None,
    outcome: str,
    answer: str,
) -> None:
    runner = FakeRunner(messages=messages, failure=failure)

    result = run_smoke(runner, working_copy)

    assert (result.outcome, result.answer) == (outcome, answer)


def test_agent_that_outlives_the_timeout_is_stopped(
    agent_env: dict[str, str], working_copy: Path
) -> None:
    runner = FakeRunner(
        messages=[assistant_message(TextBlock("Reading the tests"))], hang=True
    )

    result = run_smoke(runner, working_copy)

    assert runner.stopped
    assert result.outcome == "timeout"
    assert result.session_id == SESSION_ID


def test_result_read_before_the_timeout_stands(
    agent_env: dict[str, str], working_copy: Path
) -> None:
    # Claude Code answered, then its process hung on the way out.
    runner = FakeRunner(hang=True)

    result = run_smoke(runner, working_copy)

    assert runner.stopped
    assert result.outcome == "success"


def test_agent_task_start_and_result_are_logged(
    agent_env: dict[str, str], working_copy: Path, logs: Logs
) -> None:
    run_smoke(FakeRunner(), working_copy)

    started, finished = (
        line
        for line in logs.lines()
        if line["message"] in ("Agent task started", "Agent task finished")
    )
    assert started["model"] == JUNIOR_MODEL
    assert started["agent_action"] == "smoke"
    assert started["agent_task_id"] == finished["agent_task_id"]
    assert finished["level"] == "info"
    assert finished["outcome"] == "success"
    assert finished["num_turns"] == 4
    assert finished["cost_usd"] == 0.02
    assert finished["session_id"] == SESSION_ID


def test_agent_tool_calls_and_text_are_logged_at_debug_masked(
    agent_env: dict[str, str], working_copy: Path, logs: Logs
) -> None:
    runner = FakeRunner(
        messages=[
            assistant_message(
                TextBlock(f"Found the key {LITELLM_KEY} in the env"),
                ToolUseBlock(
                    "tool-1", "Grep", {"pattern": f"token={GITLAB_TOKEN}", "path": "."}
                ),
            ),
            result_message(),
        ]
    )

    run_smoke(runner, working_copy)

    started = next(
        line for line in logs.lines() if line["message"] == "Agent task started"
    )
    text, tool_call = (
        line
        for line in logs.lines(debug=True)
        if line["message"] in ("Agent text", "Agent tool call")
    )
    for line in (text, tool_call):
        assert line["level"] == "debug"
        assert line["agent_task_id"] == started["agent_task_id"]
    assert text["text"] == "Found the key *** in the env"
    assert tool_call["tool"] == "Grep"
    assert "token=***" in tool_call["tool_input"]
    for secret in (LITELLM_KEY, GITLAB_TOKEN):
        assert secret not in logs.text


def test_long_tool_input_is_logged_shortened(
    agent_env: dict[str, str], working_copy: Path, logs: Logs
) -> None:
    runner = FakeRunner(
        messages=[
            assistant_message(
                ToolUseBlock("tool-1", "Read", {"file_path": "a" * 1000})
            ),
            result_message(),
        ]
    )

    run_smoke(runner, working_copy)

    [tool_call] = (
        line for line in logs.lines(debug=True) if line["message"] == "Agent tool call"
    )
    assert len(tool_call["tool_input"]) < 300
