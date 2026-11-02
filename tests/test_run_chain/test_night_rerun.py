from tests.data import conclusions
from tests.support.fakes import FakeSlack, FakeTestOps
from tests.support.logs import Logs
from tests.support.run_chain import Pitcrew, StartPitcrew
from tests.support.scenarios import LoadScenario
from tests.support.slack_post import post_text


def test_night_rerun_continues_the_run_chain_of_its_night_run(
    pitcrew: Pitcrew, load_scenario: LoadScenario
) -> None:
    night = load_scenario("small_night_failing_on_rerun")
    night_run = pitcrew.trigger_night_run(night)

    answer = pitcrew.trigger_night_rerun(night)

    assert (answer.status_code, answer.trace_id) == (202, night_run.trace_id)


def test_night_rerun_posts_the_conclusion_with_its_error_groups(
    pitcrew: Pitcrew,
    load_scenario: LoadScenario,
    testops: FakeTestOps,
    slack: FakeSlack,
) -> None:
    night = load_scenario("small_night_failing_on_rerun")
    pitcrew.trigger_night_run(night)

    answer = pitcrew.trigger_night_rerun(night)

    body = pitcrew.run_chain(answer.trace_id)
    assert body["runs"][1] == {
        "kind": "rerun",
        "pipeline_id": night.rerun.pipeline_id,
        "launch_id": night.rerun.launch_id,
        "expected_test_count": 2,
        "failed_test_count": 2,
        "outcome": "with_failures",
        "outcome_reason": None,
    }
    assert body["error_groups"] == [
        {
            "kind": "model",
            "key": "DataResponse[RoutersOverview]",
            "test_count": 1,
            "tests": [
                {
                    "test_result_id": 11849203,
                    "test_case_id": 124669,
                    "name": "API: Routers overview holds valid router versions",
                }
            ],
        }
    ]
    assert body["status"] == {"step": "night_rerun", "activity": "done"}
    assert body["conclusion"]["posted_at"].endswith("Z")
    assert [post_text(post) for post in slack.posted] == [
        conclusions.RERUN_WITH_AN_ERROR_GROUP_AND_THE_REST
    ]
    assert sorted(testops.read_test_results) == [11849203, 11849204]


def test_night_rerun_logs_the_error_groups_it_recognized(
    pitcrew: Pitcrew, load_scenario: LoadScenario, logs: Logs
) -> None:
    night = load_scenario("small_night_failing_on_rerun")
    pitcrew.trigger_night_run(night)

    answer = pitcrew.trigger_night_rerun(night)

    (recognized,) = [
        line for line in logs.lines() if line["message"] == "Error groups recognized"
    ]
    assert (
        recognized["level"],
        recognized["trace_id"],
        recognized["error_group_count"],
        recognized["grouped_test_count"],
    ) == ("info", answer.trace_id, 1, 1)


def test_rerun_without_the_error_groups_feature_groups_nothing(
    start_pitcrew: StartPitcrew,
    load_scenario: LoadScenario,
    testops: FakeTestOps,
    slack: FakeSlack,
) -> None:
    night = load_scenario("small_night_failing_on_rerun")
    pitcrew = start_pitcrew(config="gateway_without_error_groups")
    pitcrew.trigger_night_run(night)

    answer = pitcrew.trigger_night_rerun(night)

    assert pitcrew.run_chain(answer.trace_id)["error_groups"] == []
    assert [post_text(post) for post in slack.posted] == [
        conclusions.RERUN_WITHOUT_ERROR_GROUPS
    ]
    assert testops.read_test_results == []


def test_night_rerun_stores_every_error_group_with_its_tests(
    pitcrew: Pitcrew, load_scenario: LoadScenario
) -> None:
    night = load_scenario("small_night_rerun_with_error_groups")
    pitcrew.trigger_night_run(night)

    answer = pitcrew.trigger_night_rerun(night)

    body = pitcrew.run_chain(answer.trace_id)
    assert body["runs"][1]["failed_test_count"] == 5
    assert body["error_groups"] == [
        {
            "kind": "model",
            "key": "PoolModel",
            "test_count": 3,
            "tests": [
                {
                    "test_result_id": 11890501,
                    "test_case_id": 89663,
                    "name": "API: Pool by address returns fees and reserves",
                },
                {
                    "test_result_id": 11890502,
                    "test_case_id": 100830,
                    "name": "API: Pools list filtered by asset",
                },
                {
                    "test_result_id": 11890503,
                    "test_case_id": 106459,
                    "name": "API: Pool stats for a period",
                },
            ],
        },
        {
            "kind": "model",
            "key": "DataResponse[RoutersOverview]",
            "test_count": 1,
            "tests": [
                {
                    "test_result_id": 11890500,
                    "test_case_id": 124669,
                    "name": "API: Routers overview holds valid router versions",
                }
            ],
        },
    ]


