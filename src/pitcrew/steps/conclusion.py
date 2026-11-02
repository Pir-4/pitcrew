"""The Conclusion: Pitcrew's own Slack post about a Run chain (`CONTEXT.md`), built as one
message by a pure function; the `Publisher` posts it."""

from collections.abc import Sequence
from typing import Any

from pitcrew.clients.links import WebLinks
from pitcrew.clients.slack import SlackMessage
from pitcrew.config.team import TeamConfig
from pitcrew.db.models.error_group import ErrorGroup, ErrorGroupTest
from pitcrew.db.models.run import Run, RunKind, RunOutcome
from pitcrew.db.models.run_chain import RunChain

# Opens every Conclusion, so that the channel tells Pitcrew's posts from the pipelines' own.
TAG = "[Pitcrew]"
BROKEN_ICON = ":rotating_light:"
FAILURES_ICON = ":x:"
GREEN_ICON = ":white_check_mark:"

_DIVIDER = {"type": "divider"}
MAX_LISTED_GROUPS = 10
MAX_LISTED_TESTS = 5
RUN_NAMES = {RunKind.NIGHTLY: "Nightly run", RunKind.RERUN: "Rerun"}


def conclusion_message(
    chain: RunChain,
    error_groups: Sequence[ErrorGroup] | None,
    team_config: TeamConfig,
    links: WebLinks,
) -> SlackMessage:
    """The Conclusion of a judged Run chain, in the style of the `qa_automation` summary: the
    header with the outcome icon, a block per Run, then what the Runs came to. Which
    Conclusion it is follows from the Runs' stored outcomes:

    - the Nightly run is broken: why, and that there is no Rerun;
    - the Rerun is broken: why, and that the Nightly run's Failed tests are not confirmed;
    - otherwise the Rerun's result: green, or how many tests still fail with the Error groups
      among them (largest first) one by one, or a line saying there are none; the Failed
      tests no rule recognized are counted with a link to the Rerun launch that holds them.

    Args:
        chain: The Run chain, its last Run judged.
        error_groups: The Error groups of the Rerun, largest first; `None` when the Team does
            not recognize them.
        team_config: The Team's GitLab project and TestOps project, for the links.
        links: The links to pipelines, launches, results and test cases.
    """
    return _ConclusionBuilder(chain, team_config, links).message(error_groups)


