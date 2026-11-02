import httpx2 as httpx

from tests.data import conclusions
from tests.support.constants import (
    GITLAB_TOKEN,
    GITLAB_URL,
    QA_AUTOMATION,
    SLACK_WEBHOOK,
    SLACK_WEBHOOK_VARIABLE,
)
from tests.support.fakes import CreatedPipeline, FakeGitLab, FakeSlack, FakeTestOps
from tests.support.logs import Logs
from tests.support.run_chain import Pitcrew, StartPitcrew
from tests.support.scenarios import LoadScenario
from tests.support.slack_post import post_text


def test_night_run_is_answered_with_the_trace_id_of_its_run_chain(
    pitcrew: Pitcrew, load_scenario: LoadScenario
) -> None:
    night = load_scenario("night_with_failures")

    answer = pitcrew.trigger_night_run(night)

    assert answer.status_code == 202
    assert set(answer.body) == {"trace_id"}
    assert pitcrew.run_chain(answer.trace_id)["trace_id"] == answer.trace_id


def test_green_night_run_ends_the_run_chain(
    pitcrew: Pitcrew,
    load_scenario: LoadScenario,
    testops: FakeTestOps,
    gitlab: FakeGitLab,
    slack: FakeSlack,
) -> None:
    night = load_scenario("green_night")

    answer = pitcrew.trigger_night_run(night)

    body = pitcrew.run_chain(answer.trace_id)
    assert body["runs"] == [
        {
            "kind": "nightly",
            "pipeline_id": night.nightly.pipeline_id,
            "launch_id": night.nightly.launch_id,
            "expected_test_count": 1,
            "failed_test_count": 0,
            "outcome": "green",
            "outcome_reason": None,
        }
    ]
    assert body["status"] == {"step": "night_run", "activity": "done"}
    assert body["conclusion"] is None
    assert (testops.written_test_plans, gitlab.created_pipelines) == ([], [])
    assert slack.posted == []


def test_night_run_with_too_few_results_is_broken(
    pitcrew: Pitcrew,
    load_scenario: LoadScenario,
    testops: FakeTestOps,
    gitlab: FakeGitLab,
    slack: FakeSlack,
) -> None:
    night = load_scenario("night_with_one_result")

    answer = pitcrew.trigger_night_run(night)

    body = pitcrew.run_chain(answer.trace_id)
    assert body["runs"] == [
        {
            "kind": "nightly",
            "pipeline_id": night.nightly.pipeline_id,
            "launch_id": night.nightly.launch_id,
            "expected_test_count": 1675,
            "failed_test_count": 0,
            "outcome": "broken",
            "outcome_reason": "1 result out of ~1675 expected",
        }
    ]
    assert body["status"] == {"step": "night_run", "activity": "done"}
    assert body["conclusion"]["posted_at"].endswith("Z")
    assert [post_text(post) for post in slack.posted] == [
        conclusions.BROKEN_NIGHT_RUN_TOO_FEW_RESULTS
    ]
    assert (testops.written_test_plans, gitlab.created_pipelines) == ([], [])


def test_night_run_logs_the_results_it_judged_by(
    pitcrew: Pitcrew, load_scenario: LoadScenario, logs: Logs
) -> None:
    night = load_scenario("night_with_one_result")

    answer = pitcrew.trigger_night_run(night)

    (checked,) = [line for line in logs.lines() if line["message"] == "Results checked"]
    assert (
        checked["trace_id"],
        checked["activity"],
        checked["result_count"],
        checked["expected_test_count"],
        checked["broken_reason"],
    ) == (answer.trace_id, "judging_run", 1, 1675, "1 result out of ~1675 expected")


