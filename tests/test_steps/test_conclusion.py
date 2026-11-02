import pytest

from pitcrew.clients.links import WebLinks
from pitcrew.constants import Environment
from pitcrew.db.models.error_group import ErrorGroup, ErrorGroupTest
from pitcrew.db.models.run import Run, RunKind, RunOutcome
from pitcrew.db.models.run_chain import RunChain
from pitcrew.steps.conclusion import conclusion_message
from tests.data import conclusions
from tests.support.config import load_team_config
from tests.support.slack_post import post_text

GATEWAY = load_team_config("gateway")


def night_run(
    pipeline_id: int,
    launch_id: int,
    failed_test_count: int | None,
    broken_reason: str | None = None,
) -> RunChain:
    """A Run chain of Gateway on staging up to its judged Nightly run: broken for the
    reason, otherwise *with failures*."""
    return RunChain(
        team="Gateway",
        environment=Environment.STAGING,
        runs=[
            Run(
                kind=RunKind.NIGHTLY,
                pipeline_id=pipeline_id,
                launch_id=launch_id,
                failed_test_count=failed_test_count,
                outcome=RunOutcome.WITH_FAILURES
                if broken_reason is None
                else RunOutcome.BROKEN,
                outcome_reason=broken_reason,
            )
        ],
    )


def with_rerun(
    chain: RunChain,
    pipeline_id: int,
    launch_id: int,
    failed_test_count: int,
    broken_reason: str | None = None,
) -> RunChain:
    """The Run chain, up to its judged Rerun: broken for the reason, otherwise green or
    *with failures* by its Failed tests."""
    if broken_reason is not None:
        outcome = RunOutcome.BROKEN
    elif failed_test_count:
        outcome = RunOutcome.WITH_FAILURES
    else:
        outcome = RunOutcome.GREEN
    chain.runs.append(
        Run(
            kind=RunKind.RERUN,
            pipeline_id=pipeline_id,
            launch_id=launch_id,
            failed_test_count=failed_test_count,
            outcome=outcome,
            outcome_reason=broken_reason,
        )
    )
    return chain


def small_night(
    rerun_failed_test_count: int,
    rerun_pipeline_id: int = 481658,
    rerun_launch_id: int = 279328,
) -> RunChain:
    """The Run chain of the two Failed tests of launch 278416, up to its Rerun."""
    return with_rerun(
        night_run(480974, 278416, 2),
        rerun_pipeline_id,
        rerun_launch_id,
        rerun_failed_test_count,
    )


def error_group(key: str, *tests: ErrorGroupTest) -> ErrorGroup:
    return ErrorGroup(kind="model", key=key, tests=list(tests))


def grouped(
    test_result_id: int, test_case_id: int | None, name: str = "API: a test"
) -> ErrorGroupTest:
    """A Failed test in an Error group."""
    return ErrorGroupTest(
        test_result_id=test_result_id, test_case_id=test_case_id, name=name
    )


def error_group_of_6(key: str, test_case_id: int) -> ErrorGroup:
    """A group of 6 results of one parametrised test case."""
    return error_group(
        key, *(grouped(test_case_id * 100 + i, test_case_id) for i in range(6))
    )


@pytest.mark.parametrize(
    ("chain", "post"),
    [
        pytest.param(
            night_run(473215, 271942, 0, "1 result out of ~1675 expected"),
            conclusions.BROKEN_NIGHT_RUN_TOO_FEW_RESULTS,
            id="with its Failed test count",
        ),
        pytest.param(
            # Pipeline 476973: canceled, its results were never read.
            night_run(476973, 275171, None, "pipeline canceled at stage test"),
            conclusions.BROKEN_NIGHT_RUN_PIPELINE,
            id="without its Failed test count",
        ),
        pytest.param(
            night_run(
                478951,
                276357,
                685,
                "too many failures, likely an environment problem: "
                "685 of 6292 results failed",
            ),
            conclusions.BROKEN_NIGHT_RUN_TOO_MANY_FAILURES,
            id="too many failures",
        ),
    ],
)
def test_broken_night_run_conclusion(
    links: WebLinks, chain: RunChain, post: str
) -> None:
    message = conclusion_message(chain, None, GATEWAY, links)

    assert post_text({"blocks": message.blocks}) == post


def test_broken_rerun_conclusion(links: WebLinks) -> None:
    chain = with_rerun(
        night_run(478951, 276357, 685),
        481658,
        279328,
        2,
        broken_reason="2 results out of ~223 expected",
    )

    message = conclusion_message(chain, None, GATEWAY, links)

    assert post_text({"blocks": message.blocks}) == conclusions.BROKEN_RERUN