class _ConclusionBuilder:
    """The parts of one Run chain's Conclusion, sharing the chain, the Team and the links."""

    def __init__(
        self, chain: RunChain, team_config: TeamConfig, links: WebLinks
    ) -> None:
        self._chain = chain
        self._team_config = team_config
        self._links = links

    def message(self, error_groups: Sequence[ErrorGroup] | None) -> SlackMessage:
        nightly_run = self._chain.nightly_run
        if nightly_run.outcome == RunOutcome.BROKEN:
            return self._broken(
                f"Nightly run is broken, no Rerun: {_escape(_reason(nightly_run))}."
            )
        rerun = self._rerun
        if rerun.outcome == RunOutcome.BROKEN:
            return self._broken(
                f"Rerun is broken: {_escape(_reason(rerun))}. The "
                f"{nightly_run.failed_test_count} Failed tests "
                "of the Nightly run are not confirmed."
            )
        return self._rerun_result(rerun, error_groups)

    def _broken(self, why: str) -> SlackMessage:
        """The Conclusion of a broken Run: the Run blocks, then why it is broken."""
        return self._message(BROKEN_ICON, *self._run_blocks(), _DIVIDER, _section(why))

    def _rerun_result(
        self, rerun: Run, error_groups: Sequence[ErrorGroup] | None
    ) -> SlackMessage:
        failed_count = rerun.failed_test_count
        if not failed_count:
            return self._message(GREEN_ICON, *self._run_blocks())
        launch_url = self._links.launch(self._rerun_launch_id)
        if error_groups is None:
            closing = [
                _section(
                    f"<{launch_url}|{_failed_tests_label(failed_count)} still failing> "
                    "on the Rerun"
                )
            ]
        elif not error_groups:
            closing = [
                _section(
                    f"No Error groups: <{launch_url}|{_failed_tests_label(failed_count)}>, "
                    "cause not determined"
                )
            ]
        else:
            closing = self._error_group_blocks(error_groups)
            ungrouped = failed_count - sum(group.test_count for group in error_groups)
            if ungrouped > 0:
                closing.append(
                    _section(
                        f"<{launch_url}|{ungrouped} more "
                        f"{_plural(ungrouped, 'Failed test')}>, cause not determined"
                    )
                )
        return self._message(
            FAILURES_ICON,
            *self._run_blocks(),
            _DIVIDER,
            *closing,
        )

    def _error_group_blocks(
        self, error_groups: Sequence[ErrorGroup]
    ) -> list[dict[str, Any]]:
        """A block per listed Error group: the model linking a TestOps page with exactly its
        test cases, the count of its tests and, for a small group, its test cases each linking
        its result in the Rerun launch. Then the groups left out, summed up."""
        listed, rest = (
            error_groups[:MAX_LISTED_GROUPS],
            error_groups[MAX_LISTED_GROUPS:],
        )
        blocks = []
        for group in listed:
            test_case_ids = {
                test.test_case_id
                for test in group.tests
                if test.test_case_id is not None
            }
            # Without a test case there is nothing to search for: the Rerun launch holds them.
            cases_url = (
                self._links.test_cases(
                    self._team_config.allure.project_id, test_case_ids
                )
                if test_case_ids
                else self._links.launch(self._rerun_launch_id)
            )
            text = (
                f"<{cases_url}|{_escape(group.key)}> · "
                f"{_failed_tests_label(group.test_count)}"
            )
            if group.test_count <= MAX_LISTED_TESTS:
                text += ": " + ", ".join(map(self._test_link, group.tests))
            blocks.append(_section(text))
        if rest:
            test_count = sum(group.test_count for group in rest)
            blocks.append(
                _section(
                    f"… and {len(rest)} more {_plural(len(rest), 'group')} "
                    f"({test_count} {_plural(test_count, 'test')})"
                )
            )
        return blocks

    def _message(self, icon: str, *blocks: dict[str, Any]) -> SlackMessage:
        chain = self._chain
        title = f"{TAG} {_escape(chain.team)} · {_escape(chain.environment)}"
        # The icon in `text` too, so that a notification tells the outcome.
        return SlackMessage(
            text=f"{icon} {title}",
            blocks=[_section(f"{icon} *{title}*"), _DIVIDER, *blocks],
        )

    def _test_link(self, test: ErrorGroupTest) -> str:
        """The test case of a grouped test, linking its result in the Rerun launch; the test
        by name when TestOps has not linked a test case to it."""
        url = self._links.test_result(self._rerun_launch_id, test.test_result_id)
        label = (
            _escape(test.name) if test.test_case_id is None else f"#{test.test_case_id}"
        )
        return f"<{url}|{label}>"

    def _run_blocks(self) -> list[dict[str, Any]]:
        return [self._run_block(run) for run in self._chain.runs]

    def _run_block(self, run: Run) -> dict[str, Any]:
        """A Run: its Failed tests (none shown when they were not read), its pipeline and its
        launch."""
        assert run.launch_id is not None, "known once the Run is judged"
        pipeline_url = self._links.pipeline(
            self._team_config.gitlab.project_path, run.pipeline_id
        )
        launch_url = self._links.launch(run.launch_id)
        count = (
            f" · {_failed_tests_label(run.failed_test_count)}"
            if run.failed_test_count is not None
            else ""
        )
        return _section(
            f"*{RUN_NAMES[run.kind]}*{count}\n"
            f"<{pipeline_url}|Pipeline {run.pipeline_id}> · "
            f"<{launch_url}|Launch {run.launch_id}>"
        )

    @property
    def _rerun(self) -> Run:
        rerun = self._chain.rerun
        assert rerun is not None, "a Run chain not broken at night concludes its Rerun"
        return rerun

    @property
    def _rerun_launch_id(self) -> int:
        launch_id = self._rerun.launch_id
        assert launch_id is not None, "set by the night_rerun trigger"
        return launch_id


def _reason(run: Run) -> str:
    assert run.outcome_reason is not None, "a broken Run has its reason"
    return run.outcome_reason


def _section(text: str) -> dict[str, Any]:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def _failed_tests_label(count: int) -> str:
    return f"{count} {_plural(count, 'Failed test')}"


def _plural(count: int, noun: str) -> str:
    return noun if count == 1 else f"{noun}s"


def _escape(text: str) -> str:
    """Slack `mrkdwn` reads `&`, `<` and `>` as markup."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