def test_night_run_with_a_broken_pipeline_reads_no_test_results(
    pitcrew: Pitcrew,
    load_scenario: LoadScenario,
    testops: FakeTestOps,
    slack: FakeSlack,
) -> None:
    """The results of tests that did not run to the end are not worth counting."""
    night = load_scenario("canceled_night")

    answer = pitcrew.trigger_night_run(night)

    [nightly] = pitcrew.run_chain(answer.trace_id)["runs"]
    assert nightly == {
        "kind": "nightly",
        "pipeline_id": night.nightly.pipeline_id,
        "launch_id": night.nightly.launch_id,
        "expected_test_count": None,
        "failed_test_count": None,
        "outcome": "broken",
        "outcome_reason": "pipeline canceled at stage test",
    }
    assert [post_text(post) for post in slack.posted] == [
        conclusions.BROKEN_NIGHT_RUN_PIPELINE
    ]
    assert testops.searched_launches == []


def test_night_run_with_more_failures_than_its_team_allows_is_broken(
    start_pitcrew: StartPitcrew,
    load_scenario: LoadScenario,
    testops: FakeTestOps,
    gitlab: FakeGitLab,
    slack: FakeSlack,
) -> None:
    """11% of the results failed: rerun under the base config's 50%, broken under this
    Team's 10%."""
    night = load_scenario("night_with_failures")
    pitcrew = start_pitcrew(config="gateway_with_a_low_max_failed_ratio")

    answer = pitcrew.trigger_night_run(night)

    [nightly] = pitcrew.run_chain(answer.trace_id)["runs"]
    assert (nightly["outcome"], nightly["outcome_reason"]) == (
        "broken",
        "too many failures, likely an environment problem: 685 of 6292 results failed",
    )
    assert [post_text(post) for post in slack.posted] == [
        conclusions.BROKEN_NIGHT_RUN_TOO_MANY_FAILURES
    ]
    assert (testops.written_test_plans, gitlab.created_pipelines) == ([], [])


def test_conclusion_slack_failed_to_take_fails_the_step_after_the_answer(
    pitcrew: Pitcrew, load_scenario: LoadScenario, slack: FakeSlack, logs: Logs
) -> None:
    """The webhook URL is a secret: the error names its variable instead."""
    night = load_scenario("night_with_one_result")
    slack.failures = 1

    answer = pitcrew.trigger_night_run(night)

    assert answer.status_code == 202
    (failure,) = [line for line in logs.lines() if line["message"] == "Step failed"]
    assert (failure["level"], failure["exc_type"]) == ("error", "ClientException")
    assert f"rollup_error (POST ${SLACK_WEBHOOK_VARIABLE})" in failure["exception"]
    assert SLACK_WEBHOOK not in logs.text


def test_conclusion_slack_failed_to_take_is_posted_by_a_repeated_trigger(
    pitcrew: Pitcrew, load_scenario: LoadScenario, slack: FakeSlack
) -> None:
    night = load_scenario("night_with_one_result")
    slack.failures = 1
    pitcrew.trigger_night_run(night)

    answer = pitcrew.trigger_night_run(night)

    assert answer.status_code == 202
    assert [post_text(post) for post in slack.posted] == [
        conclusions.BROKEN_NIGHT_RUN_TOO_FEW_RESULTS
    ]
    assert pitcrew.run_chain(answer.trace_id)["status"] == {
        "step": "night_run",
        "activity": "done",
    }


