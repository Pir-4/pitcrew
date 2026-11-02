import pytest

from pitcrew.clients.gitlab import Job
from pitcrew.steps.outcome import pipeline_broken_reason, results_broken_reason


@pytest.mark.parametrize(
    ("jobs", "reason"),
    [
        pytest.param(
            # Pipeline 476973.
            [
                Job(3068130, "pages", "publish_pages", "skipped", False),
                Job(3068129, "test", "test", "canceled", False),
                Job(3068128, "security:secret_detection", "security", "success", True),
            ],
            "pipeline canceled at stage test",
            id="test job canceled while it ran",
        ),
        pytest.param(
            [
                Job(3044493, "test", "test", "skipped", False),
                Job(3044490, "build", "build", "failed", False),
            ],
            "pipeline failed at stage build",
            id="failed before the test job",
        ),
        pytest.param(
            [
                Job(3044494, "pages", "publish_pages", "canceled", False),
                Job(3044493, "test", "test", "skipped", False),
                Job(3044490, "build", "build", "failed", False),
            ],
            "pipeline failed at stage build",
            id="named by the earliest job that stopped it",
        ),
        pytest.param(
            # Pipeline 475379.
            [
                Job(3058544, "pages", "publish_pages", "success", False),
                Job(3058543, "test", "test", "success", False),
                Job(3058542, "security:secret_detection", "security", "success", True),
                Job(
                    3058541,
                    "security:dependency_vulnerabilities",
                    "security",
                    "failed",
                    True,
                ),
            ],
            None,
            id="test job passed",
        ),
        pytest.param(
            [Job(3058543, "test", "test", "failed", False)],
            None,
            id="test job failed: the tests ran to the end",
        ),
        pytest.param(
            [
                Job(3058544, "pages", "publish_pages", "failed", False),
                Job(3058543, "test", "test", "success", False),
            ],
            None,
            id="a job after the finished test job failed",
        ),
        pytest.param(
            [
                Job(3058543, "test", "test", "running", False),
                Job(
                    3058541,
                    "security:dependency_vulnerabilities",
                    "security",
                    "failed",
                    True,
                ),
            ],
            None,
            id="a job with allow_failure failed before the test job",
        ),
    ],
)
def test_pipeline_stopped_before_its_test_job_finished_is_broken(
    jobs: list[Job], reason: str | None
) -> None:
    broken = pipeline_broken_reason(jobs, test_job="test")

    assert broken == reason


@pytest.mark.parametrize(
    ("result_count", "expected_count", "failed_count", "max_failed_ratio", "reason"),
    [
        pytest.param(
            # Launch 271942: only the data preparation, against nightly test plan 1387.
            1, 1675, 0, 0.5,
            "1 result out of ~1675 expected",
            id="one result of a Nightly run",
        ),
        pytest.param(
            # Rerun launch 279328 of the 223 test cases of launch 276357.
            2, 223, 2, None,
            "2 results out of ~223 expected",
            id="too few results of a Rerun",
        ),
        pytest.param(
            1000, 2000, 0, 0.5,
            None,
            id="exactly half the expected results",
        ),
        pytest.param(
            # Launch 276357 against nightly test plan 1387.
            6292, 1675, 685, 0.1,
            "too many failures, likely an environment problem: 685 of 6292 results failed",
            id="share of failures above the threshold",
        ),
        pytest.param(
            6292, 1675, 685, 0.5,
            None,
            id="share of failures below the threshold",
        ),
        pytest.param(
            100, 100, 50, 0.5,
            None,
            id="share of failures exactly at the threshold",
        ),
        pytest.param(
            2, 2, 2, None,
            None,
            id="every test failing again on a Rerun",
        ),
        pytest.param(
            0, 0, 0, 0.5,
            None,
            id="no results of an empty test plan",
        ),
    ],
)  # fmt: skip
def test_run_with_too_few_results_or_too_many_failures_is_broken(
    result_count: int,
    expected_count: int,
    failed_count: int,
    max_failed_ratio: float | None,
    reason: str | None,
) -> None:
    broken = results_broken_reason(
        result_count=result_count,
        expected_count=expected_count,
        failed_count=failed_count,
        broken_below_ratio=0.5,
        max_failed_ratio=max_failed_ratio,
    )

    assert broken == reason