def test_resumed_night_rerun_stores_its_error_groups_once(
    pitcrew: Pitcrew,
    load_scenario: LoadScenario,
    testops: FakeTestOps,
    slack: FakeSlack,
) -> None:
    """Slack failing the first Conclusion leaves the Step unfinished: the trigger resumes
    it."""
    night = load_scenario("small_night_rerun_with_error_groups")
    slack.failures = 1
    pitcrew.trigger_night_run(night)
    pitcrew.trigger_night_rerun(night)
    read = list(testops.read_test_results)

    answer = pitcrew.trigger_night_rerun(night)

    assert answer.status_code == 202
    groups = pitcrew.run_chain(answer.trace_id)["error_groups"]
    assert [(group["key"], group["test_count"]) for group in groups] == [
        ("PoolModel", 3),
        ("DataResponse[RoutersOverview]", 1),
    ]
    assert [post_text(post) for post in slack.posted] == [
        conclusions.RERUN_WITH_TWO_ERROR_GROUPS
    ]
    assert (len(read), testops.read_test_results) == (5, read)


def test_rerun_failing_above_the_nightly_share_of_failures_is_not_broken(
    start_pitcrew: StartPitcrew, load_scenario: LoadScenario, slack: FakeSlack
) -> None:
    """Both tests of the Rerun fail again, far above the Nightly run's limit of 10%."""
    night = load_scenario("small_night_failing_on_rerun")
    pitcrew = start_pitcrew(config="gateway_with_a_low_max_failed_ratio")
    pitcrew.trigger_night_run(night)

    answer = pitcrew.trigger_night_rerun(night)

    rerun = pitcrew.run_chain(answer.trace_id)["runs"][1]
    assert (rerun["outcome"], rerun["outcome_reason"]) == ("with_failures", None)
    assert [post_text(post) for post in slack.posted] == [
        conclusions.RERUN_WITH_AN_ERROR_GROUP_AND_THE_REST
    ]


def test_broken_rerun_is_reported_as_broken(
    pitcrew: Pitcrew,
    load_scenario: LoadScenario,
    testops: FakeTestOps,
    slack: FakeSlack,
) -> None:
    """Unconfirmed failures are not grouped: their errors are not even read."""
    night = load_scenario("night_with_failures_rerun_broken")
    pitcrew.trigger_night_run(night)

    answer = pitcrew.trigger_night_rerun(night)

    body = pitcrew.run_chain(answer.trace_id)
    assert body["runs"][1] == {
        "kind": "rerun",
        "pipeline_id": night.rerun.pipeline_id,
        "launch_id": night.rerun.launch_id,
        "expected_test_count": 223,
        "failed_test_count": 2,
        "outcome": "broken",
        "outcome_reason": "2 results out of ~223 expected",
    }
    assert body["error_groups"] == []
    assert [post_text(post) for post in slack.posted] == [conclusions.BROKEN_RERUN]
    assert testops.read_test_results == []


def test_green_rerun_is_reported_green(
    pitcrew: Pitcrew, load_scenario: LoadScenario, slack: FakeSlack
) -> None:
    night = load_scenario("small_night_green_on_rerun")
    pitcrew.trigger_night_run(night)

    answer = pitcrew.trigger_night_rerun(night)

    body = pitcrew.run_chain(answer.trace_id)
    assert [run["outcome"] for run in body["runs"]] == ["with_failures", "green"]
    assert body["status"] == {"step": "night_rerun", "activity": "done"}
    assert [post_text(post) for post in slack.posted] == [conclusions.GREEN_RERUN]


def test_night_rerun_without_the_conclusion_feature_posts_nothing(
    start_pitcrew: StartPitcrew, load_scenario: LoadScenario, slack: FakeSlack
) -> None:
    night = load_scenario("small_night_failing_on_rerun")
    pitcrew = start_pitcrew(config="gateway_without_conclusion")
    pitcrew.trigger_night_run(night)

    answer = pitcrew.trigger_night_rerun(night)

    body = pitcrew.run_chain(answer.trace_id)
    assert [run["outcome"] for run in body["runs"]] == ["with_failures"] * 2
    assert body["status"] == {"step": "night_rerun", "activity": "done"}
    assert body["conclusion"] is None
    assert slack.posted == []


def test_night_rerun_of_an_unknown_rerun_pipeline_posts_no_conclusion(
    pitcrew: Pitcrew, load_scenario: LoadScenario, slack: FakeSlack
) -> None:
    """No Run chain started the night's Rerun pipeline: its trigger is rejected
    (`test_triggers.py`)."""
    night = load_scenario("night_with_failures_rerun_broken")

    pitcrew.trigger_night_rerun(night)

    assert slack.posted == []


def test_repeated_night_rerun_posts_no_second_conclusion(
    pitcrew: Pitcrew, load_scenario: LoadScenario, slack: FakeSlack
) -> None:
    night = load_scenario("night_with_failures_rerun_broken")
    pitcrew.trigger_night_run(night)
    first = pitcrew.trigger_night_rerun(night)

    answer = pitcrew.trigger_night_rerun(night)

    assert (answer.status_code, answer.trace_id) == (200, first.trace_id)
    assert len(slack.posted) == 1
