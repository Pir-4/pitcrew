import httpx2 as httpx

from tests.support.constants import (
    ALLURE_ENDPOINT,
    ALLURE_TOKEN,
    GITLAB_TOKEN,
    SLACK_WEBHOOK,
    TOKEN,
)
from tests.support.fakes import FakeGitLab
from tests.support.logs import Logs
from tests.support.run_chain import Pitcrew
from tests.support.scenarios import LoadScenario


def test_log_lines_of_every_step_carry_the_trace_id(
    pitcrew: Pitcrew, load_scenario: LoadScenario, logs: Logs
) -> None:
    night = load_scenario("night_with_failures_rerun_broken")

    night_run = pitcrew.trigger_night_run(night)
    pitcrew.trigger_night_rerun(night)

    steps = [(line["step"], line["message"]) for line in logs.lines("pitcrew.steps")]
    assert steps == [
        ("night_run", "Trigger accepted"),
        ("night_run", "Step started"),
        ("night_run", "Pipeline checked"),
        ("night_run", "Results checked"),
        ("night_run", "Run outcome decided"),
        ("night_run", "Rerun started"),
        ("night_run", "Step finished"),
        ("night_rerun", "Trigger accepted"),
        ("night_rerun", "Step started"),
        ("night_rerun", "Pipeline checked"),
        ("night_rerun", "Results checked"),
        ("night_rerun", "Run outcome decided"),
        ("night_rerun", "Conclusion posted"),
        ("night_rerun", "Step finished"),
    ]
    traced = [line for line in logs.lines() if "trace_id" in line]
    assert {line["trace_id"] for line in traced} == {night_run.trace_id}
    assert {line["team"] for line in logs.lines()} == {"Gateway"}
    assert "External call" in logs.messages("pitcrew.clients")
    assert logs.messages("pitcrew.api") == ["Request handled", "Request handled"]


def test_launch_check_logged_before_the_run_chain_is_known_shares_the_request_id(
    pitcrew: Pitcrew, load_scenario: LoadScenario, logs: Logs
) -> None:
    """The launch is checked before the Run chain is found, so its line has no trace id; the
    request id ties it to the rest of its request."""
    night = load_scenario("night_with_failures_rerun_broken")

    pitcrew.trigger_night_run(night)
    pitcrew.trigger_night_rerun(night)

    untraced = [line for line in logs.lines() if "trace_id" not in line]
    assert [line["url"] for line in untraced] == [
        f"{ALLURE_ENDPOINT}/api/rs/launch/{night.nightly.launch_id}/job",
        f"{ALLURE_ENDPOINT}/api/rs/launch/{night.rerun.launch_id}/job",
    ]
    traced = [line for line in logs.lines() if "trace_id" in line]
    assert {line["request_id"] for line in untraced} <= {
        line["request_id"] for line in traced
    }


def test_step_failed_in_the_background_is_logged_with_its_context(
    pitcrew: Pitcrew, load_scenario: LoadScenario, gitlab: FakeGitLab, logs: Logs
) -> None:
    """GitLab rejects the Rerun and echoes the token back: neither may reach the caller as an
    error, nor the token the log."""
    night = load_scenario("night_with_failures")
    gitlab.create_pipeline_error = httpx.Response(
        400, json={"message": f"PROJECT_NAME is invalid; token {GITLAB_TOKEN}"}
    )

    answer = pitcrew.trigger_night_run(night)

    assert answer.status_code == 202
    assert pitcrew.run_chain(answer.trace_id)["status"] == {
        "step": "night_run",
        "activity": "failed",
    }
    (call,) = [
        line
        for line in logs.lines("pitcrew.clients")
        if line["message"] == "External call answered an error"
    ]
    assert (call["client"], call["status_code"], call["reason"]) == (
        "GitLabClient",
        400,
        "PROJECT_NAME is invalid; token ***",
    )
    (failure,) = [line for line in logs.lines() if line["message"] == "Step failed"]
    context = {
        "level": "error",
        "trace_id": answer.trace_id,
        "step": "night_run",
        "pipeline_id": night.nightly.pipeline_id,
        "activity": "starting_rerun",
        "exc_type": "ClientException",
    }
    assert {key: failure[key] for key in context} == context
    assert "Traceback" in failure["exception"]
    assert "PROJECT_NAME is invalid" in failure["exception"]
    assert GITLAB_TOKEN not in logs.text


def test_no_secret_reaches_the_log(
    pitcrew: Pitcrew, load_scenario: LoadScenario, logs: Logs
) -> None:
    night = load_scenario("night_with_failures_rerun_broken")

    night_run = pitcrew.trigger_night_run(night)
    pitcrew.trigger_night_rerun(night)
    pitcrew.run_chain(night_run.trace_id)

    for secret in (TOKEN, ALLURE_TOKEN, GITLAB_TOKEN, SLACK_WEBHOOK):
        assert secret not in logs.text