def test_night_run_with_failures_starts_a_rerun(
    pitcrew: Pitcrew,
    load_scenario: LoadScenario,
    testops: FakeTestOps,
    gitlab: FakeGitLab,
) -> None:
    night = load_scenario("night_with_failures")

    answer = pitcrew.trigger_night_run(night)

    assert testops.written_test_plans == [
        (night.rerun.test_plan_id, night.rerun.recorded("test_plan_request.json"))
    ]
    assert gitlab.created_pipelines == [
        CreatedPipeline(
            ref="master",
            inputs={
                "PROJECT_NAME": "Gateway",
                "ENVIRONMENT": "staging",
                "TEST_PLAN_ID": str(night.rerun.test_plan_id),
                "NOTIFY_SLACK": True,
                "RUN_WITH_FLAGS": True,
            },
            variables={
                "PITCREW_STEP": "night_rerun",
                "ALLURE_LAUNCH_TAGS": "master, gitlab, "
                f"pitcrew-rerun-of-{night.nightly.launch_id}",
            },
        )
    ]
    body = pitcrew.run_chain(answer.trace_id)
    assert body["runs"] == [
        {
            "kind": "nightly",
            "pipeline_id": night.nightly.pipeline_id,
            "launch_id": night.nightly.launch_id,
            "expected_test_count": 1675,
            "failed_test_count": 685,
            "outcome": "with_failures",
            "outcome_reason": None,
        },
        {
            "kind": "rerun",
            "pipeline_id": night.rerun.pipeline_id,
            "launch_id": None,
            "expected_test_count": 223,
            "failed_test_count": None,
            "outcome": None,
            "outcome_reason": None,
        },
    ]
    assert body["status"] == {"step": "night_rerun", "activity": "waiting_for_trigger"}


def test_broken_night_run_without_the_conclusion_feature_posts_nothing(
    start_pitcrew: StartPitcrew, load_scenario: LoadScenario, slack: FakeSlack
) -> None:
    night = load_scenario("night_with_one_result")
    pitcrew = start_pitcrew(config="gateway_without_conclusion")

    answer = pitcrew.trigger_night_run(night)

    body = pitcrew.run_chain(answer.trace_id)
    assert [run["outcome"] for run in body["runs"]] == ["broken"]
    assert body["status"] == {"step": "night_run", "activity": "done"}
    assert body["conclusion"] is None
    assert slack.posted == []


def test_night_run_with_failures_without_the_rerun_feature_starts_no_rerun(
    start_pitcrew: StartPitcrew,
    load_scenario: LoadScenario,
    testops: FakeTestOps,
    gitlab: FakeGitLab,
    slack: FakeSlack,
) -> None:
    night = load_scenario("night_with_failures")
    pitcrew = start_pitcrew(config="gateway_without_rerun")

    answer = pitcrew.trigger_night_run(night)

    body = pitcrew.run_chain(answer.trace_id)
    assert [run["outcome"] for run in body["runs"]] == ["with_failures"]
    assert body["conclusion"] is None
    assert body["status"] == {"step": "night_run", "activity": "done"}
    assert (testops.written_test_plans, gitlab.created_pipelines) == ([], [])
    assert slack.posted == []


def test_rerun_runs_on_the_configured_branch_with_the_configured_inputs(
    start_pitcrew: StartPitcrew, load_scenario: LoadScenario, gitlab: FakeGitLab
) -> None:
    night = load_scenario("night_with_failures")
    pitcrew = start_pitcrew(config="gateway_rerun_on_a_debug_branch")

    pitcrew.trigger_night_run(night)

    [pipeline] = gitlab.created_pipelines
    assert pipeline.ref == "pitcrew-debug"
    assert pipeline.inputs == {
        "PROJECT_NAME": "Gateway",
        "ENVIRONMENT": "staging",
        "TEST_PLAN_ID": str(night.rerun.test_plan_id),
        "NOTIFY_SLACK": False,
        "RUN_WITH_FLAGS": False,
        "PYTEST_WORKERS_NUMBER": 4,
    }
    assert pipeline.variables["ALLURE_LAUNCH_TAGS"] == (
        f"pitcrew-debug, gitlab, pitcrew-rerun-of-{night.nightly.launch_id}"
    )


def test_repeated_trigger_of_a_night_run_with_failures_starts_no_second_rerun(
    pitcrew: Pitcrew,
    load_scenario: LoadScenario,
    testops: FakeTestOps,
    gitlab: FakeGitLab,
) -> None:
    night = load_scenario("night_with_failures")
    first = pitcrew.trigger_night_run(night)

    answer = pitcrew.trigger_night_run(night)

    assert (answer.status_code, answer.trace_id) == (200, first.trace_id)
    assert len(testops.written_test_plans) == 1
    assert len(gitlab.created_pipelines) == 1


