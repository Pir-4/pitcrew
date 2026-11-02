from fastapi.testclient import TestClient

from tests.support.constants import AUTH, UNKNOWN_TRACE_ID
from tests.support.fakes import FakeSlack
from tests.support.run_chain import Pitcrew, StartPitcrew
from tests.support.scenarios import LoadScenario


def test_run_chain_shows_its_team_and_environment(
    pitcrew: Pitcrew, load_scenario: LoadScenario
) -> None:
    night = load_scenario("green_night")
    answer = pitcrew.trigger_night_run(night)

    body = pitcrew.run_chain(answer.trace_id)

    assert (body["team"], body["environment"]) == ("Gateway", "staging")


def test_run_chain_shows_its_timestamps_in_utc(
    pitcrew: Pitcrew, load_scenario: LoadScenario
) -> None:
    """Also after the round trip through SQLite, which drops the timezone."""
    night = load_scenario("green_night")
    answer = pitcrew.trigger_night_run(night)

    body = pitcrew.run_chain(answer.trace_id)

    assert body["created_at"].endswith("Z")
    assert body["updated_at"].endswith("Z")


def test_run_chains_of_different_nightly_runs_are_separate(
    start_pitcrew: StartPitcrew, load_scenario: LoadScenario
) -> None:
    """The night's Rerun, triggered as a Nightly run, stands for another Nightly run: the
    first chain starts no Rerun, so that its pipeline belongs to no Run yet."""
    night = load_scenario("night_with_failures_rerun_broken")
    pitcrew = start_pitcrew(config="gateway_without_rerun")
    first = pitcrew.trigger_night_run(night)

    answer = pitcrew.trigger_night_run(
        night,
        pipeline_id=night.rerun.pipeline_id,
        allure_launch_id=night.rerun.launch_id,
    )

    assert answer.status_code == 202
    assert answer.trace_id != first.trace_id


def test_run_chain_shows_the_night_rerun_that_failed(
    pitcrew: Pitcrew, load_scenario: LoadScenario, slack: FakeSlack
) -> None:
    night = load_scenario("night_with_failures_rerun_broken")
    night_run = pitcrew.trigger_night_run(night)
    slack.failures = 1

    pitcrew.trigger_night_rerun(night)

    body = pitcrew.run_chain(night_run.trace_id)
    assert body["status"] == {"step": "night_rerun", "activity": "failed"}
    assert body["failure_reason"] == (
        "ClientException: rollup_error (POST $SLACK_WEBHOOK_GATEWAY)"
    )
    assert body["runs"][1]["launch_id"] == night.rerun.launch_id
    assert body["conclusion"] is None


def test_run_chain_shows_no_failure_reason_while_no_step_failed(
    pitcrew: Pitcrew, load_scenario: LoadScenario
) -> None:
    night = load_scenario("green_night")

    answer = pitcrew.trigger_night_run(night)

    assert pitcrew.run_chain(answer.trace_id)["failure_reason"] is None


def test_repeated_trigger_resumes_the_step_that_did_not_finish(
    pitcrew: Pitcrew, load_scenario: LoadScenario, slack: FakeSlack
) -> None:
    night = load_scenario("night_with_failures_rerun_broken")
    night_run = pitcrew.trigger_night_run(night)
    slack.failures = 1
    pitcrew.trigger_night_rerun(night)

    answer = pitcrew.trigger_night_rerun(night)

    assert answer.status_code == 202
    assert pitcrew.run_chain(night_run.trace_id)["status"] == {
        "step": "night_rerun",
        "activity": "done",
    }
    assert len(slack.posted) == 1


def test_run_chain_of_an_unknown_trace_id_is_not_found(client: TestClient) -> None:
    response = client.get(f"/run-chains/{UNKNOWN_TRACE_ID}", headers=AUTH)

    assert response.status_code == 404
    assert response.json() == {
        "detail": f"No Run chain with trace id {UNKNOWN_TRACE_ID}"
    }


def test_run_chain_of_a_malformed_trace_id_is_rejected(client: TestClient) -> None:
    response = client.get("/run-chains/478951", headers=AUTH)

    assert response.status_code == 422


def test_run_chain_without_token_is_rejected(client: TestClient) -> None:
    response = client.get(f"/run-chains/{UNKNOWN_TRACE_ID}")

    assert response.status_code == 401
