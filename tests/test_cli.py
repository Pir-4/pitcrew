import pytest
from claude_agent_sdk import Message, TextBlock

from pitcrew.cli import main
from pitcrew.config.settings import get_settings
from tests.support.agent import ANSWER, FakeRunner, assistant_message, result_message
from tests.support.git import Origin
from tests.support.logs import Logs


def test_smoke_prints_the_agents_answer(
    agent_env: dict[str, str],
    origin: Origin,
    logs: Logs,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # `logs` takes the log lines off stdout, as the console script sends them to stderr.
    runner = FakeRunner()

    exit_code = main(["agent-smoke"], runner=runner)

    assert exit_code == 0
    assert capsys.readouterr().out == f"{ANSWER}\n"
    assert "describe" in runner.calls[0].prompt.lower()


def test_smoke_asks_the_given_prompt(agent_env: dict[str, str], origin: Origin) -> None:
    runner = FakeRunner()

    main(["agent-smoke", "--prompt", "Which skills does the repo have?"], runner=runner)

    assert runner.calls[0].prompt == "Which skills does the repo have?"


def test_smoke_works_in_a_working_copy_of_the_rerun_branch(
    agent_env: dict[str, str], origin: Origin
) -> None:
    # `rerun.branch` of the repo's config/base.yaml is `master`.
    origin.commit("feature", "feature.md")
    runner = FakeRunner()

    main(["agent-smoke"], runner=runner)

    assert runner.calls[0].files == [".claude", ".git", "README.md"]


def test_smoke_works_in_a_working_copy_of_the_requested_ref(
    agent_env: dict[str, str], origin: Origin
) -> None:
    origin.commit("feature", "feature.md")
    runner = FakeRunner()

    main(["agent-smoke", "--ref", "feature"], runner=runner)

    assert "feature.md" in runner.calls[0].files


@pytest.mark.parametrize(
    ("messages", "hang", "named"),
    [
        pytest.param(
            [result_message("error_max_turns", result=None)],
            False,
            "AGENT_MAX_TURNS",
            id="turn limit",
        ),
        pytest.param(
            [result_message("error_max_budget_usd", result=None)],
            False,
            "AGENT_MAX_BUDGET_USD",
            id="budget limit",
        ),
        pytest.param(
            [assistant_message(TextBlock("Reading the tests"))],
            True,
            "AGENT_TIMEOUT_SECONDS",
            id="timeout",
        ),
        pytest.param(
            [result_message("error_during_execution", result=None)],
            False,
            "error",
            id="error",
        ),
    ],
)
def test_smoke_without_an_answer_fails_naming_why(
    agent_env: dict[str, str],
    origin: Origin,
    capsys: pytest.CaptureFixture[str],
    messages: list[Message],
    hang: bool,
    named: str,
) -> None:
    runner = FakeRunner(messages=messages, hang=hang)

    exit_code = main(["agent-smoke"], runner=runner)

    assert exit_code != 0
    assert named in capsys.readouterr().err


def test_smoke_without_litellm_key_fails_before_the_agent(
    agent_env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("LITELLM_KEY")
    get_settings.cache_clear()
    runner = FakeRunner()

    exit_code = main(["agent-smoke"], runner=runner)

    assert exit_code != 0
    assert "LITELLM_KEY" in capsys.readouterr().err
    assert runner.calls == []
