import shutil
from pathlib import Path

import pytest

from pitcrew.agent.environment import AgentEnvironment
from pitcrew.agent.exceptions import AgentNotConfiguredException
from pitcrew.config.settings import get_settings
from tests.support.constants import JUNIOR_MODEL, LITELLM_KEY, LITELLM_URL


def test_agent_reaches_litellm_with_its_own_claude_state(
    agent_env: dict[str, str], work_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The `PATH` Claude Code inherits, kept clear of the home directory the test looks for.
    git = shutil.which("git")
    assert git is not None
    monkeypatch.setenv("PATH", str(Path(git).parent))

    env = AgentEnvironment(get_settings()).for_model(JUNIOR_MODEL)

    assert env["ANTHROPIC_BASE_URL"] == LITELLM_URL
    assert env["ANTHROPIC_AUTH_TOKEN"] == LITELLM_KEY
    assert env["ANTHROPIC_MODEL"] == JUNIOR_MODEL
    assert Path(env["CLAUDE_CONFIG_DIR"]).is_relative_to(work_dir)
    assert Path(env["HOME"]).is_relative_to(work_dir)
    assert env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"
    assert env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] == "1"
    assert not any(str(Path.home()) in value for value in env.values())


def test_agent_gets_nothing_else_of_the_service_env(
    agent_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "developer-anthropic-key")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    env = AgentEnvironment(get_settings()).for_model(JUNIOR_MODEL)

    for variable in (
        "GITLAB_TOKEN",
        "ALLURE_TOKEN",
        "PITCREW_TRIGGER_TOKEN",
        "SLACK_WEBHOOK_GATEWAY",
        "ANTHROPIC_API_KEY",
    ):
        assert env[variable] == ""
    assert env["PATH"] == "/usr/bin:/bin"


def test_agent_environment_without_litellm_key_fails(
    agent_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("LITELLM_KEY")
    get_settings.cache_clear()

    with pytest.raises(AgentNotConfiguredException, match="LITELLM_KEY"):
        AgentEnvironment(get_settings())
