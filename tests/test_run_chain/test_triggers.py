from collections.abc import Callable
from dataclasses import dataclass

import pytest

from pitcrew.constants import Step
from pitcrew.steps.registry import STEPS
from tests.support.constants import ALLURE_ENDPOINT
from tests.support.fakes import FakeGitLab, FakeTestOps
from tests.support.logs import Logs
from tests.support.run_chain import Answer, Pitcrew, StartPitcrew
from tests.support.scenarios import LoadScenario, Night


@dataclass(frozen=True)
class Rejection:
    """A row of the rejected triggers: the trigger sent for the night, what it is answered
    (`reason` names the night's ids as `{night...}`: a test holds no id of its own), the
    night, the error switch of TestOps set before the trigger, and the Step left without a
    class."""

    trigger: Callable[[Pitcrew, Night], Answer]
    status_code: int
    reason: str
    scenario: str = "night_with_failures_rerun_broken"
    switch: Callable[[FakeTestOps, Night], None] | None = None
    not_implemented: Step | None = None


def revoke_the_token(testops: FakeTestOps, night: Night) -> None:
    testops.token_revoked = True


@pytest.mark.parametrize(
    "rejection",
    [
        pytest.param(
            Rejection(
                lambda pitcrew, night: pitcrew.trigger_night_run(night, token=None),
                401,
                "Invalid or missing bearer token",
            ),
            id="no token",
        ),
        pytest.param(
            Rejection(
                lambda pitcrew, night: pitcrew.trigger_night_run(
                    night, token="not-the-token"
                ),
                401,
                "Invalid or missing bearer token",
            ),
            id="a wrong token",
        ),
        pytest.param(
            Rejection(
                lambda pitcrew, night: pitcrew.trigger_night_run(night, team="Nobody"),
                422,
                "No Team config for team 'Nobody'",
            ),
            id="a Team without a Team config",
        ),
        # The Environment goes into the Rerun as `ENVIRONMENT`, one of qa_automation's
        # options.
        pytest.param(
            Rejection(
                lambda pitcrew, night: pitcrew.trigger_night_run(
                    night, environment="mainnet"
                ),
                422,
                "environment: Input should be 'staging' or 'testnet'",
            ),
            id="an unknown Environment",
        ),
        pytest.param(
            Rejection(
                lambda pitcrew, night: pitcrew.trigger_night_run(
                    night, step="night_party"
                ),
                422,
                "step: Input should be 'night_run' or 'night_rerun'",
            ),
            id="an unknown Step",
        ),
        # The launch belongs to the pipeline, but no Run chain started that pipeline as its
        # Rerun.
        pytest.param(
            Rejection(
                lambda pitcrew, night: pitcrew.trigger_night_rerun(night),
                422,
                "Pipeline {night.rerun.pipeline_id} is not the Rerun of any Run chain",
            ),
            id="an unknown Rerun pipeline",
        ),
        # The night's Rerun launch, claimed for its Nightly run's pipeline.
        pytest.param(
            Rejection(
                lambda pitcrew, night: pitcrew.trigger_night_run(
                    night, allure_launch_id=night.rerun.launch_id
                ),
                422,
                "Allure launch {night.rerun.launch_id} belongs to pipeline "
                "{night.rerun.pipeline_id}, not to pipeline {night.nightly.pipeline_id}",
            ),
            id="a launch of another pipeline",
        ),
        # TestOps answers `403` for a launch that does not exist, as for one it hides: no
        # night holds launch 999999999.
        pytest.param(
            Rejection(
                lambda pitcrew, night: pitcrew.trigger_night_run(
                    night, allure_launch_id=999999999
                ),
                422,
                "TestOps denies access to Allure launch 999999999: it does not exist, "
                "or the token has no access to its project",
            ),
            id="a launch TestOps denies",
        ),
        pytest.param(
            Rejection(
                lambda pitcrew, night: pitcrew.trigger_night_run(night),
                422,
                "Allure launch {night.nightly.launch_id} does not exist in TestOps",
                switch=lambda testops, night: testops.not_found_launches.add(
                    night.nightly.launch_id
                ),
            ),
            id="a launch TestOps does not find",
        ),
        pytest.param(
            Rejection(
                lambda pitcrew, night: pitcrew.trigger_night_run(night),
                422,
                "Allure launch {night.nightly.launch_id} has no GitLab pipeline",
                scenario="launch_without_pipeline",
            ),
            id="a launch of no pipeline",
        ),
        # Pitcrew's own token, not the trigger: the caller can do nothing about it.
        pytest.param(
            Rejection(
                lambda pitcrew, night: pitcrew.trigger_night_run(night),
                502,
                "TestOps rejected Pitcrew's token (ALLURE_TOKEN): auth.bad-token "
                f"(GET {ALLURE_ENDPOINT}/api/rs/launch/{{night.nightly.launch_id}}/job)",
                switch=revoke_the_token,
            ),
            id="TestOps rejects Pitcrew's token",
        ),
        pytest.param(
            Rejection(
                lambda pitcrew, night: pitcrew.trigger_night_rerun(night),
                501,
                "Step night_rerun is not implemented yet",
                not_implemented=Step.NIGHT_RERUN,
            ),
            id="a Step with no class",
        ),
    ],
)
def test_trigger_is_rejected(
    pitcrew: Pitcrew,
    load_scenario: LoadScenario,
    testops: FakeTestOps,
    rejection: Rejection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    night = load_scenario(rejection.scenario)
    if rejection.switch is not None:
        rejection.switch(testops, night)
    if rejection.not_implemented is not None:
        monkeypatch.delitem(STEPS, rejection.not_implemented)

    answer = rejection.trigger(pitcrew, night)

    assert (answer.status_code, answer.reason) == (
        rejection.status_code,
        rejection.reason.format(night=night),
    )


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"team": "Nobody"}, id="a Team without a Team config"),
        pytest.param({"environment": "mainnet"}, id="an unknown Environment"),
    ],
)
def test_trigger_with_an_invalid_field_checks_no_launch(
    pitcrew: Pitcrew,
    load_scenario: LoadScenario,
    testops: FakeTestOps,
    overrides: dict[str, str],
) -> None:
    night = load_scenario("night_with_failures")

    pitcrew.trigger_night_run(night, **overrides)

    assert testops.checked_launches == []


