"""`pitcrew`: the service's commands for a developer, beside its HTTP API.

`pitcrew agent-smoke [--team] [--ref] [--prompt]` asks the Agent about the test repo in a
Working copy and prints its answer: the check that the Agent works from the service.
"""

import argparse
import sys
from collections.abc import Sequence

from pitcrew.agent import Agent, AgentAction, AgentOutcome, AgentTask
from pitcrew.agent.exceptions import AgentNotConfiguredException
from pitcrew.agent.runner import AgentRunner, run_with_sdk
from pitcrew.agent.working_copy import WorkingCopies
from pitcrew.config.settings import AgentSettings, LogSettings, get_settings
from pitcrew.config.team import TeamConfigs, UnknownTeamException
from pitcrew.log import configure_logging, get_logger

logger = get_logger(__name__)

DEFAULT_PROMPT = (
    "Describe this repository: its purpose, its layout, how its tests are run and what "
    "agent tooling (AGENTS.md / CLAUDE.md, skills, agents, commands) it has."
)


def main(argv: Sequence[str] | None = None, runner: AgentRunner = run_with_sdk) -> int:
    """Runs a command.

    Args:
        argv: The command line without the program name; `sys.argv` when `None`.
        runner: Runs Claude Code; the tests pass a fake in place of the SDK.

    Returns:
        The exit code.
    """
    parser = argparse.ArgumentParser(prog="pitcrew")
    commands = parser.add_subparsers(dest="command", required=True)
    smoke = commands.add_parser(
        "agent-smoke", help="Ask the Agent about the test repo and print its answer"
    )
    smoke.add_argument("--team", default="Gateway", help="Team config of the test repo")
    smoke.add_argument(
        "--ref", help="Branch, tag or commit to ask about; default: the Rerun branch"
    )
    smoke.add_argument("--prompt", default=DEFAULT_PROMPT, help="What to ask")
    args = parser.parse_args(argv)
    return _agent_smoke(args.team, args.ref, args.prompt, runner)


def _agent_smoke(team: str, ref: str | None, prompt: str, runner: AgentRunner) -> int:
    settings = get_settings()
    try:
        team_config = TeamConfigs(settings.config_dir).get(team)
    except UnknownTeamException as error:
        print(error, file=sys.stderr)
        return 2
    try:
        agent = Agent(settings, runner)
    except AgentNotConfiguredException as error:
        print(error, file=sys.stderr)
        return 1
    task = AgentTask(AgentAction.SMOKE, prompt)
    working_copies = WorkingCopies(settings, team_config.gitlab.project_path)
    with working_copies.create(
        ref or team_config.rerun.branch, task.action, task.id
    ) as working_copy:
        result = agent.run(task, working_copy)
    if result.answer:
        print(result.answer)
    if result.succeeded:
        return 0
    print(_unfinished(result.outcome, settings.agent), file=sys.stderr)
    return 1


def _unfinished(outcome: AgentOutcome, agent: AgentSettings) -> str:
    """Why the Agent task ended without an answer, naming the limit and its variable."""
    match outcome:
        case AgentOutcome.TURN_LIMIT:
            return (
                f"The Agent hit the turn limit of {agent.max_turns} (AGENT_MAX_TURNS)"
            )
        case AgentOutcome.BUDGET_LIMIT:
            return (
                f"The Agent hit the budget limit of {agent.max_budget_usd} USD "
                "(AGENT_MAX_BUDGET_USD)"
            )
        case AgentOutcome.TIMEOUT:
            return (
                f"The Agent ran out of {agent.timeout_seconds} s "
                "(AGENT_TIMEOUT_SECONDS) and was stopped"
            )
        case _:
            return "The Agent ended with an error; see the log"


def run() -> None:
    """The `pitcrew` console script: logs go to stderr, so stdout holds only the answer; a
    failure nobody handled is logged once, masked, like a failed Step."""
    log_settings = LogSettings()
    configure_logging(
        log_settings.log_format, log_settings.log_level, stream=sys.stderr
    )
    try:
        exit_code = main()
    except Exception:
        logger.exception("Command failed")
        exit_code = 1
    sys.exit(exit_code)
