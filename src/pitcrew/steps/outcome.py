"""The rules of a broken run (`CONTEXT.md`, Run outcome): each returns the reason in words, or
`None` when its rule does not hold."""

from collections.abc import Iterable

from pitcrew.clients.gitlab import Job
from pitcrew.constants import JobStatus

_FINISHED = frozenset({JobStatus.SUCCESS, JobStatus.FAILED})
_STOPPED = frozenset({JobStatus.FAILED, JobStatus.CANCELED})


def pipeline_broken_reason(jobs: Iterable[Job], test_job: str) -> str | None:
    """The pipeline failed or was canceled before its `test_job` finished: the tests did not
    run, or not to the end. Named by the earliest job that stopped it.

    Args:
        jobs: The jobs of the pipeline.
        test_job: The name of the job that runs the tests.
    """
    jobs = list(jobs)
    if any(job.name == test_job and job.status in _FINISHED for job in jobs):
        return None
    stopped = [job for job in jobs if job.status in _STOPPED and not job.allow_failure]
    if not stopped:
        return None
    first = min(stopped, key=lambda job: job.id)
    return f"pipeline {first.status} at stage {first.stage}"


def results_broken_reason(
    result_count: int,
    expected_count: int,
    failed_count: int,
    broken_below_ratio: float,
    max_failed_ratio: float | None,
) -> str | None:
    """Far fewer results than expected (the tests did not actually run), or too large a share
    of them failed (the Environment is likely down). `max_failed_ratio` is `None` for a Rerun:
    it runs only Failed tests, so a large share of them failing again is no sign of a down
    Environment.

    Args:
        result_count: The results the launch holds.
        expected_count: The test cases the run was meant to run.
        failed_count: The Failed tests among the results.
        broken_below_ratio: The share of `expected_count` below which the run is broken.
        max_failed_ratio: The share of failures above which the run is broken; `None` to
            skip this rule.
    """
    if result_count < broken_below_ratio * expected_count:
        results = "result" if result_count == 1 else "results"
        return f"{result_count} {results} out of ~{expected_count} expected"
    if (
        max_failed_ratio is not None
        and result_count
        and failed_count / result_count > max_failed_ratio
    ):
        return (
            "too many failures, likely an environment problem: "
            f"{failed_count} of {result_count} results failed"
        )
    return None