def test_trigger_of_a_team_with_only_a_team_config_starts_its_run_chain(
    start_pitcrew: StartPitcrew, load_scenario: LoadScenario
) -> None:
    pitcrew = start_pitcrew(team="Farming")
    night = load_scenario("green_night")

    answer = pitcrew.trigger_night_run(night, team="Farming")

    chain = pitcrew.run_chain(answer.trace_id)
    assert (answer.status_code, chain["team"], chain["status"]) == (
        202,
        "Farming",
        {"step": "night_run", "activity": "done"},
    )


# qa_automation takes only its own spelling of `PROJECT_NAME`: the Team config's, never the
# caller's.
def test_trigger_of_a_team_spelled_otherwise_uses_the_team_config_spelling(
    pitcrew: Pitcrew, load_scenario: LoadScenario, gitlab: FakeGitLab
) -> None:
    night = load_scenario("night_with_failures")

    answer = pitcrew.trigger_night_run(night, team="gateway")

    [pipeline] = gitlab.created_pipelines
    assert (
        answer.status_code,
        pitcrew.run_chain(answer.trace_id)["team"],
        pipeline.inputs["PROJECT_NAME"],
    ) == (202, "Gateway", "Gateway")


def test_trigger_rejected_for_its_launch_is_logged(
    pitcrew: Pitcrew, load_scenario: LoadScenario, logs: Logs
) -> None:
    night = load_scenario("night_with_failures_rerun_broken")

    answer = pitcrew.trigger_night_run(night, allure_launch_id=night.rerun.launch_id)

    rejected, request = logs.lines("pitcrew.api")
    assert rejected | {"timestamp": None} == {
        "timestamp": None,
        "level": "warning",
        "logger": "pitcrew.api.exception_handlers",
        "message": "Trigger rejected",
        "request_id": answer.request_id,
        "step": "night_run",
        "team": "Gateway",
        "environment": "staging",
        "pipeline_id": night.nightly.pipeline_id,
        "launch_id": night.rerun.launch_id,
        "reason": answer.detail,
        "launch_pipeline_ids": [night.rerun.pipeline_id],
    }
    assert (
        request["message"],
        request["level"],
        request["status_code"],
        request["request_id"],
    ) == ("Request handled", "warning", 422, answer.request_id)


def test_trigger_rejected_for_its_launch_leaves_no_run_chain_behind(
    pitcrew: Pitcrew, load_scenario: LoadScenario
) -> None:
    night = load_scenario("night_with_failures_rerun_broken")
    pitcrew.trigger_night_run(night, allure_launch_id=night.rerun.launch_id)

    answer = pitcrew.trigger_night_run(night)

    nightly = pitcrew.run_chain(answer.trace_id)["runs"][0]
    assert (nightly["kind"], nightly["launch_id"]) == (
        "nightly",
        night.nightly.launch_id,
    )


def test_night_run_of_the_pipeline_of_a_rerun_is_rejected(
    pitcrew: Pitcrew, load_scenario: LoadScenario
) -> None:
    """A pipeline belongs to one Run: the Rerun Pitcrew started is no Nightly run."""
    night = load_scenario("night_with_failures_rerun_broken")
    first = pitcrew.trigger_night_run(night)

    answer = pitcrew.trigger_night_run(
        night,
        pipeline_id=night.rerun.pipeline_id,
        allure_launch_id=night.rerun.launch_id,
    )

    assert (answer.status_code, answer.reason) == (
        422,
        f"Pipeline {night.rerun.pipeline_id} is the Rerun of Run chain "
        f"{first.trace_id}, not a Nightly run",
    )