def test_night_run_with_failures_is_recorded_before_the_rerun_is_created(
    pitcrew: Pitcrew, load_scenario: LoadScenario, gitlab: FakeGitLab
) -> None:
    night = load_scenario("night_with_failures")
    gitlab.create_pipeline_error = httpx.Response(500, json={"message": "500"})

    answer = pitcrew.trigger_night_run(night)

    body = pitcrew.run_chain(answer.trace_id)
    [nightly] = body["runs"]
    assert (nightly["outcome"], nightly["failed_test_count"]) == ("with_failures", 685)
    assert body["status"] == {"step": "night_run", "activity": "failed"}


def test_repeated_trigger_starts_the_rerun_gitlab_failed_to_create(
    pitcrew: Pitcrew, load_scenario: LoadScenario, gitlab: FakeGitLab
) -> None:
    night = load_scenario("night_with_failures")
    gitlab.create_pipeline_error = httpx.Response(500, json={"message": "500"})
    first = pitcrew.trigger_night_run(night)
    gitlab.create_pipeline_error = None

    answer = pitcrew.trigger_night_run(night)

    assert (answer.status_code, answer.trace_id) == (202, first.trace_id)
    assert len(gitlab.created_pipelines) == 1
    body = pitcrew.run_chain(answer.trace_id)
    assert [(run["kind"], run["outcome"]) for run in body["runs"]] == [
        ("nightly", "with_failures"),
        ("rerun", None),
    ]
    assert body["status"] == {"step": "night_rerun", "activity": "waiting_for_trigger"}


def test_repeated_trigger_of_a_finished_night_run_reads_no_results_again(
    pitcrew: Pitcrew, load_scenario: LoadScenario, testops: FakeTestOps
) -> None:
    night = load_scenario("green_night")
    first = pitcrew.trigger_night_run(night)
    searched = list(testops.searched_launches)

    answer = pitcrew.trigger_night_run(night)

    assert (answer.status_code, answer.trace_id) == (200, first.trace_id)
    assert testops.searched_launches == searched


def test_night_run_gitlab_failed_shows_failed_with_its_masked_reason(
    pitcrew: Pitcrew, load_scenario: LoadScenario, gitlab: FakeGitLab
) -> None:
    night = load_scenario("night_with_failures")
    gitlab.pipeline_jobs_error = httpx.Response(
        500, json={"message": f"token {GITLAB_TOKEN} broke"}
    )

    answer = pitcrew.trigger_night_run(night)

    body = pitcrew.run_chain(answer.trace_id)
    assert body["status"] == {"step": "night_run", "activity": "failed"}
    assert body["failure_reason"] == (
        "ClientException: token *** broke (GET "
        f"{GITLAB_URL}/api/v4/projects/{QA_AUTOMATION}/pipelines/"
        f"{night.nightly.pipeline_id}/jobs?per_page=100)"
    )


def test_failed_night_run_is_resumed_by_a_repeated_trigger(
    pitcrew: Pitcrew, load_scenario: LoadScenario, gitlab: FakeGitLab
) -> None:
    night = load_scenario("night_with_failures")
    gitlab.pipeline_jobs_error = httpx.Response(500, json={"message": "500"})
    first = pitcrew.trigger_night_run(night)
    gitlab.pipeline_jobs_error = None

    answer = pitcrew.trigger_night_run(night)

    assert (answer.status_code, answer.trace_id) == (202, first.trace_id)
    body = pitcrew.run_chain(answer.trace_id)
    assert body["status"] == {"step": "night_rerun", "activity": "waiting_for_trigger"}
    assert body["failure_reason"] is None
