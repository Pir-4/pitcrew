"""Judging a Run (`CONTEXT.md`, Run outcome): the order of the checks and the rules each kind
of Run is judged by, written once for every Step."""

from dataclasses import dataclass

from pitcrew.clients.testops import TestResult
from pitcrew.config.team import TeamConfig
from pitcrew.constants import FAILED_STATUSES
from pitcrew.db.models.run import Run, RunKind, RunOutcome, RunVerdict
from pitcrew.log import get_logger
from pitcrew.steps.dependencies import StepDependencies
from pitcrew.steps.outcome import pipeline_broken_reason, results_broken_reason

logger = get_logger(__name__)


@dataclass(frozen=True)
class Judgement:
    """What judging a Run found.

    Attributes:
        outcome: The Run outcome.
        reason: Why the Run is broken, in words; `None` unless it is.
        failed_tests: The Failed tests of the Run's launch; `None` when they were not read
            (a broken pipeline's never are).
        expected_test_count: The Run's expected size the results were checked against; when
            they were not, the one the Run already holds.
    """

    outcome: RunOutcome
    reason: str | None
    failed_tests: list[TestResult] | None
    expected_test_count: int | None

    @property
    def failed_test_count(self) -> int | None:
        """How many Failed tests the Run has; `None` when they were not read."""
        return None if self.failed_tests is None else len(self.failed_tests)

    @property
    def verdict(self) -> RunVerdict:
        """What of the judgement is recorded on the Run (`RunChain.record_judgement`)."""
        return RunVerdict(
            self.outcome, self.reason, self.failed_test_count, self.expected_test_count
        )


def judge_run(run: Run, team_config: TeamConfig, deps: StepDependencies) -> Judgement:
    """Judges a finished Run: its pipeline jobs first; only when the pipeline is not broken
    are its Failed tests read, then its results checked against its expected size. The Run's
    kind decides the rules: a Nightly run is expected to run the Team's nightly test plan and
    is broken by too large a share of Failed tests; a Rerun is expected to run the test cases
    stored on it (`expected_test_count`), and the share does not apply, since it runs only
    Failed tests. Reads GitLab and TestOps; records nothing.

    Args:
        run: The Run to judge; its launch is known.
        team_config: The config of the Run chain's Team.
        deps: The clients to read the pipeline and the launch with.
    """
    jobs = deps.gitlab.pipeline_jobs(team_config.gitlab.project_path, run.pipeline_id)
    reason = pipeline_broken_reason(jobs, team_config.gitlab.test_job)
    logger.info("Pipeline checked", pipeline_id=run.pipeline_id, broken_reason=reason)
    if reason is None:
        judgement = _judge_results(run, team_config, deps)
    else:
        judgement = Judgement(RunOutcome.BROKEN, reason, None, run.expected_test_count)
    logger.info(
        "Run outcome decided",
        run_kind=run.kind,
        outcome=judgement.outcome,
        reason=judgement.reason,
    )
    return judgement


def _judge_results(
    run: Run, team_config: TeamConfig, deps: StepDependencies
) -> Judgement:
    """Reads the Failed tests and the result count of the Run's launch and judges them
    against its expected size, by the rules of its kind."""
    assert run.launch_id is not None, "known once the Run has finished"
    project_id = team_config.allure.project_id
    failed_tests = deps.testops.test_results(project_id, run.launch_id, FAILED_STATUSES)
    if run.kind == RunKind.NIGHTLY:
        expected_count = deps.testops.test_plan_test_case_count(
            team_config.allure.nightly_test_plan_id
        )
        max_failed_ratio = team_config.rerun.max_failed_ratio
    else:
        assert run.expected_test_count is not None, "stored when the Rerun was started"
        expected_count = run.expected_test_count
        max_failed_ratio = None
    result_count = deps.testops.result_count(project_id, run.launch_id)
    reason = results_broken_reason(
        result_count=result_count,
        expected_count=expected_count,
        failed_count=len(failed_tests),
        broken_below_ratio=team_config.broken_below_ratio,
        max_failed_ratio=max_failed_ratio,
    )
    logger.info(
        "Results checked",
        launch_id=run.launch_id,
        result_count=result_count,
        expected_test_count=expected_count,
        failed_test_count=len(failed_tests),
        broken_reason=reason,
    )
    if reason is not None:
        outcome = RunOutcome.BROKEN
    elif failed_tests:
        outcome = RunOutcome.WITH_FAILURES
    else:
        outcome = RunOutcome.GREEN
    return Judgement(outcome, reason, failed_tests, expected_count)