@pytest.mark.parametrize(
    ("chain", "error_groups", "post"),
    [
        pytest.param(
            small_night(0, rerun_pipeline_id=475379, rerun_launch_id=273781),
            [],
            conclusions.GREEN_RERUN,
            id="green",
        ),
        pytest.param(
            small_night(2),
            None,
            conclusions.RERUN_WITHOUT_ERROR_GROUPS,
            id="without the Error groups feature",
        ),
        pytest.param(
            small_night(2),
            [],
            conclusions.RERUN_WITH_NO_ERROR_GROUPS,
            id="no Error groups",
        ),
        pytest.param(
            small_night(2),
            [
                error_group(
                    "DataResponse[RoutersOverview]",
                    grouped(11849203, 124669),
                )
            ],
            conclusions.RERUN_WITH_AN_ERROR_GROUP_AND_THE_REST,
            id="a group and an unrecognized rest",
        ),
        pytest.param(
            small_night(5, rerun_pipeline_id=483287, rerun_launch_id=280791),
            [
                error_group(
                    "PoolModel",
                    grouped(11890501, 89663),
                    grouped(11890502, 100830),
                    grouped(11890503, 106459),
                ),
                error_group(
                    "DataResponse[RoutersOverview]",
                    grouped(11890500, 124669),
                ),
            ],
            conclusions.RERUN_WITH_TWO_ERROR_GROUPS,
            id="groups listing their test cases",
        ),
        pytest.param(
            small_night(6),
            [
                error_group(
                    "LpPositionsV2Model",
                    *(
                        grouped(result_id, test_case_id)
                        for result_id, test_case_id in (
                            (10339129, 98115),
                            (10339130, 98115),
                            (10339131, 98116),
                            (10339132, 98116),
                            (10339133, 98117),
                            (10339134, 98117),
                        )
                    ),
                )
            ],
            conclusions.RERUN_WITH_A_GROUP_OF_MORE_THAN_5_TESTS,
            id="a group of more than 5 tests",
        ),
        pytest.param(
            small_night(2),
            [
                error_group(
                    "PoolModel",
                    grouped(11849203, None, "API: pools list"),
                    grouped(11849204, None, "API: pool by address"),
                )
            ],
            conclusions.RERUN_WITH_A_GROUP_WITHOUT_TEST_CASES,
            id="a group without test cases",
        ),
        pytest.param(
            small_night(2),
            [
                error_group(
                    "PoolModel",
                    grouped(11849203, 124669),
                    grouped(11849204, None, "API: pool by address"),
                )
            ],
            conclusions.RERUN_WITH_A_TEST_WITHOUT_A_TEST_CASE,
            id="a test without a test case",
        ),
        pytest.param(
            small_night(70),
            [
                error_group_of_6("PaginatedResponse[list[FarmsList]]", 1),
                error_group_of_6("DataResponse[Config]", 2),
                error_group_of_6("SwapCreatedNsqModel", 3),
                error_group_of_6("OperationsV3Model", 4),
                error_group_of_6("SwapConfirmedNsqModel", 5),
                error_group_of_6("PoolsInfoResponse", 6),
                error_group_of_6("PoolModel", 7),
                error_group_of_6("LpPositionsV2Model", 8),
                error_group_of_6("OperationsInfoResponse", 9),
                error_group_of_6("DataResponse[RoutersOverview]", 10),
                error_group("DataResponse[PoolInfo]", grouped(1100, 11)),
            ],
            conclusions.RERUN_WITH_11_ERROR_GROUPS,
            id="11 groups: 10 listed and a summary line",
        ),
        pytest.param(
            small_night(2),
            [error_group("Page<Pool> & Co", grouped(11849203, None, "API: a <b> & c"))],
            conclusions.RERUN_ESCAPED,
            id="escaping of <, > and &",
        ),
    ],
)
def test_rerun_conclusion(
    links: WebLinks,
    chain: RunChain,
    error_groups: list[ErrorGroup] | None,
    post: str,
) -> None:
    message = conclusion_message(chain, error_groups, GATEWAY, links)

    assert post_text({"blocks": message.blocks}) == post


def test_conclusion_is_one_block_kit_message_with_the_icon_in_its_text(
    links: WebLinks,
) -> None:
    chain = small_night(0, rerun_pipeline_id=475379, rerun_launch_id=273781)

    message = conclusion_message(chain, [], GATEWAY, links)

    assert message.text == ":white_check_mark: [Pitcrew] Gateway · staging"
    assert list(message.blocks) == [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":white_check_mark: *[Pitcrew] Gateway · staging*",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Nightly run* · 2 Failed tests\n"
                "<https://gitlab.example/gateway/qa_automation/-/pipelines/480974|Pipeline 480974>"
                " · <https://testops.example/launch/278416|Launch 278416>",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Rerun* · 0 Failed tests\n"
                "<https://gitlab.example/gateway/qa_automation/-/pipelines/475379|Pipeline 475379>"
                " · <https://testops.example/launch/273781|Launch 273781>",
            },
        },
    ]
